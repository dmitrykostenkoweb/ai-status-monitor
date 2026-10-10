"""Start the widget at login — or not (Settings → "Start at login", ``AI_STATUS_AUTOSTART``).

Shared by the installer and the widget so both write exactly the same entry:

* Linux: ``~/.config/autostart/ai-cli-status-widget.desktop`` (XDG autostart);
* macOS: the LaunchAgent ``~/Library/LaunchAgents/com.github.ai-cli-status-monitor.widget.plist``
  (RunAtLoad only, no KeepAlive: quitting the widget keeps it quit);
* Windows: ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\ai-cli-status-monitor``
  (``pythonw.exe``, so no console window).

Disabling removes the entry; enabling writes it again.
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.sax.saxutils import escape

from ai_agent_status_lib import platform_support
from ai_agent_status_lib import process_control

APP_ID = "ai-cli-status-widget"
APP_NAME = "AI CLI Status Widget"
LAUNCH_AGENT_LABEL = "com.github.ai-cli-status-monitor.widget"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE = "ai-cli-status-monitor"


def linux_entry(home: Path) -> Path:
    return home / ".config" / "autostart" / f"{APP_ID}.desktop"


def linux_icon(home: Path) -> Path:
    return home / ".local" / "share" / "pixmaps" / f"{APP_ID}.png"


def macos_entry(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def desktop_entry(python: str, bin_dir: Path, icon: Path) -> str:
    return (
        "[Desktop Entry]\nType=Application\n"
        f"Name={APP_NAME}\nComment=Floating status widget for Claude Code and Codex CLI\n"
        f'Exec="{python}" "{bin_dir}/ai-agent-status-widget"\nIcon={icon}\nTerminal=false\n'
        "X-GNOME-Autostart-enabled=true\n"
    )


def launch_agent_path(current: str) -> str:
    """PATH for the LaunchAgent: launchd starts it with only /usr/bin:/bin:/usr/sbin:/sbin,
    which hides Homebrew/npm installs of `codex` (needed for Codex usage limits)."""
    entries: list[str] = []
    for entry in ["/opt/homebrew/bin", "/usr/local/bin", *current.split(os.pathsep), "/usr/bin", "/bin",
                  "/usr/sbin", "/sbin"]:
        if entry and entry not in entries:
            entries.append(entry)
    return os.pathsep.join(entries)


def launch_agent_plist(argv: list[str], log_file: Path, path: str = "") -> str:
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
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>{escape(launch_agent_path(path))}</string>
  </dict>
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


def windows_command(bin_dir: Path, python: str) -> str:
    return platform_support.quote_command(
        process_control.widget_argv(bin_dir, platform_support.gui_python(python, platform_support.WINDOWS)),
        platform_support.WINDOWS,
    )


def enable(home: Path, bin_dir: Path, cache_dir: Path, python: str, platform: str | None = None) -> str:
    """Install the login entry; returns a human-readable description of where it went."""
    system = platform or platform_support.PLATFORM
    if system == platform_support.WINDOWS:
        import winreg  # type: ignore[import-not-found]

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, windows_command(bin_dir, python))
        return f"HKCU\\{WINDOWS_RUN_KEY}\\{WINDOWS_RUN_VALUE}"
    if system == platform_support.MACOS:
        plist = macos_entry(home)
        plist.parent.mkdir(parents=True, exist_ok=True)
        argv = process_control.widget_argv(bin_dir, python)
        plist.write_text(launch_agent_plist(argv, cache_dir / "widget.log", os.environ.get("PATH", "")),
                         encoding="utf-8")
        return str(plist)
    entry = linux_entry(home)
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(desktop_entry(python, bin_dir, linux_icon(home)), encoding="utf-8")
    entry.chmod(0o755)
    return str(entry)


def disable(home: Path, platform: str | None = None) -> None:
    """Remove the login entry (a missing entry is fine)."""
    system = platform or platform_support.PLATFORM
    if system == platform_support.WINDOWS:
        import winreg  # type: ignore[import-not-found]

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, WINDOWS_RUN_VALUE)
        except FileNotFoundError:
            pass
        return
    entry = macos_entry(home) if system == platform_support.MACOS else linux_entry(home)
    entry.unlink(missing_ok=True)


def is_enabled(home: Path, platform: str | None = None) -> bool:
    system = platform or platform_support.PLATFORM
    if system == platform_support.WINDOWS:
        try:
            import winreg  # type: ignore[import-not-found]

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
                winreg.QueryValueEx(key, WINDOWS_RUN_VALUE)
            return True
        except OSError:
            return False
    entry = macos_entry(home) if system == platform_support.MACOS else linux_entry(home)
    return entry.exists()


def set_enabled(enabled: bool, home: Path, bin_dir: Path, cache_dir: Path, python: str,
                platform: str | None = None) -> None:
    if enabled:
        enable(home, bin_dir, cache_dir, python, platform)
    else:
        disable(home, platform)
