"""Lightweight update checking for ai-cli-status-monitor.

The widget calls :func:`check_for_update` from a short-lived background thread on
startup; the ``ai-agent-status-update`` script performs the actual git pull. This
is the one place the project reaches the network, and it is deliberately
best-effort: any failure (offline, timeout, malformed data) resolves to "no
update known" rather than raising, so it can never disrupt the widget.
"""
from __future__ import annotations

import os
import re
import urllib.request
from pathlib import Path
from typing import Optional


# GitHub "owner/repo" the update check and self-update pull from. Overridable so a
# fork or an internal mirror can be used without editing the source.
DEFAULT_REPO = "dmitrykostenkoweb/ai-status-monitor"
DEFAULT_BRANCH = "main"


def repo_slug() -> str:
    return os.environ.get("AI_STATUS_UPDATE_REPO", DEFAULT_REPO).strip() or DEFAULT_REPO


def repo_branch() -> str:
    return os.environ.get("AI_STATUS_UPDATE_BRANCH", DEFAULT_BRANCH).strip() or DEFAULT_BRANCH


def raw_version_url() -> str:
    return f"https://raw.githubusercontent.com/{repo_slug()}/{repo_branch()}/VERSION"


def parse_version(value: str) -> tuple[int, ...]:
    """Turn a version string into a comparable tuple, tolerating junk.

    ``"0.2.0"`` -> ``(0, 2, 0)``. Non-numeric or empty input -> ``()`` which
    sorts below any real version, so a garbage local version still prompts an
    update rather than suppressing it.
    """
    parts = re.findall(r"\d+", value or "")
    return tuple(int(part) for part in parts)


def _resolve_data_dir() -> Optional[Path]:
    """Locate the runtime data dir the same way the rest of the app does.

    The ``AI_STATUS_DATA_DIR`` env var is only exported by the Bash helpers; when
    the widget is launched directly (e.g. from the autostart .desktop) it is
    absent, so fall back to the canonical settings resolver, which reads the
    runtime ``.env``. Without this the version would read as ``"0"`` on login.
    """
    env = os.environ.get("AI_STATUS_DATA_DIR")
    if env:
        return Path(env).expanduser()
    try:
        from ai_agent_status_lib.env_config import load_settings

        return Path(load_settings().data_dir)
    except Exception:
        return None


def installed_version() -> str:
    """Read the installed version string, or ``"0"`` if none can be found.

    Prefers the copy the installer drops next to the runtime data, then falls
    back to the ``VERSION`` file at the repo root (running straight from a clone).
    """
    candidates = []
    data_dir = _resolve_data_dir()
    if data_dir:
        candidates.append(data_dir / "VERSION")
    # bin/ai_agent_status_lib/updates.py -> repo root is three levels up.
    candidates.append(Path(__file__).resolve().parents[2] / "VERSION")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "0"


def fetch_remote_version(timeout: float = 4.0) -> Optional[str]:
    """Fetch the latest published version string, or ``None`` on any failure."""
    try:
        request = urllib.request.Request(
            raw_version_url(),
            headers={"User-Agent": "ai-cli-status-monitor"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(64).decode("utf-8", "replace").strip()
    except Exception:
        return None


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def check_for_update(timeout: float = 4.0) -> Optional[str]:
    """Return the remote version string if it is newer than installed, else ``None``."""
    remote = fetch_remote_version(timeout=timeout)
    if not remote:
        return None
    if is_newer(remote, installed_version()):
        return remote
    return None
