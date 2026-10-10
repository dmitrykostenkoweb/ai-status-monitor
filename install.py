#!/usr/bin/env python3
"""Cross-platform installer for ai-cli-status-monitor (Linux, macOS, Windows).

Idempotent: copies the scripts and ``ai_agent_status_lib`` into the per-user bin
directory, seeds the data directory (sound, logos, GIF pool, VERSION), creates the
runtime ``.env`` once (never overwrites it), merges the Claude Code / Codex hooks
into their JSON config (backing the files up first), installs autostart for the
current OS and restarts the widget so an update takes effect.

The widget UI needs PySide6 (Qt). When this interpreter cannot import it, the
installer creates a private venv in ``<data dir>/venv`` and installs
``PySide6-Essentials`` there (a one-time download); the hook and the helper
scripts keep using this interpreter. Set ``AI_STATUS_WIDGET_PYTHON`` to use an
interpreter of your own, or ``AI_STATUS_SKIP_PIP=1`` to skip the download.

Run it with the Python interpreter that should run the widget and the hooks:
``python3 install.py`` (Linux/macOS, also what ``install.sh`` does) or
``py install.py`` / ``python install.py`` (Windows).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "bin"))

from ai_agent_status_lib import platform_support  # noqa: E402
from ai_agent_status_lib import process_control  # noqa: E402
from ai_agent_status_lib.env_config import DEFAULT_VALUES  # noqa: E402
from ai_agent_status_lib.env_config import LEGACY_KEYS  # noqa: E402
from ai_agent_status_lib.env_config import load_settings  # noqa: E402
from ai_agent_status_lib.env_config import parse_dotenv  # noqa: E402
from ai_agent_status_lib.env_config import platform_default_values  # noqa: E402
from ai_agent_status_lib.env_config import serialize_env  # noqa: E402

PLATFORM = platform_support.PLATFORM
APP_NAME = "AI CLI Status Widget"
APP_ID = "ai-cli-status-widget"
LAUNCH_AGENT_LABEL = "com.github.ai-cli-status-monitor.widget"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE = "ai-cli-status-monitor"

SCRIPTS = (
    "ai-agent-status-hook",
    "ai-agent-status-panel",
    "ai-agent-status-widget",
    "ai-agent-status-widget-start",
    "ai-agent-status-widget-stop",
    "ai-agent-status-doctor",
    "ai-agent-status-update",
)
POSIX_ONLY_SCRIPTS = ("ai-agent-status-env",)  # Bash dotenv loader, kept for user scripts
DATA_FILES = ("notification.mp3", "openai-logo.svg", "anthropic-logo.png")
PYSIDE_REQUIREMENT = "PySide6-Essentials>=6.5"
QT_PROBE = "import PySide6.QtWidgets"

CLAUDE_EVENTS = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification", "Stop", "StopFailure")
CODEX_EVENTS = ("UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "SubagentStop", "Stop")
CODEX_MATCHER_EVENTS = frozenset({"PreToolUse", "PermissionRequest", "PostToolUse", "SubagentStop"})

TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
Say = Callable[[str], None]


def say(message: str) -> None:
    print(message, flush=True)


# ----------------------------- runtime configuration -----------------------------

def read_legacy_widget_config(config_dir: Path, report: Say = say) -> dict[str, object]:
    path = config_dir / "widget.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as error:
        report(f"⚠️  Cannot migrate widget config: {path}: {error}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


def install_environment_config(
    runtime_env: Path,
    source_env: Path,
    config_dir: Path,
    home: Path,
    environ: dict[str, str] | None = None,
    report: Say = say,
) -> bool:
    """Create the runtime ``.env`` (mode 0600) unless one exists. Returns whether it wrote."""
    if runtime_env.exists():
        report(f"✅ Environment config preserved: {runtime_env}")
        return False
    env = dict(os.environ if environ is None else environ)
    legacy = read_legacy_widget_config(config_dir, report)
    source_values = parse_dotenv(source_env, lambda message: report(f"⚠️  {message}"))
    template_values = parse_dotenv(PROJECT_DIR / ".env.default")
    explicit_keys = {key for key in DEFAULT_VALUES if key in env}
    defaults = platform_default_values()

    # Directory values copied verbatim from the (Linux/macOS) template are defaults,
    # not choices: let the current OS pick its own directories.
    for key in ("AI_STATUS_CACHE_DIR", "AI_STATUS_CONFIG_DIR", "AI_STATUS_DATA_DIR"):
        if source_values.get(key) == DEFAULT_VALUES[key]:
            source_values[key] = defaults[key]

    # Values unchanged from the public template are defaults, not intentional
    # overrides, so legacy widget customizations may take precedence on migration.
    for env_key, legacy_key in LEGACY_KEYS.items():
        if env_key in explicit_keys or legacy_key not in legacy:
            continue
        if source_values.get(env_key, DEFAULT_VALUES[env_key]) == template_values.get(env_key, DEFAULT_VALUES[env_key]):
            source_values.pop(env_key, None)

    process_values = {"HOME": str(home)}
    process_values.update({key: env[key] for key in explicit_keys})
    warnings: list[str] = []
    settings = load_settings(
        environ=process_values,
        env_path=source_env,
        dotenv_values=source_values,
        legacy=legacy,
        diagnostic=warnings.append,
    )
    for message in warnings:
        report(f"⚠️  {message}")
    runtime_env.parent.mkdir(parents=True, exist_ok=True)
    runtime_env.write_text(serialize_env(settings.as_env()), encoding="utf-8")
    try:
        runtime_env.chmod(0o600)
    except OSError:
        pass
    report(f"✅ Environment config installed: {runtime_env}")
    return True


# ----------------------------- hooks -----------------------------

def hook_group(command: str, event: str, codex: bool) -> dict[str, object]:
    group: dict[str, object] = {"hooks": [{"type": "command", "command": command}]}
    if codex and event in CODEX_MATCHER_EVENTS:
        group["matcher"] = "*"
    return group


def snippet(command: str, events: tuple[str, ...], codex: bool = False) -> str:
    hooks = {event: [hook_group(command, event, codex)] for event in events}
    return json.dumps({"hooks": hooks}, ensure_ascii=False, indent=2)


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.bak.{TIMESTAMP}")
    shutil.copy2(path, target)
    return target


def add_hooks(path: Path, command: str, events: tuple[str, ...], codex: bool = False, report: Say = say) -> bool:
    """Merge ``command`` into ``path``'s hooks for ``events``; never drops existing hooks."""
    def manual() -> bool:
        report("Manual snippet:")
        report(snippet(command, events, codex=codex))
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    data: object = {}
    if not created:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
            made = backup(path)
            report(f"⚠️  Cannot merge hooks into invalid JSON: {path}")
            report(f"   Error: {error}")
            if made:
                report(f"   Backup created: {made}")
            return manual()
        if not isinstance(data, dict):
            made = backup(path)
            report(f"⚠️  Cannot merge hooks because top-level JSON is not an object: {path}")
            if made:
                report(f"   Backup created: {made}")
            return manual()
    assert isinstance(data, dict)

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        report(f"⚠️  Cannot merge hooks because {path} has non-object 'hooks'.")
        return manual()

    changed = False
    for event in events:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            report(f"⚠️  Cannot merge event {event} because it is not a list in {path}.")
            return manual()
        exists = any(
            isinstance(handler, dict) and handler.get("type") == "command" and handler.get("command") == command
            for group in groups if isinstance(group, dict) and isinstance(group.get("hooks"), list)
            for handler in group["hooks"]
        )
        if not exists:
            groups.append(hook_group(command, event, codex))
            changed = True

    if changed or created:
        if not created:
            made = backup(path)
            if made:
                report(f"Backup created: {made}")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report(f"✅ Hooks installed: {path}")
    else:
        report(f"✅ Hooks already installed: {path}")
    return True


