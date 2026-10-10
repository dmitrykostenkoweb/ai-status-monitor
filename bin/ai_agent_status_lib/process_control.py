"""Start/stop the widget and build the commands that run the installed scripts.

Used by ``ai-agent-status-widget-start`` / ``-stop``, the installer (which restarts
the widget after an install or update) and the widget's own self-update button.
POSIX runs the scripts through their ``#!/usr/bin/env python3`` shebang; Windows has
no shebangs, so each script runs as ``python.exe <script>`` (``pythonw.exe`` for
the GUI, so no console window appears).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ai_agent_status_lib import platform_support

WIDGET_SCRIPT = "ai-agent-status-widget"
HOOK_SCRIPT = "ai-agent-status-hook"


def script_argv(script: Path, *args: str, gui: bool = False, platform: str | None = None,
                python: str | None = None) -> list[str]:
    """argv that runs one of the installed Python scripts on this OS."""
    if (platform or platform_support.PLATFORM) == platform_support.WINDOWS:
        interpreter = platform_support.gui_python(python, platform) if gui else (python or sys.executable)
        return [interpreter, str(script), *args]
    return [str(script), *args]


def hook_command(bin_dir: Path, agent: str, platform: str | None = None, python: str | None = None) -> str:
    """The hook ``command`` string written into ``~/.claude`` / ``~/.codex`` hook config."""
    system = platform or platform_support.PLATFORM
    script = bin_dir / HOOK_SCRIPT
    if system == platform_support.WINDOWS:
        argv = [python or sys.executable, str(script), "--agent", agent]
    else:
        # Keep the historical shape (``<bin>/ai-agent-status-hook --agent X``) so the
        # installer recognises hooks written by earlier versions and stays idempotent.
        argv = [f"{bin_dir.as_posix()}/{HOOK_SCRIPT}", "--agent", agent]
    return platform_support.quote_command(argv, system)


def pid_file(cache_dir: Path) -> Path:
    return cache_dir / "widget.pid"


def running_widget_pid(cache_dir: Path) -> int | None:
    """PID from ``widget.pid`` when that process is alive and really is the widget."""
    try:
        raw = pid_file(cache_dir).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw.isdigit():
        return None
    pid = int(raw)
    if not platform_support.pid_alive(pid):
        return None
    command = platform_support.process_command_line(pid)
    if command and WIDGET_SCRIPT not in command:
        return None  # PID was reused by an unrelated process
    return pid


def start_widget(bin_dir: Path, cache_dir: Path, *extra_args: str) -> tuple[bool, str]:
    """Start the widget detached, unless it already runs. Returns ``(started, message)``."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    if running_widget_pid(cache_dir) is not None:
        return False, "ai-agent-status-widget is already running"
    argv = script_argv(bin_dir / WIDGET_SCRIPT, *extra_args, gui=True)
    with open(cache_dir / "widget.log", "a", encoding="utf-8") as log:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            **platform_support.detached_flags(),
        )
    pid_file(cache_dir).write_text(f"{process.pid}\n", encoding="utf-8")
    return True, "ai-agent-status-widget started"


def stop_widget(cache_dir: Path) -> tuple[bool, str]:
    """Stop the widget recorded in ``widget.pid``. Returns ``(stopped, message)``."""
    pid = running_widget_pid(cache_dir)
    try:
        pid_file(cache_dir).unlink()
    except OSError:
        pass
    if pid is None:
        return False, "ai-agent-status-widget is not running"
    platform_support.terminate_pid(pid)
    return True, "ai-agent-status-widget stopped"
