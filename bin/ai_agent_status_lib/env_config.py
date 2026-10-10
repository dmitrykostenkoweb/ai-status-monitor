"""Dependency-free environment configuration for ai-cli-status-monitor."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from ai_agent_status_lib import platform_support


DEFAULT_VALUES = {
    "AI_STATUS_CACHE_DIR": "$HOME/.cache/ai-cli-status-monitor",
    "AI_STATUS_CONFIG_DIR": "$HOME/.config/ai-cli-status-monitor",
    "AI_STATUS_DATA_DIR": "$HOME/.local/share/ai-cli-status-monitor",
    "AI_STATUS_TITLE": "AI Agents Status",
    "AI_STATUS_CARD_WIDTH": "344",
    "AI_STATUS_MAX_ROWS": "5",
    "AI_STATUS_SOUND_ENABLED": "true",
    "AI_STATUS_STALE_AFTER_SECONDS": "180",
    "AI_STATUS_HIDE_DONE_AFTER_SECONDS": "180",
    "AI_STATUS_IDLE_AFTER_SECONDS": "600",
    "AI_STATUS_HIDE_STALE_AFTER_SECONDS": "900",
    "AI_STATUS_THEME": "dark",
    "AI_STATUS_AGENTS": "claude,codex",
    "AI_STATUS_SERIOUS_MODE": "false",
    "AI_STATUS_SESSION_WINDOWS": "true",
    "AI_STATUS_STICKER_ROTATE_SECONDS": "120",
    "AI_STATUS_KLIPY_API_KEY": "",
}

# Keys whose value may legitimately be empty (an unset optional credential).
OPTIONAL_KEYS = frozenset({"AI_STATUS_KLIPY_API_KEY"})

SUPPORTED_AGENTS = ("claude", "codex")

KNOWN_KEYS = frozenset(DEFAULT_VALUES)


def platform_default_values(platform: str | None = None) -> dict[str, str]:
    """``DEFAULT_VALUES`` with the runtime directories of the given/current OS.

    ``DEFAULT_VALUES`` (and ``.env.default``) carry the Linux/macOS layout; Windows
    swaps in its ``AppData`` folders.
    """
    return {**DEFAULT_VALUES, **platform_support.default_dir_values(platform)}


LEGACY_KEYS = {
    "AI_STATUS_SOUND_ENABLED": "sound_enabled",
    "AI_STATUS_STALE_AFTER_SECONDS": "stale_after_seconds",
    "AI_STATUS_HIDE_DONE_AFTER_SECONDS": "hide_done_after_seconds",
    "AI_STATUS_IDLE_AFTER_SECONDS": "idle_after_seconds",
    "AI_STATUS_HIDE_STALE_AFTER_SECONDS": "hide_stale_after_seconds",
    "AI_STATUS_THEME": "theme",
}

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
AGENT_SEPARATOR = re.compile(r"[\s,]+")
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
Diagnostic = Callable[[str], None]


@dataclass(frozen=True)
class Settings:
    env_file: Path
    cache_dir: Path
    config_dir: Path
    data_dir: Path
    title: str
    card_width: int
    max_rows: int
    sound_enabled: bool
    stale_after_seconds: int
    hide_done_after_seconds: int
    idle_after_seconds: int
    hide_stale_after_seconds: int
    theme: str
    agents: tuple[str, ...] = SUPPORTED_AGENTS
    serious_mode: bool = False
    session_windows: bool = True
    sticker_rotate_seconds: int = 120
    klipy_api_key: str = ""

    @property
    def widget_config(self) -> dict[str, object]:
        return {
            "sound_enabled": self.sound_enabled,
            "stale_after_seconds": self.stale_after_seconds,
            "hide_done_after_seconds": self.hide_done_after_seconds,
            "idle_after_seconds": self.idle_after_seconds,
            "hide_stale_after_seconds": self.hide_stale_after_seconds,
            "theme": self.theme,
        }

    def as_env(self) -> dict[str, str]:
        return {
            "AI_STATUS_CACHE_DIR": str(self.cache_dir),
            "AI_STATUS_CONFIG_DIR": str(self.config_dir),
            "AI_STATUS_DATA_DIR": str(self.data_dir),
            "AI_STATUS_TITLE": self.title,
            "AI_STATUS_CARD_WIDTH": str(self.card_width),
            "AI_STATUS_MAX_ROWS": str(self.max_rows),
            "AI_STATUS_SOUND_ENABLED": "true" if self.sound_enabled else "false",
            "AI_STATUS_STALE_AFTER_SECONDS": str(self.stale_after_seconds),
            "AI_STATUS_HIDE_DONE_AFTER_SECONDS": str(self.hide_done_after_seconds),
            "AI_STATUS_IDLE_AFTER_SECONDS": str(self.idle_after_seconds),
            "AI_STATUS_HIDE_STALE_AFTER_SECONDS": str(self.hide_stale_after_seconds),
            "AI_STATUS_THEME": self.theme,
            "AI_STATUS_AGENTS": format_agents(self.agents),
            "AI_STATUS_SERIOUS_MODE": "true" if self.serious_mode else "false",
            "AI_STATUS_SESSION_WINDOWS": "true" if self.session_windows else "false",
            "AI_STATUS_STICKER_ROTATE_SECONDS": str(self.sticker_rotate_seconds),
            "AI_STATUS_KLIPY_API_KEY": self.klipy_api_key,
        }


def _noop_diagnostic(_message: str) -> None:
    pass


def _unquote(value: str) -> str | None:
    value = value.strip()
    if not value:
        return ""
    if value[0] not in {"'", '"'}:
        return value
    if len(value) < 2 or value[-1] != value[0]:
        return None
    return value[1:-1]


def parse_dotenv(path: Path, diagnostic: Diagnostic | None = None) -> dict[str, str]:
    """Parse a restricted dotenv subset as data, never as executable shell."""
    warn = diagnostic or _noop_diagnostic
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    except OSError as error:
        warn(f"cannot read environment file {path}: {error}")
        return {}

    values: dict[str, str] = {}
    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ASSIGNMENT.match(line)
        if not match:
            warn(f"ignored malformed dotenv line {number} in {path}")
            continue
        key, raw_value = match.groups()
        if key not in KNOWN_KEYS:
            continue
        value = _unquote(raw_value)
        if value is None:
            warn(f"ignored unclosed quote for {key} in {path}")
            continue
        values[key] = value
    return values


def _expand_path(value: str, home: Path) -> Path:
    expanded = value.replace("${HOME}", str(home)).replace("$HOME", str(home))
    if expanded == "~":
        expanded = str(home)
    elif expanded.startswith("~/"):
        expanded = str(home / expanded[2:])
    return Path(expanded)


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in TRUE_VALUES:
            return True
        if lowered in FALSE_VALUES:
            return False
    return None


def _parse_int(value: object, minimum: int) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= minimum else None


def parse_agents(value: object) -> tuple[str, ...] | None:
    """Parse AI_STATUS_AGENTS: a comma/space list drawn from SUPPORTED_AGENTS (or "all")."""
    if not isinstance(value, str):
        return None
    tokens = {token for token in AGENT_SEPARATOR.split(value.strip().lower()) if token}
    if tokens == {"all"} or tokens == {"both"}:
        return SUPPORTED_AGENTS
    if not tokens or not tokens <= set(SUPPORTED_AGENTS):
        return None
    return tuple(agent for agent in SUPPORTED_AGENTS if agent in tokens)


def format_agents(agents: tuple[str, ...]) -> str:
    return ",".join(agents)


def _legacy_widget_config(config_dir: Path, diagnostic: Diagnostic) -> dict[str, object]:
    path = config_dir / "widget.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as error:
        diagnostic(f"cannot read legacy widget config {path}: {error}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _serialize_value(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@+,-]+", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def serialize_env(values: Mapping[str, str]) -> str:
    lines = ["# ai-cli-status-monitor runtime configuration"]
    lines.extend(f"{key}={_serialize_value(values[key])}" for key in DEFAULT_VALUES)
    return "\n".join(lines) + "\n"


def write_env_value(path: Path, key: str, value: str) -> None:
    """Set one known key in a runtime dotenv file, keeping every other line as written.

    Replaces the last assignment of ``key`` (the one the loaders honour) or appends
    one, then writes atomically with mode 0600 like the installer does.
    """
    if key not in KNOWN_KEYS:
        raise ValueError(f"unknown configuration key {key}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = ["# ai-cli-status-monitor runtime configuration"]
    assignment = f"{key}={_serialize_value(value)}"
    indexes = [
        index for index, line in enumerate(lines)
        if (match := ASSIGNMENT.match(line.strip())) and match.group(1) == key
    ]
    if indexes:
        lines[indexes[-1]] = assignment
    else:
        lines.append(assignment)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = None,
    dotenv_values: Mapping[str, str] | None = None,
    legacy: Mapping[str, object] | None = None,
    diagnostic: Diagnostic | None = None,
) -> Settings:
    env = dict(os.environ if environ is None else environ)
    warn = diagnostic or _noop_diagnostic
    home = platform_support.home_dir(env)
    defaults = platform_default_values()
    selected_env = env_path
    if selected_env is None:
        selected_raw = env.get("AI_STATUS_ENV_FILE", "").strip()
        selected_env = _expand_path(selected_raw, home) if selected_raw else platform_support.default_env_file(home)
    file_values = dict(dotenv_values) if dotenv_values is not None else parse_dotenv(selected_env, warn)

    def candidates(key: str, legacy_values: Mapping[str, object]) -> list[tuple[str, object]]:
        result: list[tuple[str, object]] = []
        if key in env:
            result.append(("process environment", env[key]))
        if key in file_values:
            result.append((str(selected_env), file_values[key]))
        legacy_key = LEGACY_KEYS.get(key)
        if legacy_key and legacy_key in legacy_values:
            result.append(("widget.json", legacy_values[legacy_key]))
        result.append(("built-in default", defaults[key]))
        return result

    def resolve_path(key: str) -> Path:
        for source, value in candidates(key, {}):
            if isinstance(value, str) and value.strip():
                return _expand_path(value.strip(), home)
            warn(f"invalid {key} from {source}; using next configuration source")
        raise AssertionError(f"missing valid default for {key}")

    config_dir = resolve_path("AI_STATUS_CONFIG_DIR")
    legacy_values = dict(legacy) if legacy is not None else _legacy_widget_config(config_dir, warn)

    def resolve_string(key: str) -> str:
        for source, value in candidates(key, legacy_values):
            if isinstance(value, str) and value.strip():
                return value.strip()
            warn(f"invalid {key} from {source}; using next configuration source")
        raise AssertionError(f"missing valid default for {key}")

    def resolve_int(key: str, minimum: int) -> int:
        for source, value in candidates(key, legacy_values):
            parsed = _parse_int(value, minimum)
            if parsed is not None:
                return parsed
            warn(f"invalid {key} from {source}; using next configuration source")
        raise AssertionError(f"missing valid default for {key}")

    def resolve_bool(key: str) -> bool:
        for source, value in candidates(key, legacy_values):
            parsed = _parse_bool(value)
            if parsed is not None:
                return parsed
            warn(f"invalid {key} from {source}; using next configuration source")
        raise AssertionError(f"missing valid default for {key}")

    def resolve_optional_string(key: str) -> str:
        for source, value in candidates(key, legacy_values):
            if isinstance(value, str) and "\n" not in value:
                return value.strip()
            warn(f"invalid {key} from {source}; using next configuration source")
        raise AssertionError(f"missing valid default for {key}")

    def resolve_agents(key: str) -> tuple[str, ...]:
        for source, value in candidates(key, legacy_values):
            parsed = parse_agents(value)
            if parsed is not None:
                return parsed
            warn(f"invalid {key} from {source}; using next configuration source")
        raise AssertionError(f"missing valid default for {key}")

    return Settings(
        env_file=selected_env,
        cache_dir=resolve_path("AI_STATUS_CACHE_DIR"),
        config_dir=config_dir,
        data_dir=resolve_path("AI_STATUS_DATA_DIR"),
        title=resolve_string("AI_STATUS_TITLE"),
        card_width=resolve_int("AI_STATUS_CARD_WIDTH", 1),
        max_rows=resolve_int("AI_STATUS_MAX_ROWS", 1),
        sound_enabled=resolve_bool("AI_STATUS_SOUND_ENABLED"),
        stale_after_seconds=resolve_int("AI_STATUS_STALE_AFTER_SECONDS", 0),
        hide_done_after_seconds=resolve_int("AI_STATUS_HIDE_DONE_AFTER_SECONDS", 0),
        idle_after_seconds=resolve_int("AI_STATUS_IDLE_AFTER_SECONDS", 0),
        hide_stale_after_seconds=resolve_int("AI_STATUS_HIDE_STALE_AFTER_SECONDS", 0),
        theme=resolve_string("AI_STATUS_THEME"),
        agents=resolve_agents("AI_STATUS_AGENTS"),
        serious_mode=resolve_bool("AI_STATUS_SERIOUS_MODE"),
        session_windows=resolve_bool("AI_STATUS_SESSION_WINDOWS"),
        sticker_rotate_seconds=resolve_int("AI_STATUS_STICKER_ROTATE_SECONDS", 0),
        klipy_api_key=resolve_optional_string("AI_STATUS_KLIPY_API_KEY"),
    )
