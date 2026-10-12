"""Make the widget a findable Windows app: Start menu + desktop shortcuts and an "Installed apps" entry.

The widget itself is a tool window with no taskbar button, so without these the only way to
open it again (after closing it, or with "Start at login" off) was a console. The installer
calls :func:`install`; ``ai-agent-status-uninstall`` (the entry's Uninstall button) calls
:func:`uninstall`.

* Shortcuts ``AI Status Monitor.lnk`` in the Start menu's Programs folder and on the desktop
  start ``pythonw.exe <bin>\\ai-agent-status-widget-start`` (no console window) with the
  bundled ``.ico``. They are written through PowerShell's ``WScript.Shell`` COM object, so no
  extra Python package is needed; the user can pin either one to the taskbar.
* ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ai-cli-status-monitor`` lists
  the app under Settings → Apps → Installed apps (per user, no admin rights).

Every function is best-effort and never raises: a missing PowerShell or registry only costs
the shortcut, not the install.
"""

from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path
from typing import Callable, Mapping

from ai_agent_status_lib import platform_support

APP_TITLE = "AI Status Monitor"
SHORTCUT_NAME = f"{APP_TITLE}.lnk"
ICON_NAME = "ai-cli-status-widget.ico"
PUBLISHER = "dmitrykostenkoweb"
HOMEPAGE = "https://github.com/dmitrykostenkoweb/ai-status-monitor"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ai-cli-status-monitor"
START_SCRIPT = "ai-agent-status-widget-start"
UNINSTALL_SCRIPT = "ai-agent-status-uninstall"

Runner = Callable[..., subprocess.CompletedProcess]

# Values travel in environment variables, so no path ever needs PowerShell quoting.
_FOLDERS = "$folders = @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))\n"
CREATE_SCRIPT = _FOLDERS + r"""
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in $folders) {
    if (-not $folder) { continue }
    $path = Join-Path $folder $env:AI_STATUS_LNK_NAME
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $env:AI_STATUS_LNK_TARGET
    $link.Arguments = $env:AI_STATUS_LNK_ARGS
    $link.WorkingDirectory = $env:AI_STATUS_LNK_DIR
    $link.IconLocation = $env:AI_STATUS_LNK_ICON
    $link.Description = $env:AI_STATUS_LNK_DESC
    $link.Save()
    Write-Output $path
}
"""
REMOVE_SCRIPT = _FOLDERS + r"""
foreach ($folder in $folders) {
    if (-not $folder) { continue }
    $path = Join-Path $folder $env:AI_STATUS_LNK_NAME
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force; Write-Output $path }
}
"""


def _powershell(script: str, values: Mapping[str, str], runner: Runner) -> list[str]:
    """Run ``script`` with ``values`` in its environment; the non-empty output lines."""
    env = dict(os.environ)
    env.update(values)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")  # no command-line quoting at all
    try:
        result = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60, check=False, env=env,
            **platform_support.hidden_window_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def shortcut_values(bin_dir: Path, icon: Path, python: str) -> dict[str, str]:
    """What each shortcut runs: ``pythonw.exe "<bin>\\ai-agent-status-widget-start"``."""
    return {
        "AI_STATUS_LNK_NAME": SHORTCUT_NAME,
        "AI_STATUS_LNK_TARGET": platform_support.gui_python(python, platform_support.WINDOWS),
        "AI_STATUS_LNK_ARGS": f'"{bin_dir / START_SCRIPT}"',
        "AI_STATUS_LNK_DIR": str(bin_dir),
        "AI_STATUS_LNK_ICON": f"{icon},0",
        "AI_STATUS_LNK_DESC": "Floating status widget for Claude Code and Codex CLI",
    }


def uninstall_values(bin_dir: Path, data_dir: Path, icon: Path, python: str, version: str) -> dict[str, object]:
    """The ``Uninstall\\ai-cli-status-monitor`` registry values (str → REG_SZ, int → REG_DWORD)."""
    # A console interpreter, so the uninstaller can show what it removes and ask first.
    console = Path(python)
    if console.name.lower() == "pythonw.exe":
        console = console.with_name("python.exe")
    command = f'"{console}" "{bin_dir / UNINSTALL_SCRIPT}"'
    return {
        "DisplayName": APP_TITLE,
        "DisplayVersion": version,
        "Publisher": PUBLISHER,
        "DisplayIcon": str(icon),
        "InstallLocation": str(data_dir),
        "URLInfoAbout": HOMEPAGE,
        "UninstallString": command,
        "QuietUninstallString": f"{command} --yes",
        "NoModify": 1,
        "NoRepair": 1,
    }


def _register(values: Mapping[str, object]) -> bool:
    try:
        import winreg  # type: ignore[import-not-found]

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            for name, value in values.items():
                if isinstance(value, int):
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
        return True
    except Exception:
        return False


def _unregister() -> bool:
    try:
        import winreg  # type: ignore[import-not-found]

        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        return True
    except Exception:
        return False


def install(bin_dir: Path, data_dir: Path, python: str, version: str, runner: Runner = subprocess.run) -> list[str]:
    """Create the shortcuts and the Installed-apps entry; returns notes for the installer's summary."""
    icon = data_dir / ICON_NAME
    notes: list[str] = []
    created = _powershell(CREATE_SCRIPT, shortcut_values(bin_dir, icon, python), runner)
    if created:
        notes.append("Shortcuts (Start menu and desktop; right-click → Pin to taskbar):\n"
                     + "\n".join(f"  {path}" for path in created))
    else:
        notes.append("⚠️  Could not create the Start menu shortcut (PowerShell unavailable?). "
                     f"Start the widget with {bin_dir / (START_SCRIPT + '.cmd')}")
    if _register(uninstall_values(bin_dir, data_dir, icon, python, version)):
        notes.append(f"Listed in Settings → Apps → Installed apps as \"{APP_TITLE}\".")
    return notes


def uninstall(runner: Runner = subprocess.run) -> list[str]:
    """Remove the shortcuts and the Installed-apps entry; returns what was removed."""
    removed = _powershell(REMOVE_SCRIPT, {"AI_STATUS_LNK_NAME": SHORTCUT_NAME}, runner)
    if _unregister():
        removed.append(f"HKCU\\{UNINSTALL_KEY}")
    return removed