# ----------------------------- files -----------------------------

def copy_scripts(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    names = SCRIPTS + (() if PLATFORM == platform_support.WINDOWS else POSIX_ONLY_SCRIPTS)
    for name in names:
        target = bin_dir / name
        shutil.copyfile(PROJECT_DIR / "bin" / name, target)
        if PLATFORM != platform_support.WINDOWS:
            target.chmod(0o755)
    library = bin_dir / "ai_agent_status_lib"
    shutil.rmtree(library, ignore_errors=True)
    shutil.copytree(PROJECT_DIR / "bin" / "ai_agent_status_lib", library,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Remove the retired toggle script from earlier installs.
    (bin_dir / "ai-agent-status-widget-toggle").unlink(missing_ok=True)
    if PLATFORM == platform_support.WINDOWS:
        write_windows_shims(bin_dir)


def write_windows_shims(bin_dir: Path) -> None:
    """``ai-agent-status-<name>.cmd`` wrappers so the tools run by name from cmd/PowerShell."""
    python = sys.executable
    for name in SCRIPTS:
        if name == "ai-agent-status-hook":
            continue  # the agents call the hook with an explicit interpreter
        interpreter = platform_support.gui_python(python) if name == "ai-agent-status-widget" else python
        (bin_dir / f"{name}.cmd").write_text(
            f'@echo off\r\n"{interpreter}" "%~dp0{name}" %*\r\n', encoding="utf-8"
        )


def copy_data(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        shutil.copyfile(PROJECT_DIR / "assets" / name, data_dir / name)
    # Seed the local GIF sticker pool (gifs/<status>/*). Never overwrite or delete the
    # user's own GIFs: only files that are not there yet are added.
    source_gifs = PROJECT_DIR / "assets" / "gifs"
    for source in source_gifs.rglob("*"):
        if source.is_file():
            target = data_dir / "gifs" / source.relative_to(source_gifs)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    # Record the version and where we installed from, so ai-agent-status-update can
    # pull the right clone and the widget can tell when a newer version is published.
    shutil.copyfile(PROJECT_DIR / "VERSION", data_dir / "VERSION")
    (data_dir / "install_source").write_text(f"{PROJECT_DIR}\n", encoding="utf-8")


# ----------------------------- autostart -----------------------------

def install_linux_desktop(home: Path, bin_dir: Path, python: str) -> list[str]:
    autostart_dir = home / ".config" / "autostart"
    applications_dir = home / ".local" / "share" / "applications"
    icons_dir = home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    pixmaps_dir = home / ".local" / "share" / "pixmaps"
    for directory in (autostart_dir, applications_dir, icons_dir, pixmaps_dir):
        directory.mkdir(parents=True, exist_ok=True)
    icon = pixmaps_dir / f"{APP_ID}.png"
    shutil.copyfile(PROJECT_DIR / "assets" / f"{APP_ID}.png", icons_dir / f"{APP_ID}.png")
    shutil.copyfile(PROJECT_DIR / "assets" / f"{APP_ID}.png", icon)

    autostart = autostart_dir / f"{APP_ID}.desktop"
    launcher = applications_dir / f"{APP_ID}.desktop"
    autostart.write_text(
        "[Desktop Entry]\nType=Application\n"
        f"Name={APP_NAME}\nComment=Floating status widget for Claude Code and Codex CLI\n"
        f'Exec="{python}" "{bin_dir}/ai-agent-status-widget"\nIcon={icon}\nTerminal=false\n'
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
    launcher.write_text(
        "[Desktop Entry]\nType=Application\n"
        f"Name={APP_NAME}\nComment=Open floating status widget for Claude Code and Codex CLI\n"
        f"Exec={bin_dir}/ai-agent-status-widget-start\nIcon={icon}\nTerminal=false\n"
        "Categories=Utility;\nStartupNotify=false\n",
        encoding="utf-8",
    )
    autostart.chmod(0o755)
    launcher.chmod(0o755)
    # Remove the retired toggle launcher from earlier installs.
    (applications_dir / f"{APP_ID}-toggle.desktop").unlink(missing_ok=True)
    for tool, args in (("update-desktop-database", [str(applications_dir)]),
                       ("gtk-update-icon-cache", ["-q", str(home / ".local" / "share" / "icons" / "hicolor")])):
        if shutil.which(tool):
            subprocess.run([tool, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return [f"Autostart installed:\n  {autostart}", f"Application launcher installed:\n  {launcher}"]


def launch_agent_plist(argv: list[str], log_file: Path) -> str:
    from xml.sax.saxutils import escape

    arguments = "\n".join(f"    <string>{escape(arg)}</string>" for arg in argv)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCH_AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{arguments}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>StandardOutPath</key>
  <string>{escape(str(log_file))}</string>
  <key>StandardErrorPath</key>
  <string>{escape(str(log_file))}</string>
</dict>
</plist>
"""


def install_macos_launch_agent(home: Path, bin_dir: Path, cache_dir: Path, python: str) -> list[str]:
    """Start the widget at login. RunAtLoad only (no KeepAlive): quitting it stays quit."""
    agents_dir = home / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist = agents_dir / f"{LAUNCH_AGENT_LABEL}.plist"
    argv = process_control.widget_argv(bin_dir, python)
    plist.write_text(launch_agent_plist(argv, cache_dir / "widget.log"), encoding="utf-8")
    return [f"Login item (LaunchAgent) installed:\n  {plist}"]


def install_windows_run_key(bin_dir: Path, python: str) -> list[str]:
    """Start the widget at sign-in via HKCU\\...\\Run (pythonw, so no console window)."""
    import winreg  # type: ignore[import-not-found]

    command = platform_support.quote_command(
        process_control.widget_argv(bin_dir, platform_support.gui_python(python)), platform_support.WINDOWS
    )
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, command)
    return [f"Sign-in autostart installed:\n  HKCU\\{WINDOWS_RUN_KEY}\\{WINDOWS_RUN_VALUE}"]


def install_autostart(home: Path, bin_dir: Path, cache_dir: Path, python: str) -> list[str]:
    try:
        if PLATFORM == platform_support.WINDOWS:
            return install_windows_run_key(bin_dir, python)
        if PLATFORM == platform_support.MACOS:
            return install_macos_launch_agent(home, bin_dir, cache_dir, python)
        return install_linux_desktop(home, bin_dir, python)
    except OSError as error:
        return [f"⚠️  Autostart not installed: {error}"]


# ----------------------------- widget runtime -----------------------------

def can_import_qt(python: str) -> bool:
    try:
        result = subprocess.run([python, "-c", QT_PROBE], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def venv_python(venv: Path) -> Path:
    if PLATFORM == platform_support.WINDOWS:
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def ensure_widget_python(data_dir: Path, environ: dict[str, str] | None = None) -> str | None:
    """An interpreter that can import PySide6, setting up ``<data>/venv`` when needed."""
    env = os.environ if environ is None else environ
    chosen = env.get("AI_STATUS_WIDGET_PYTHON", "").strip()
    if chosen:
        if can_import_qt(chosen):
            return chosen
        say(f"⚠️  AI_STATUS_WIDGET_PYTHON={chosen} cannot import PySide6.")
        return None
    if can_import_qt(sys.executable):
        return sys.executable
    venv = data_dir / "venv"
    python = venv_python(venv)
    if python.exists() and can_import_qt(str(python)):
        return str(python)
    if env.get("AI_STATUS_SKIP_PIP"):
        say("AI_STATUS_SKIP_PIP is set: not installing PySide6.")
        return None
    pip = [str(python), "-m", "pip"]
    if not python.exists():
        say(f"Creating a private Python environment for the widget: {venv}")
        result = subprocess.run([sys.executable, "-m", "venv", str(venv)], check=False)
        if result.returncode != 0 or not python.exists():
            # Debian/Ubuntu/Mint ship venv without ensurepip unless python3-venv is
            # installed; a pip-less venv still works when this Python has pip itself.
            shutil.rmtree(venv, ignore_errors=True)
            result = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=False)
            if result.returncode != 0 or not python.exists():
                say("⚠️  Could not create the venv.")
                return None
    if subprocess.run([*pip, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      check=False).returncode != 0:
        pip = [sys.executable, "-m", "pip", "--python", str(python)]
    say(f"Installing {PYSIDE_REQUIREMENT} into it (one-time download, about 100 MB)…")
    result = subprocess.run(
        [*pip, "install", "--disable-pip-version-check", "--upgrade", PYSIDE_REQUIREMENT],
        check=False,
    )
    if result.returncode != 0 or not can_import_qt(str(python)):
        say("⚠️  PySide6 could not be installed.")
        return None
    return str(python)


def toolkit_hint() -> str:
    if PLATFORM == platform_support.LINUX:
        return (
            "  sudo apt install python3-venv python3-pip libxcb-cursor0 wmctrl\n"
            "  then run the installer again (or set AI_STATUS_WIDGET_PYTHON to a Python with PySide6)."
        )
    if PLATFORM == platform_support.MACOS:
        return "  Install Python 3.9+ from python.org or Homebrew, then run the installer again."
    return "  Install Python 3.9+ from python.org (tick \"Add python.exe to PATH\"), then run the installer again."


def has_display() -> bool:
    if PLATFORM != platform_support.LINUX:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def restart_widget(bin_dir: Path, cache_dir: Path, python: str) -> None:
    """Restart so a reinstall/update picks up the new code."""
    process_control.stop_widget(cache_dir)
    _started, message = process_control.start_widget(bin_dir, cache_dir, python=platform_support.gui_python(python))
    say(message)


# ----------------------------- main -----------------------------

def main() -> int:
    if sys.version_info < (3, 9):
        say("Python 3.9 or newer is required.")
        return 1
    home = platform_support.home_dir()
    runtime_raw = os.environ.get("AI_STATUS_ENV_FILE", "").strip()
    runtime_env = Path(os.path.expanduser(runtime_raw)) if runtime_raw else platform_support.default_env_file(home)
    source_env = PROJECT_DIR / (".env" if (PROJECT_DIR / ".env").is_file() else ".env.default")

    # Resolve directories from the runtime .env when present, else from the source
    # template with this OS's default directories.
    if runtime_env.exists():
        settings = load_settings(env_path=runtime_env)
    else:
        values = parse_dotenv(source_env)
        defaults = platform_default_values()
        for key in ("AI_STATUS_CACHE_DIR", "AI_STATUS_CONFIG_DIR", "AI_STATUS_DATA_DIR"):
            if values.get(key) == DEFAULT_VALUES[key]:
                values[key] = defaults[key]
        settings = load_settings(env_path=source_env, dotenv_values=values)
    os.environ["AI_STATUS_ENV_FILE"] = str(runtime_env)

    bin_dir = platform_support.default_bin_dir(home)
    cache_dir, config_dir, data_dir = settings.cache_dir, settings.config_dir, settings.data_dir
    for directory in (cache_dir / "last_payloads", cache_dir / "debug_payloads", config_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)

    copy_scripts(bin_dir)
    copy_data(data_dir)
    widget_python = ensure_widget_python(data_dir)
    process_control.save_interpreters(data_dir, sys.executable, widget_python)
    notes = install_autostart(home, bin_dir, cache_dir, widget_python or sys.executable)
    install_environment_config(runtime_env, source_env, config_dir, home)

    add_hooks(home / ".claude" / "settings.json", process_control.hook_command(bin_dir, "claude"), CLAUDE_EVENTS)
    codex_config_toml = home / ".codex" / "config.toml"
    if codex_config_toml.exists() and "[hooks" in codex_config_toml.read_text(encoding="utf-8", errors="ignore"):
        say("⚠️  ~/.codex/config.toml already contains inline hooks.")
        say("   Codex can load hooks from both config.toml and hooks.json, but may warn when both exist in one layer.")
    add_hooks(home / ".codex" / "hooks.json", process_control.hook_command(bin_dir, "codex"), CODEX_EVENTS, codex=True)

    toolkit_ok = widget_python is not None
    version = (PROJECT_DIR / "VERSION").read_text(encoding="utf-8").strip()
    suffix = ".cmd" if PLATFORM == platform_support.WINDOWS else ""
    say("")
    say(f"Installed ai-cli-status-monitor {version} ({PLATFORM}).")
    say("")
    say("Commands:")
    for name in ("ai-agent-status-widget", "ai-agent-status-doctor", "ai-agent-status-panel", "ai-agent-status-update"):
        say(f"  {bin_dir / (name + suffix)}")
    if PLATFORM == platform_support.WINDOWS:
        say(f"Add {bin_dir} to your PATH to run them by name.")
    say("")
    if not toolkit_ok:
        say("The widget UI needs PySide6 (Qt), which is not available yet:")
        say(toolkit_hint())
        say("")
    missing_libraries = platform_support.missing_linux_qt_packages() if PLATFORM == platform_support.LINUX else []
    if missing_libraries:
        say(f"⚠️  Qt needs {', '.join(missing_libraries)} to open windows on X11:")
        say(f"  sudo apt install {' '.join(missing_libraries)}")
        say("")
    for note in notes:
        say(note)
    say(f"Notification sound installed:\n  {data_dir / 'notification.mp3'}")
    say(f"Environment config:\n  {runtime_env}")
    say("")
    say(f"Run doctor:\n  {bin_dir / ('ai-agent-status-doctor' + suffix)}")
    say("")

    if widget_python is not None and has_display() and not missing_libraries:
        restart_widget(bin_dir, cache_dir, widget_python)
    elif toolkit_ok:
        say("No display found, widget was not started now. It will start on desktop login.")
    else:
        say("PySide6 is missing, widget was not started. Hooks and status files work without it.")
    say("")
    say("For Codex CLI, open /hooks and trust the new hook if Codex asks for review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
