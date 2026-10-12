"""Remove what ``install.py`` put in place (``ai-agent-status-uninstall``, and the Windows
"Installed apps" Uninstall button).

Removed: the running widget, the login entry, menu/desktop shortcuts (and on Windows the
Installed-apps entry), our hook entries in ``~/.claude/settings.json`` / ``~/.codex/hooks.json``
(other hooks stay; the file is backed up first), the installed scripts, and the data and cache
directories. The configuration directory (runtime ``.env``, KLIPY key, window positions) is kept
unless ``purge`` is set. A WSL install that feeds the Windows widget never deletes that widget's
cache dir.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from ai_agent_status_lib import autostart
from ai_agent_status_lib import platform_support
from ai_agent_status_lib import process_control

HOOK_MARKER = "ai-agent-status-hook"
SCRIPT_PREFIX = "ai-agent-status-"
LIBRARY_DIR = "ai_agent_status_lib"
Say = Callable[[str], None]


def strip_hooks(data: object, marker: str = HOOK_MARKER) -> int:
    """Drop every hook handler whose command contains ``marker``; returns how many went.

    Groups left without handlers and events left without groups are dropped too, so the
    file looks as it did before the install. Anything malformed is left alone.
    """
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        return 0
    hooks = data["hooks"]
    removed = 0
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                kept_groups.append(group)
                continue
            kept = [handler for handler in handlers
                    if not (isinstance(handler, dict) and marker in str(handler.get("command", "")))]
            removed += len(handlers) - len(kept)
            if kept:
                group["hooks"] = kept
                kept_groups.append(group)
            elif not handlers:
                kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]
    return removed


def remove_hooks(path: Path, report: Say) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        report(f"⚠️  Not touching {path} ({error}); remove the {HOOK_MARKER} entries by hand.")
        return
    if strip_hooks(data) == 0:
        return
    backup = path.with_name(f"{path.name}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report(f"✅ Hooks removed from {path} (backup: {backup})")


def installed_files(bin_dir: Path) -> list[Path]:
    """Our scripts, their ``.cmd`` wrappers and the library in ``bin_dir`` (shared ``~/.local/bin`` on POSIX)."""
    if not bin_dir.is_dir():
        return []
    files = sorted(path for path in bin_dir.glob(f"{SCRIPT_PREFIX}*") if path.is_file())
    library = bin_dir / LIBRARY_DIR
    return files + ([library] if library.is_dir() else [])


def stop_widget(cache_dir: Path, report: Say) -> None:
    _stopped, message = process_control.stop_widget(cache_dir)  # waits until it is gone
    report(message)


def remove_path(path: Path, report: Say) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass
    if path.exists():
        report(f"⚠️  Could not remove {path} (in use?); delete it by hand.")
    else:
        report(f"✅ Removed {path}")


def plan(home: Path, bin_dir: Path, cache_dir: Path, config_dir: Path, data_dir: Path, purge: bool) -> list[Path]:
    """The files and directories :func:`run` deletes, in order."""
    targets = installed_files(bin_dir) + [data_dir]
    if not platform_support.is_windows_mount(cache_dir):
        targets.append(cache_dir)
    if purge:
        targets.append(config_dir)
    return [path for path in targets if path.exists()]


def run(home: Path, bin_dir: Path, cache_dir: Path, config_dir: Path, data_dir: Path,
        purge: bool = False, report: Say = print) -> None:
    targets = plan(home, bin_dir, cache_dir, config_dir, data_dir, purge)
    if not platform_support.is_windows_mount(cache_dir):
        stop_widget(cache_dir, report)
    try:
        autostart.disable(home)
        report("✅ Start at login removed")
    except OSError as error:
        report(f"⚠️  Could not remove the login entry: {error}")
    if platform_support.PLATFORM == platform_support.WINDOWS:
        from ai_agent_status_lib import windows_app

        for removed in windows_app.uninstall():
            report(f"✅ Removed {removed}")
    elif platform_support.PLATFORM == platform_support.LINUX:
        share = home / ".local" / "share"
        for path in (share / "applications" / f"{autostart.APP_ID}.desktop", autostart.linux_icon(home),
                     *autostart.linux_theme_icons(home), *autostart.legacy_linux_icons(home)):
            remove_path(path, report)
    remove_hooks(home / ".claude" / "settings.json", report)
    remove_hooks(home / ".codex" / "hooks.json", report)
    for path in targets:
        remove_path(path, report)
    # The per-user app folders on Windows (…\Local\ai-cli-status-monitor) go once empty.
    for parent in {bin_dir.parent, data_dir.parent, cache_dir.parent}:
        if parent.name == platform_support.APP_DIR_NAME:
            try:
                parent.rmdir()
            except OSError:
                pass
    if not purge and config_dir.exists():
        report(f"Kept your settings in {config_dir} (run with --purge to delete them too).")
