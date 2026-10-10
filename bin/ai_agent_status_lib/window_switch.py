"""Raise the terminal window an agent session runs in (GUI-toolkit independent).

The hook records the process-ancestor chain of each event as ``client_pids``
(hook → CLI → shell → terminal emulator). Each platform maps that to a window:

* Linux/X11: ``wmctrl -lp`` lists windows with their owner PID; when one emulator
  process owns several windows (gnome-terminal), the window title (project/cwd)
  disambiguates. Title-only match is the last fallback.
* macOS: System Events (AppleScript) brings the first GUI process in the chain to
  the front and raises its window whose title contains the project, when allowed.
* Windows: ``EnumWindows`` finds a visible top-level window owned by a PID in the
  chain (e.g. ``WindowsTerminal.exe``), falling back to the console window handle
  the hook recorded (classic conhost windows are not owned by an ancestor).

Every path is best effort and quiet: a missing tool or permission only logs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable

from ai_agent_status_lib import platform_support

Log = Callable[[str], None]
Window = dict[str, object]


def _noop(_message: str) -> None:
    pass


def target_title(project: str, cwd: str) -> str:
    return (project or (Path(cwd).name if cwd else "")).lower()


def choose_window(windows: list[Window], client_pids: Iterable[int], target: str, log: Log = _noop) -> Window | None:
    """Pick the session's window from ``[{id, pid, title}]``: PID first, then title."""
    pidset = set(client_pids)
    candidates = [window for window in windows if window.get("pid") in pidset]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        titled = [window for window in candidates if target and target in str(window.get("title", "")).lower()]
        if titled:
            return titled[0]
        log(f"switch_to_session: {len(candidates)} windows share the emulator PID and none "
            f"match title '{target}'; raising first (one-process-per-window terminal needed "
            f"for exact targeting)")
        return candidates[0]
    if target:
        titled = [window for window in windows if target in str(window.get("title", "")).lower()]
        if titled:
            return titled[0]
    return None


# ----------------------------- Linux / X11 -----------------------------

def parse_wmctrl_listing(listing: str) -> list[Window]:
    """Parse ``wmctrl -lp`` output into ``[{id, pid, title}]``."""
    windows: list[Window] = []
    for line in listing.splitlines():
        parts = line.split(None, 4)  # winid, desktop, pid, host, title
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[2])
        except ValueError:
            continue
        windows.append({"id": parts[0], "pid": pid, "title": parts[4] if len(parts) >= 5 else ""})
    return windows


def _switch_linux(client_pids: list[int], target: str, log: Log) -> bool:
    wmctrl = shutil.which("wmctrl")
    if not wmctrl:
        log("switch_to_session: wmctrl is not available")
        return False
    try:
        listing = subprocess.run(
            [wmctrl, "-lp"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
        ).stdout
    except OSError as error:
        log(f"wmctrl -lp failed: {error}")
        return False
    windows = parse_wmctrl_listing(listing)
    if not windows:
        log("switch_to_session: no windows reported by wmctrl -lp")
        return False
    chosen = choose_window(windows, client_pids, target, log)
    if chosen is None:
        log(f"switch_to_session: no window matched pids {client_pids} or title '{target}'")
        return False
    try:
        subprocess.run(
            [wmctrl, "-i", "-a", str(chosen["id"])],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    except OSError as error:
        log(f"wmctrl activate {chosen['id']} failed: {error}")
        return False
    return True


# ----------------------------- macOS -----------------------------

MACOS_SWITCH_SCRIPT = """
on run argv
  set target to item 1 of argv
  set pids to rest of argv
  tell application "System Events"
    repeat with p in pids
      set matches to (every process whose unix id is (p as integer) and background only is false)
      if matches is not {} then
        set proc to item 1 of matches
        set frontmost of proc to true
        if target is not "" then
          try
            perform action "AXRaise" of (first window of proc whose name contains target)
          end try
        end if
        return "ok"
      end if
    end repeat
  end tell
  return "none"
end run
"""


def macos_switch_command(client_pids: list[int], target: str) -> list[str]:
    return ["osascript", "-e", MACOS_SWITCH_SCRIPT, target, *(str(pid) for pid in client_pids)]


def _switch_macos(client_pids: list[int], target: str, log: Log) -> bool:
    if not client_pids:
        log("switch_to_session: no client pids recorded for this session")
        return False
    try:
        result = subprocess.run(
            macos_switch_command(client_pids, target),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        log(f"osascript failed: {error}")
        return False
    if result.stdout.strip() != "ok":
        log(f"switch_to_session: no GUI process among pids {client_pids} "
            f"({result.stderr.strip() or 'grant Accessibility access if this keeps failing'})")
        return False
    return True


# ----------------------------- Windows -----------------------------

def list_windows_win32() -> list[Window]:
    """Visible, titled top-level windows as ``[{id, pid, title}]`` (ctypes)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    windows: list[Window] = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append({"id": int(hwnd), "pid": int(pid.value), "title": buffer.value})
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return windows


def activate_window_win32(hwnd: int) -> bool:
    import ctypes

    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    if user32.SetForegroundWindow(hwnd):
        return True
    # Windows only lets the foreground process hand focus away. The session cards never
    # take focus, so tap Alt (the documented way to unlock SetForegroundWindow) and retry.
    vk_menu, keyup = 0x12, 0x0002
    user32.keybd_event(vk_menu, 0, 0, 0)
    user32.keybd_event(vk_menu, 0, keyup, 0)
    return bool(user32.SetForegroundWindow(hwnd))


def _switch_windows(client_pids: list[int], target: str, console_window: int, log: Log) -> bool:
    try:
        windows = list_windows_win32()
    except Exception as error:  # pragma: no cover - depends on Win32
        log(f"EnumWindows failed: {error}")
        windows = []
    pidset = set(client_pids)
    chosen = choose_window([w for w in windows if w["pid"] in pidset], client_pids, target, log)
    hwnd = int(chosen["id"]) if chosen else 0
    if not hwnd and console_window:
        hwnd = console_window
    if not hwnd and target:
        chosen = choose_window(windows, [], target, log)
        hwnd = int(chosen["id"]) if chosen else 0
    if not hwnd:
        log(f"switch_to_session: no window matched pids {client_pids} or title '{target}'")
        return False
    try:
        return activate_window_win32(hwnd)
    except Exception as error:  # pragma: no cover - depends on Win32
        log(f"SetForegroundWindow failed: {error}")
        return False


def switch_to_session(
    project: str,
    cwd: str,
    client_pids: list[int],
    *,
    console_window: int = 0,
    log: Log = _noop,
    platform: str | None = None,
) -> bool:
    """Raise the terminal window of a session; returns whether a window was activated."""
    target = target_title(project, cwd)
    pids = [pid for pid in client_pids if isinstance(pid, int) and pid > 0]
    system = platform or platform_support.PLATFORM
    if system == platform_support.MACOS:
        return _switch_macos(pids, target, log)
    if system == platform_support.WINDOWS:
        return _switch_windows(pids, target, console_window, log)
    return _switch_linux(pids, target, log)
