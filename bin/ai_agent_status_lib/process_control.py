"""Start/stop the widget and build the commands that run the installed scripts.

Used by ``ai-agent-status-widget-start`` / ``-stop``, the installer (which restarts
the widget after an install or update) and the widget's own self-update button.
POSIX runs the helper scripts through their ``#!/usr/bin/env python3`` shebang;
Windows has no shebangs, so each script runs as ``python.exe <script>``.

The widget needs PySide6, which the installer may have put into a private venv
(``<data>/venv``). The installer records both interpreters in
``<data>/interpreters.json`` — ``base`` (runs the hook and helpers) and ``widget``
(can import PySide6) — and everything that launches the widget reads it from there.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from ai_agent_status_lib import platform_support

WIDGET_SCRIPT = "ai-agent-status-widget"
HOOK_SCRIPT = "ai-agent-status-hook"


INTERPRETERS_FILE = "interpreters.json"


def load_interpreters(data_dir: Path) -> dict[str, str]:
    try:
        loaded = json.loads((data_dir / INTERPRETERS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {key: value for key, value in loaded.items() if isinstance(value, str) and Path(value).exists()}


def save_interpreters(data_dir: Path, base: str, widget: str | None) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    values = {"base": base}
    if widget:
        values["widget"] = widget
    (data_dir / INTERPRETERS_FILE).write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")


def base_interpreter(data_dir: Path) -> str:
    """The interpreter for the hook and helper scripts (no GUI toolkit needed)."""
    return load_interpreters(data_dir).get("base") or sys.executable


def widget_interpreter(data_dir: Path) -> str:
    """The interpreter that can run the Qt widget (``pythonw.exe`` on Windows)."""
    return platform_support.gui_python(load_interpreters(data_dir).get("widget") or sys.executable)


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


def widget_argv(bin_dir: Path, python: str, *extra_args: str) -> list[str]:
    """argv that starts the widget with an explicit (possibly venv) interpreter."""
    return [python, str(bin_dir / WIDGET_SCRIPT), *extra_args]


def start_widget(bin_dir: Path, cache_dir: Path, *extra_args: str, python: str | None = None) -> tuple[bool, str]:
    """Start the widget detached, unless it already runs. Returns ``(started, message)``."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    if running_widget_pid(cache_dir) is not None:
        return False, "ai-agent-status-widget is already running"
    argv = widget_argv(bin_dir, python or platform_support.gui_python(), *extra_args)
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


# A Python interpreter running the widget script itself: the command line must START with the
# interpreter (``[…/]python[w][3.x][.exe]``, quoted or not) and continue with the widget script,
# so ``-start``/``-stop``, editors, grep, or a shell whose ``-c`` text merely mentions the
# script never match.
_PYTHON = r'pythonw?(?:\d+(?:\.\d+)*)?(?:\.exe)?'
WIDGET_COMMAND = re.compile(
    r'^\s*(?:"(?:[^"]*[\\/])?' + _PYTHON + r'"|(?:[^\s"]*[\\/])?' + _PYTHON + r')\s+'
    r'(?:"(?:[^"]*[\\/])?' + re.escape(WIDGET_SCRIPT) + r'"|(?:[^\s"]*[\\/])?' + re.escape(WIDGET_SCRIPT) + r')'
    r'(?=\s|$)',
    re.IGNORECASE,
)


def is_widget_command(command: str) -> bool:
    return bool(WIDGET_COMMAND.search(command))


def widget_pids(processes: list[tuple[int, str]] | None = None) -> list[int]:
    """Every running widget process, found by its command line (not only the one in ``widget.pid``)."""
    table = platform_support.list_processes() if processes is None else processes
    own = os.getpid()
    return [pid for pid, command in table if pid != own and is_widget_command(command)]


def stop_widget(cache_dir: Path, wait_seconds: float = 5.0) -> tuple[bool, str]:
    """Stop the widget: the one in ``widget.pid`` and any other widget process still running
    (a re-exec wrapper, a duplicate). Waits until they are gone so the caller may replace
    their files (Windows keeps a running interpreter's files locked). Returns ``(stopped, message)``.
    """
    pids = []
    recorded = running_widget_pid(cache_dir)
    if recorded is not None:
        pids.append(recorded)
    pids.extend(pid for pid in widget_pids() if pid not in pids)
    try:
        pid_file(cache_dir).unlink()
    except OSError:
        pass
    if not pids:
        return False, "ai-agent-status-widget is not running"
    for pid in pids:
        platform_support.terminate_pid(pid)
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline and any(platform_support.pid_alive(pid) for pid in pids):
        time.sleep(0.1)
    return True, "ai-agent-status-widget stopped"


