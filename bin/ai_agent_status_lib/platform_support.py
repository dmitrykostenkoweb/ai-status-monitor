"""Operating-system specific plumbing shared by the hook, widget and helpers.

Everything that differs between Linux, macOS and Windows lives here so the rest of
the code can stay platform-neutral: default runtime directories, the process
ancestry the widget uses to find a session's terminal window, the per-terminal
session key for agents that send no session id, opening files/URLs, playing the
notification sound, starting a detached process and checking whether a PID is alive.

Nothing in this module may raise on an unexpected environment: callers (notably the
hook, which runs inside the agent CLI) rely on a quiet best-effort fallback.
"""

from __future__ import annotations

import os
import shutil
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Mapping, Sequence

LINUX = "linux"
MACOS = "macos"
WINDOWS = "windows"

APP_DIR_NAME = "ai-cli-status-monitor"
MAX_ANCESTORS = 12


def current_platform(value: str | None = None) -> str:
    """Map ``sys.platform`` (or ``value``) to ``linux`` / ``macos`` / ``windows``."""
    raw = sys.platform if value is None else value
    if raw.startswith("win") or raw == "cygwin":
        return WINDOWS
    if raw == "darwin":
        return MACOS
    return LINUX


PLATFORM = current_platform()


# ----------------------------- WSL bridge -----------------------------
#
# Agents running inside WSL can feed a widget running on Windows: the hook (installed
# in WSL, hooks only) writes its status files into the Windows widget's cache dir
# through the /mnt/<drive> mount. Linux PIDs mean nothing to the Windows widget, so
# such a hook records no process ancestry (the ➜ button falls back to the title match).

def is_wsl(environ: Mapping[str, str] | None = None, osrelease: Path = Path("/proc/sys/kernel/osrelease")) -> bool:
    """Whether this Linux runs under Windows Subsystem for Linux."""
    env = os.environ if environ is None else environ
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True
    try:
        return "microsoft" in osrelease.read_text(encoding="utf-8").lower()
    except OSError:
        return False


def is_windows_mount(path: Path | str) -> bool:
    """Whether ``path`` lives on a Windows drive mounted into WSL (``/mnt/c/…``)."""
    parts = Path(path).parts
    return len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1 and parts[2].isalpha()


