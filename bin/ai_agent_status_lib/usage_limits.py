"""Best-effort account usage collection for Claude Code and Codex."""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, TypedDict


CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


class UsageSourceError(RuntimeError):
    """A provider could not return valid usage without exposing sensitive detail."""


class UsageLimit(TypedDict):
    provider: str
    window: str
    used_percent: float
    resets_at: str
    fetched_at: str
    stale: bool


class UsageSnapshot(TypedDict):
    providers: dict[str, list[UsageLimit]]
    errors: dict[str, str]


class UsageDisplayRow(TypedDict):
    provider: str
    provider_key: str
    window: str
    used_percent: float
    percent_text: str
    fraction: float
    reset_text: str
    state: str
    color_class: str


class UsageDisplayGroup(TypedDict):
    provider: str
    provider_key: str
    rows: list[UsageDisplayRow]


def _as_utc(value: Any) -> datetime | None:
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, bool):
            return None
        elif isinstance(value, (int, float)):
            parsed = datetime.fromtimestamp(value, tz=timezone.utc)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return None
    except (OSError, OverflowError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: Any) -> str | None:
    parsed = _as_utc(value)
    return parsed.isoformat(timespec="seconds") if parsed is not None else None


def _normalized_limit(
    provider: str,
    window: str,
    used_percent: Any,
    resets_at: Any,
    fetched_at: datetime,
) -> UsageLimit | None:
    if isinstance(used_percent, bool) or not isinstance(used_percent, (int, float)):
        return None
    percent = float(used_percent)
    if not 0.0 <= percent <= 100.0:
        return None
    reset_iso = _iso_utc(resets_at)
    fetched_iso = _iso_utc(fetched_at)
    if reset_iso is None or fetched_iso is None:
        return None
    return {
        "provider": provider,
        "window": window,
        "used_percent": percent,
        "resets_at": reset_iso,
        "fetched_at": fetched_iso,
        "stale": False,
    }


def parse_claude_usage(payload: Any, *, fetched_at: datetime | None = None) -> list[UsageLimit]:
    if not isinstance(payload, dict):
        return []
    fetched = fetched_at or datetime.now(timezone.utc)
    limits: list[UsageLimit] = []
    for source_key, label in (("five_hour", "5h"), ("seven_day", "Weekly")):
        source = payload.get(source_key)
        if not isinstance(source, dict):
            continue
        normalized = _normalized_limit(
            "claude",
            label,
            source.get("utilization"),
            source.get("resets_at"),
            fetched,
        )
        if normalized is not None:
            limits.append(normalized)
    return limits


def parse_codex_rate_limits(payload: Any, *, fetched_at: datetime | None = None) -> list[UsageLimit]:
    if not isinstance(payload, dict):
        return []
    fetched = fetched_at or datetime.now(timezone.utc)
    for key in ("primary", "secondary", "individual_limit"):
        source = payload.get(key)
        if not isinstance(source, dict) or source.get("window_minutes") != 10080:
            continue
        normalized = _normalized_limit(
            "codex",
            "Weekly",
            source.get("used_percent"),
            source.get("resets_at"),
            fetched,
        )
        return [normalized] if normalized is not None else []
    return []


def codex_home(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = env.get("CODEX_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def claude_credentials_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = env.get("CLAUDE_CONFIG_DIR", "").strip()
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / ".credentials.json"


def _claude_access_token(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    oauth = payload.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return None
    token = oauth.get("accessToken")
    return token.strip() if isinstance(token, str) and token.strip() else None


def collect_claude_usage(
    credentials: Path | None = None,
    *,
    fetched_at: datetime | None = None,
    timeout: float = 4.0,
    opener: Any = urllib.request.urlopen,
) -> list[UsageLimit]:
    token = _claude_access_token(credentials or claude_credentials_path())
    if token is None:
        raise UsageSourceError("Claude usage unavailable")

    request = urllib.request.Request(
        CLAUDE_USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "User-Agent": "ai-cli-status-monitor",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read(65_536).decode("utf-8"))
        limits = parse_claude_usage(payload, fetched_at=fetched_at)
        if not limits:
            raise UsageSourceError("Claude usage unavailable")
        return limits
    except UsageSourceError:
        raise
    except Exception:
        raise UsageSourceError("Claude usage unavailable") from None


def _tail_lines(path: Path, max_lines: int, max_bytes: int = 262_144) -> list[str]:
    if max_lines <= 0 or max_bytes <= 0:
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            chunks: list[bytes] = []
            consumed = 0
            newline_count = 0
            while position > 0 and consumed < max_bytes and newline_count <= max_lines:
                size = min(8192, position, max_bytes - consumed)
                position -= size
                handle.seek(position)
                chunk = handle.read(size)
                chunks.append(chunk)
                consumed += len(chunk)
                newline_count += chunk.count(b"\n")
    except OSError:
        return []
    raw = b"".join(reversed(chunks)).decode("utf-8", "replace")
    return raw.splitlines()[-max_lines:]


def collect_codex_usage(
    home: Path | None = None,
    *,
    fetched_at: datetime | None = None,
    max_files: int = 12,
    max_lines: int = 300,
) -> list[UsageLimit]:
    sessions = (home or codex_home()) / "sessions"
    try:
        candidates = sorted(
            sessions.glob("**/*.jsonl"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )[: max(0, max_files)]
    except OSError:
        return []

    for path in candidates:
        for raw_line in reversed(_tail_lines(path, max_lines)):
            try:
                event = json.loads(raw_line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(event, dict) or event.get("type") != "event_msg":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            limits = parse_codex_rate_limits(payload.get("rate_limits"), fetched_at=fetched_at)
            if limits:
                return limits
    return []


def _sanitize_limit(value: Any, expected_provider: str) -> UsageLimit | None:
    if not isinstance(value, dict):
        return None
    provider = value.get("provider")
    window = value.get("window")
    fetched = _as_utc(value.get("fetched_at"))
    if provider != expected_provider or not isinstance(window, str) or fetched is None:
        return None
    return _normalized_limit(
        provider,
        window,
        value.get("used_percent"),
        value.get("resets_at"),
        fetched,
    )


def _sanitized_providers(providers: Any) -> dict[str, list[UsageLimit]]:
    result: dict[str, list[UsageLimit]] = {"claude": [], "codex": []}
    if not isinstance(providers, dict):
        return result
    for provider in result:
        values = providers.get(provider)
        if not isinstance(values, list):
            continue
        result[provider] = [
            normalized
            for value in values
            if (normalized := _sanitize_limit(value, provider)) is not None
        ]
    return result


def write_usage_cache(
    path: Path,
    providers: Any,
    *,
    replacer: Any = os.replace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "providers": _sanitized_providers(providers)}
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        replacer(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_usage_cache(path: Path, *, now: datetime | None = None) -> dict[str, list[UsageLimit]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"claude": [], "codex": []}
    providers = _sanitized_providers(payload.get("providers") if isinstance(payload, dict) else None)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for provider, limits in providers.items():
        unexpired: list[UsageLimit] = []
        for limit in limits:
            reset = _as_utc(limit["resets_at"])
            if reset is None or reset <= current:
                continue
            limit["stale"] = True
            unexpired.append(limit)
        providers[provider] = unexpired
    return providers


def refresh_usage(
    cache_path: Path,
    *,
    now: datetime | None = None,
    provider_keys: tuple[str, ...] = ("claude", "codex"),
    claude_collector: Callable[[], list[UsageLimit]] | None = None,
    codex_collector: Callable[[], list[UsageLimit]] | None = None,
    persist: bool = True,
) -> UsageSnapshot:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    providers = load_usage_cache(cache_path, now=current)
    collectors: dict[str, Callable[[], list[UsageLimit]]] = {
        "claude": claude_collector or (lambda: collect_claude_usage(fetched_at=current)),
        "codex": codex_collector or (lambda: collect_codex_usage(fetched_at=current)),
    }
    errors: dict[str, str] = {}

    selected_providers = tuple(dict.fromkeys(
        provider for provider in provider_keys if provider in collectors
    ))
    for provider in selected_providers:
        collector = collectors[provider]
        try:
            collected = collector()
        except Exception:
            collected = []
        normalized = _sanitized_providers({provider: collected})[provider]
        if normalized:
            providers[provider] = normalized
        else:
            errors[provider] = "unavailable"

    if persist:
        try:
            write_usage_cache(cache_path, providers)
        except OSError:
            pass
    return {"providers": providers, "errors": errors}


def _percent_text(value: float) -> str:
    rounded = round(value)
    return f"{rounded:.0f}%" if abs(value - rounded) < 0.05 else f"{value:.1f}%"


def usage_color_class(used_percent: object) -> str:
    if isinstance(used_percent, bool) or not isinstance(used_percent, (int, float)):
        return ""
    if float(used_percent) >= 85.0:
        return "usage-red"
    if float(used_percent) >= 60.0:
        return "usage-orange"
    return "usage-green"


def build_usage_rows(
    snapshot: Any,
    *,
    now: datetime | None = None,
    local_timezone: Any = None,
) -> list[UsageDisplayRow]:
    providers = snapshot.get("providers") if isinstance(snapshot, dict) else None
    providers = providers if isinstance(providers, dict) else {}
    current = now or datetime.now(timezone.utc)
    zone = local_timezone or datetime.now().astimezone().tzinfo or timezone.utc
    current_local = current.astimezone(zone)
    rows: list[UsageDisplayRow] = []

    for provider_key, provider_name, windows in (
        ("claude", "Claude", ("5h", "Weekly")),
        ("codex", "Codex", ("Weekly",)),
    ):
        raw_limits = providers.get(provider_key)
        limits = raw_limits if isinstance(raw_limits, list) else []
        by_window = {
            str(limit.get("window")): limit
            for limit in limits
            if isinstance(limit, dict) and limit.get("provider") == provider_key
        }
        provider_rows = 0
        for window in windows:
            limit = by_window.get(window)
            if not isinstance(limit, dict):
                continue
            percent = limit.get("used_percent")
            reset = _as_utc(limit.get("resets_at"))
            if isinstance(percent, bool) or not isinstance(percent, (int, float)) or reset is None:
                continue
            local_reset = reset.astimezone(zone)
            reset_text = (
                f"resets {local_reset:%H:%M}"
                if local_reset.date() == current_local.date()
                else f"resets {local_reset:%a %H:%M}"
            )
            value = float(percent)
            rows.append(
                {
                    "provider": provider_name,
                    "provider_key": provider_key,
                    "window": window,
                    "used_percent": value,
                    "percent_text": _percent_text(value),
                    "fraction": max(0.0, min(1.0, value / 100.0)),
                    "reset_text": reset_text,
                    "state": "stale" if limit.get("stale") is True else "current",
                    "color_class": usage_color_class(value),
                }
            )
            provider_rows += 1
        if provider_rows == 0:
            rows.append(
                {
                    "provider": provider_name,
                    "provider_key": provider_key,
                    "window": "",
                    "used_percent": 0.0,
                    "percent_text": "Unavailable",
                    "fraction": 0.0,
                    "reset_text": "",
                    "state": "unavailable",
                    "color_class": "",
                }
            )
    return rows


def build_usage_groups(
    snapshot: Any,
    *,
    now: datetime | None = None,
    local_timezone: Any = None,
) -> list[UsageDisplayGroup]:
    rows = build_usage_rows(snapshot, now=now, local_timezone=local_timezone)
    grouped: dict[str, list[UsageDisplayRow]] = {"claude": [], "codex": []}
    for row in rows:
        provider_key = row["provider_key"]
        if provider_key in grouped:
            grouped[provider_key].append(row)
    return [
        {"provider": provider, "provider_key": provider_key, "rows": grouped[provider_key]}
        for provider_key, provider in (("claude", "Claude"), ("codex", "Codex"))
    ]


def demo_usage_states(now: datetime | None = None) -> list[dict[str, Any]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    def limit(provider: str, window: str, used: float, reset_delta: timedelta, stale: bool = False) -> UsageLimit:
        normalized = _normalized_limit(provider, window, used, current + reset_delta, current)
        if normalized is None:
            raise AssertionError("invalid built-in demo usage limit")
        normalized["stale"] = stale
        return normalized

    def snapshot(*, stale: bool = False) -> UsageSnapshot:
        return {
            "providers": {
                "claude": [
                    limit("claude", "5h", 76.0, timedelta(hours=2), stale),
                    limit("claude", "Weekly", 43.0, timedelta(days=3), stale),
                ],
                "codex": [limit("codex", "Weekly", 5.0, timedelta(days=6), stale)],
            },
            "errors": {},
        }

    return [
        {"name": "current", "snapshot": snapshot(), "refreshing": False},
        {"name": "refreshing", "snapshot": snapshot(), "refreshing": True},
        {"name": "stale", "snapshot": snapshot(stale=True), "refreshing": False},
        {
            "name": "partial",
            "snapshot": {
                "providers": {"claude": [], "codex": [limit("codex", "Weekly", 5.0, timedelta(days=6))]},
                "errors": {"claude": "unavailable"},
            },
            "refreshing": False,
        },
        {
            "name": "unavailable",
            "snapshot": {
                "providers": {"claude": [], "codex": []},
                "errors": {"claude": "unavailable", "codex": "unavailable"},
            },
            "refreshing": False,
        },
    ]