def wsl_windows_profile(runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> Path | None:
    """The Windows user profile (``%USERPROFILE%``) as a WSL path, or ``None``."""
    try:
        result = runner(
            ["cmd.exe", "/d", "/c", "echo %USERPROFILE%"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10, check=False,
            cwd="/mnt/c" if os.path.isdir("/mnt/c") else None,  # cmd.exe warns on a UNC cwd
        )
        windows_path = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
        if result.returncode != 0 or not windows_path or "%" in windows_path:
            return None
        converted = runner(
            ["wslpath", "-u", windows_path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10, check=False,
        )
        path = converted.stdout.strip()
        return Path(path) if converted.returncode == 0 and path else None
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def wsl_windows_cache_dir(profile: Path) -> Path:
    """The Windows widget's default cache dir, seen from WSL."""
    return profile / "AppData" / "Local" / APP_DIR_NAME / "cache"


# ----------------------------- runtime directories -----------------------------

def default_dir_values(platform: str | None = None) -> dict[str, str]:
    """Default cache/config/data directories, as ``$HOME``-relative dotenv values.

    Linux and macOS share the XDG-style layout (common for CLI tools, and what the
    hook commands of existing installs point at). Windows uses the per-user
    ``AppData`` folders.
    """
    if (platform or PLATFORM) == WINDOWS:
        return {
            "AI_STATUS_CACHE_DIR": f"$HOME/AppData/Local/{APP_DIR_NAME}/cache",
            "AI_STATUS_CONFIG_DIR": f"$HOME/AppData/Roaming/{APP_DIR_NAME}",
            "AI_STATUS_DATA_DIR": f"$HOME/AppData/Local/{APP_DIR_NAME}/data",
        }
    return {
        "AI_STATUS_CACHE_DIR": f"$HOME/.cache/{APP_DIR_NAME}",
        "AI_STATUS_CONFIG_DIR": f"$HOME/.config/{APP_DIR_NAME}",
        "AI_STATUS_DATA_DIR": f"$HOME/.local/share/{APP_DIR_NAME}",
    }


def home_dir(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    for key in ("HOME", "USERPROFILE"):
        value = env.get(key, "").strip()
        if value:
            return Path(value)
    return Path.home()


def default_env_file(home: Path, platform: str | None = None) -> Path:
    if (platform or PLATFORM) == WINDOWS:
        return home / "AppData" / "Roaming" / APP_DIR_NAME / ".env"
    return home / ".config" / APP_DIR_NAME / ".env"


def default_bin_dir(home: Path, platform: str | None = None) -> Path:
    """Where the installer puts the scripts and ``ai_agent_status_lib``."""
    if (platform or PLATFORM) == WINDOWS:
        return home / "AppData" / "Local" / APP_DIR_NAME / "bin"
    return home / ".local" / "bin"


# ----------------------------- process ancestry -----------------------------

def _linux_parent(pid: int) -> int:
    with open(f"/proc/{pid}/status", "r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("PPid:"):
                return int(line.split()[1])
    return 0


def _ps_parent_table(runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[int, int]:
    """``pid -> ppid`` for every process, from one ``ps`` call (macOS / BSD)."""
    result = runner(
        ["ps", "-A", "-o", "pid=", "-o", "ppid="],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=2,
        check=False,
    )
    table: dict[int, int] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = int(parts[1])
    return table


def _windows_parent_table() -> dict[int, int]:
    """``pid -> ppid`` from a Toolhelp32 snapshot (Windows, via ctypes)."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return {}
    table: dict[int, int] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            table[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return table


def walk_ancestors(pid: int, parent_of: Callable[[int], int], limit: int = MAX_ANCESTORS) -> list[int]:
    """``[pid, parent, grandparent, ...]`` until init/the root or ``limit`` entries."""
    pids: list[int] = []
    seen: set[int] = set()
    while len(pids) < limit and pid > 0 and pid not in seen:
        pids.append(pid)
        seen.add(pid)
        try:
            parent = parent_of(pid)
        except (OSError, ValueError, KeyError):
            break
        if parent <= 1:
            break
        pid = parent
    return pids


def ancestor_pids(pid: int | None = None, platform: str | None = None) -> list[int]:
    """The process-ancestor chain (hook → CLI → shell → terminal), best effort.

    The widget matches these PIDs against window owners to raise the right terminal.
    """
    start = os.getpid() if pid is None else pid
    system = platform or PLATFORM
    try:
        if system == LINUX:
            return walk_ancestors(start, _linux_parent)
        table = _windows_parent_table() if system == WINDOWS else _ps_parent_table()
    except Exception:
        return [start]
    return walk_ancestors(start, lambda child: table.get(child, 0))


# ----------------------------- session key -----------------------------

def terminal_session_key(platform: str | None = None) -> str | None:
    """A key that is stable for one terminal window/tab and unique across them.

    POSIX: the session leader (``getsid``) — the terminal's shell, which survives the
    transient per-event wrapper that spawns the hook. Windows: the console window
    handle, which every process attached to one console (or one Windows Terminal
    tab / ConPTY) shares.
    """
    system = platform or PLATFORM
    try:
        if system == WINDOWS:
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            return f"con{int(hwnd)}" if hwnd else None
        sid = os.getsid(0)
        return f"sid{sid}" if sid > 0 else None
    except Exception:
        return None


# ----------------------------- opening things -----------------------------

def open_command(target: str, platform: str | None = None) -> list[str] | None:
    """The command that opens a file, folder or URL with the desktop default app."""
    system = platform or PLATFORM
    if system == MACOS:
        return ["open", target]
    if system == LINUX:
        opener = shutil.which("xdg-open") or shutil.which("gio")
        if opener is None:
            return None
        return [opener, "open", target] if opener.endswith("gio") else [opener, target]
    return None


def open_path(target: str | os.PathLike[str]) -> bool:
    """Open a file, folder or URL; returns False when nothing could handle it."""
    value = str(target)
    if PLATFORM == WINDOWS:
        try:
            os.startfile(value)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    command = open_command(value)
    if command is None:
        return False
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


# ----------------------------- sound -----------------------------

def _powershell_play_script(path: str) -> str:
    quoted = path.replace("'", "''")
    return (
        "Add-Type -AssemblyName PresentationCore; "
        "$p = New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open([Uri]'{quoted}'); $p.Play(); Start-Sleep -Seconds 4"
    )


def sound_commands(path: str, platform: str | None = None) -> list[tuple[str, list[str]]]:
    """Candidate ``(binary, argv)`` players for an MP3, in preference order."""
    system = platform or PLATFORM
    if system == MACOS:
        return [("afplay", ["afplay", path])]
    if system == WINDOWS:
        script = _powershell_play_script(path)
        return [
            (binary, [binary, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script])
            for binary in ("powershell", "pwsh")
        ]
    return [
        ("mpv", ["mpv", "--no-video", "--really-quiet", path]),
        ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]),
        ("mpg123", ["mpg123", "-q", path]),
        ("gst-play-1.0", ["gst-play-1.0", "-q", path]),
        ("paplay", ["paplay", path]),
    ]


def play_sound(path: Path, log: Callable[[str], None] = lambda _message: None) -> bool:
    """Play ``path`` with the first available player, without blocking."""
    if not path.exists():
        log(f"notification sound missing: {path}")
        return False
    for binary, command in sound_commands(str(path)):
        if not shutil.which(binary):
            continue
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **hidden_window_flags())
            log(f"notification sound played with {binary}")
            return True
        except OSError as error:
            log(f"failed to play notification with {binary}: {error}")
    log(f"no supported audio player found for {path.name}")
    return False


# ----------------------------- Qt runtime -----------------------------

# Qt 6.5+ loads its X11 (xcb) backend only when libxcb-cursor is present; it is not
# installed by default on every distribution (Debian/Ubuntu/Mint: libxcb-cursor0).
LINUX_QT_LIBRARIES = (("xcb-cursor", "libxcb-cursor0"),)


def missing_linux_qt_packages(find_library: Callable[[str], str | None] | None = None) -> list[str]:
    """Debian package names of X11 libraries Qt needs but cannot find (Linux only)."""
    if find_library is None:
        import ctypes.util

        find_library = ctypes.util.find_library
    return [package for library, package in LINUX_QT_LIBRARIES if not find_library(library)]


# ----------------------------- processes -----------------------------

def hidden_window_flags(platform: str | None = None) -> dict[str, int]:
    """``Popen`` kwargs that keep a console window from flashing up on Windows."""
    if (platform or PLATFORM) == WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def detached_flags(platform: str | None = None) -> dict[str, object]:
    """``Popen`` kwargs for a child that must outlive its parent (no console on Windows)."""
    if (platform or PLATFORM) == WINDOWS:
        # Not DETACHED_PROCESS: Windows ignores CREATE_NO_WINDOW alongside it, and a
        # console-less updater would then flash a new console for every git/pip child.
        # A hidden console is inherited by the children; the process still outlives us.
        flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
        return {"creationflags": flags, "close_fds": True}
    return {"start_new_session": True}


def gui_python(executable: str | None = None, platform: str | None = None) -> str:
    """The interpreter for GUI processes: ``pythonw.exe`` on Windows (no console)."""
    python = executable or sys.executable
    if (platform or PLATFORM) == WINDOWS:
        candidate = Path(python).with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    return python


def pid_alive(pid: int, platform: str | None = None) -> bool:
    if pid <= 0:
        return False
    if (platform or PLATFORM) == WINDOWS:
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def process_command_line(pid: int, platform: str | None = None) -> str:
    """The command line of ``pid`` (best effort, ``""`` when unknown)."""
    system = platform or PLATFORM
    try:
        if system == LINUX:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
            return raw.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
        if system == MACOS:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=2, check=False,
            )
            return result.stdout.strip()
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10, check=False,
            **hidden_window_flags(system),
        )
        return result.stdout.strip()
    except Exception:
        return ""


def powershell_argv(script: str) -> list[str]:
    """argv running ``script`` in Windows PowerShell, base64-encoded so nothing needs quoting."""
    import base64

    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded]


WINDOWS_PROCESS_QUERY = (
    "Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%ai-agent-status-%'\" | "
    "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"
)


def list_processes(platform: str | None = None,
                   runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> list[tuple[int, str]]:
    """``(pid, command line)`` of running processes (on Windows only ours, by a cheap filter).

    Best effort: an empty list when the process table cannot be read.
    """
    system = platform or PLATFORM
    processes: list[tuple[int, str]] = []
    try:
        if system == LINUX:
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    raw = (entry / "cmdline").read_bytes()
                except OSError:
                    continue
                if raw:
                    processes.append((int(entry.name), raw.rstrip(b"\0").replace(b"\0", b" ").decode("utf-8", "replace")))
            return processes
        if system == MACOS:
            command = ["ps", "-A", "-o", "pid=", "-o", "args="]
            separator = None
        else:
            command = powershell_argv(WINDOWS_PROCESS_QUERY)
            separator = "\t"
        result = runner(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=15,
                        check=False, **hidden_window_flags(system))
        for line in result.stdout.splitlines():
            pid, _sep, args = line.strip().partition(separator) if separator else _split_ps(line)
            if pid.strip().isdigit():
                processes.append((int(pid), args.strip()))
    except Exception:
        return []
    return processes


def _split_ps(line: str) -> tuple[str, str, str]:
    parts = line.strip().split(None, 1)
    return (parts[0], " ", parts[1]) if len(parts) == 2 else (line, "", "")


def terminate_pid(pid: int, platform: str | None = None) -> bool:
    if (platform or PLATFORM) == WINDOWS:
        try:
            # No /T: the widget's self-update spawns the updater as its child, and the
            # updater stops the widget through here — a tree kill would take it down too.
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                **hidden_window_flags(WINDOWS),
            )
            return result.returncode == 0
        except OSError:
            return False
    import signal

    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def quote_command(argv: Sequence[str], platform: str | None = None) -> str:
    """Join ``argv`` into one hook ``command`` string the agent CLI can run.

    POSIX paths without spaces stay bare, so commands written by earlier installs
    (``~/.local/bin/ai-agent-status-hook --agent claude``) keep matching. On Windows
    every path (anything with a separator, drive colon or space) is double-quoted and uses forward slashes, which both cmd.exe and the
    Git Bash that Claude Code runs hooks in accept.
    """
    if (platform or PLATFORM) == WINDOWS:
        parts = []
        for arg in argv:
            if any(char in arg for char in ' /\\:"'):
                parts.append('"' + arg.replace("\\", "/") + '"')
            else:
                parts.append(arg)
        return " ".join(parts)
    import shlex

    return " ".join(shlex.quote(arg) for arg in argv)


# ----------------------------- HTTPS trust store -----------------------------

# python.org's macOS Python ships its own OpenSSL with an empty trust store until the user
# runs "Install Certificates.command"; every HTTPS request then fails certificate checks.
MACOS_TRUST_KEYCHAINS = (
    "/System/Library/Keychains/SystemRootCertificates.keychain",
    "/Library/Keychains/System.keychain",  # admin-installed (e.g. corporate proxy) roots
)
PEM_END = "-----END CERTIFICATE-----"


def macos_keychain_certificates(runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> str:
    """PEM text of the macOS system root certificates, or "" when ``security`` fails."""
    chunks: list[str] = []
    for keychain in MACOS_TRUST_KEYCHAINS:
        try:
            result = runner(
                ["security", "find-certificate", "-a", "-p", keychain],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and isinstance(result.stdout, str):
            chunks.append(result.stdout)
    return "".join(chunks)


def https_context(
    platform: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> ssl.SSLContext:
    """A verifying SSL context; on macOS it falls back to the Keychain's root certificates."""
    context = ssl.create_default_context()
    if (platform or PLATFORM) != MACOS or context.cert_store_stats().get("x509_ca"):
        return context
    pem = macos_keychain_certificates(runner)
    if not pem:
        return context
    try:
        context.load_verify_locations(cadata=pem)
    except (ssl.SSLError, ValueError):
        # One certificate OpenSSL cannot parse must not discard the rest.
        for block in pem.split(PEM_END):
            if "BEGIN CERTIFICATE" in block:
                try:
                    context.load_verify_locations(cadata=block.strip() + "\n" + PEM_END + "\n")
                except (ssl.SSLError, ValueError):
                    pass
    return context


def install_https_opener(platform: str | None = None) -> None:
    """Make every ``urllib.request.urlopen`` without an explicit context use ``https_context``."""
    if (platform or PLATFORM) != MACOS:
        return
    try:
        handler = urllib.request.HTTPSHandler(context=https_context(platform))
    except (OSError, ssl.SSLError, ValueError):
        return
    urllib.request.install_opener(urllib.request.build_opener(handler))


# ----------------------------- macOS Dock -----------------------------

NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY = 1


def hide_from_macos_dock(platform: str | None = None) -> bool:
    """Run as a macOS accessory app: no Dock icon (labelled "Python"), no app menu.

    The widget windows stay out of the taskbar on every OS; on macOS a bare interpreter
    still gets a Dock tile named after Python.app. Call once the Qt application exists
    (it loads AppKit). Returns True when the policy was applied.
    """
    if (platform or PLATFORM) != MACOS:
        return False
    try:
        import ctypes
        import ctypes.util

        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        # objc_msgSend must be called through a prototype matching each message (arm64 ABI).
        send_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
            ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        )
        send_long = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(
            ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        )
        ns_application = objc.objc_getClass(b"NSApplication")
        if not ns_application:
            return False
        app = send_id(ns_application, objc.sel_registerName(b"sharedApplication"))
        if not app:
            return False
        return bool(send_long(app, objc.sel_registerName(b"setActivationPolicy:"),
                              NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY))
    except Exception:
        return False
