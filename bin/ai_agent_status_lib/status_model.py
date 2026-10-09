from __future__ import annotations

import json
import os
import re
import shlex
import urllib.parse
from typing import Any, Literal, TypedDict


StatusKind = Literal[
    "thinking",
    "reading",
    "coding",
    "command",
    "analyzing",
    "waiting",
    "error",
    "done",
    "idle",
    "stale",
    "neutral",
]

STATUS_KINDS: tuple[StatusKind, ...] = (
    "thinking",
    "reading",
    "coding",
    "command",
    "analyzing",
    "waiting",
    "error",
    "done",
    "idle",
    "stale",
    "neutral",
)
IN_PROGRESS_KINDS: frozenset[StatusKind] = frozenset(("thinking", "reading", "coding", "command", "analyzing"))
INACTIVE_KINDS: frozenset[StatusKind] = frozenset(("done", "idle", "stale"))


class StatusSemantic(TypedDict):
    kind: StatusKind
    status: str


def lower_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    return json.dumps(value, ensure_ascii=False, default=str).lower()


def contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def normalize_kind(value: Any, fallback_status: str = "") -> StatusKind:
    if isinstance(value, str) and value in STATUS_KINDS:
        return value  # type: ignore[return-value]
    return classify_status_text(fallback_status)


def classify_status_text(status: str) -> StatusKind:
    """Fallback classifier for status records without an explicit `kind`.

    Recognizes both the current English display strings and the legacy Polish
    ones, so old cache files written before the translation still classify.
    """
    text = status.lower()
    if any(word in text for word in ("not running", "nie uruchomiony")):
        return "idle"
    if any(word in text for word in ("czeka", "zgod", "waiting", "permission", "approval")):
        return "waiting"
    if any(word in text for word in ("błąd", "error", "failure", "malformed")):
        return "error"
    if "myśl" in text or "thinking" in text:
        return "thinking"
    if "czyta" in text or "reading" in text:
        return "reading"
    if "koduje" in text or "coding" in text:
        return "coding"
    if "wykon" in text or "komend" in text or "command" in text:
        return "command"
    if "analiz" in text or "analyz" in text:
        return "analyzing"
    if "kończył" in text or "done" in text or "finished" in text:
        return "done"
    if "brak nowych" in text or "no new events" in text:
        return "stale"
    if "idle" in text or "bezczynny" in text:
        return "idle"
    return "neutral"


def payload_search_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("notification", "message", "content", "reason", "title", "body"):
        if key in payload:
            parts.append(lower_text(payload[key]))
    return " ".join(parts)


def claude_semantic(event: str, tool: str, payload: dict[str, Any]) -> StatusSemantic:
    event_l = event.lower()
    tool_l = tool.lower()
    agent = "Claude"

    if event_l == "userpromptsubmit":
        return {"kind": "thinking", "status": f"{agent}: thinking"}
    if event_l == "pretooluse":
        if contains_any(tool_l, ("askuserquestion", "ask_user", "question", "input")):
            return {"kind": "waiting", "status": f"{agent}: waiting for you"}
        if contains_any(tool_l, ("edit", "write", "multiedit", "notebookedit", "todowrite")):
            return {"kind": "coding", "status": f"{agent}: coding"}
        if contains_any(tool_l, ("bash", "shell", "command")):
            return {"kind": "command", "status": f"{agent}: running command"}
        if contains_any(tool_l, ("read", "grep", "glob", "ls", "search", "webfetch", "websearch")):
            return {"kind": "reading", "status": f"{agent}: reading code"}
        return {"kind": "neutral", "status": f"{agent}: working"}
    if event_l == "posttooluse":
        return {"kind": "analyzing", "status": f"{agent}: analyzing"}
    if event_l == "notification":
        text = payload_search_text(payload)
        if contains_any(text, ("permission", "approval", "approve", "allow", "confirm", "trust", "zgod")):
            return {"kind": "waiting", "status": f"{agent}: waiting for approval"}
        if contains_any(text, ("idle", "input", "response", "user", "waiting", "czeka")):
            return {"kind": "waiting", "status": f"{agent}: waiting for you"}
    if event_l == "stop":
        return {"kind": "done", "status": f"{agent}: done"}
    if event_l == "stopfailure":
        return {"kind": "error", "status": f"{agent}: error"}
    if event_l in ("malformed_json", "unexpected_payload"):
        return {"kind": "error", "status": f"{agent}: {event}"}
    return {"kind": "neutral", "status": f"{agent}: {event}"}


def codex_semantic(event: str, tool: str, payload: dict[str, Any]) -> StatusSemantic:
    event_l = event.lower()
    tool_l = tool.lower()
    agent = "Codex"

    if event_l == "userpromptsubmit":
        return {"kind": "thinking", "status": f"{agent}: thinking"}
    if event_l == "pretooluse":
        if contains_any(tool_l, ("shell", "bash", "exec", "command", "terminal")):
            return {"kind": "command", "status": f"{agent}: running command"}
        if contains_any(tool_l, ("apply_patch", "patch", "edit", "write")):
            return {"kind": "coding", "status": f"{agent}: coding"}
        if contains_any(tool_l, ("read", "search", "rg", "grep", "find", "open", "cat", "sed", "ls")):
            return {"kind": "reading", "status": f"{agent}: reading code"}
    if event_l == "permissionrequest":
        return {"kind": "waiting", "status": f"{agent}: waiting for approval"}
    if event_l == "posttooluse":
        return {"kind": "analyzing", "status": f"{agent}: analyzing"}
    if event_l == "stop":
        return {"kind": "done", "status": f"{agent}: done"}
    if event_l == "subagentstop":
        return {"kind": "done", "status": "Codex subagent: done"}
    if event_l in ("stopfailure", "malformed_json", "unexpected_payload"):
        return {"kind": "error", "status": f"{agent}: {event}"}
    return {"kind": "neutral", "status": f"{agent}: {event}"}


def agent_semantic(agent: str, event: str, tool: str, payload: dict[str, Any]) -> StatusSemantic:
    if agent == "claude":
        return claude_semantic(event, tool, payload)
    return codex_semantic(event, tool, payload)


# ---- what the agent is doing right now (for the sticker speech bubble) ----

ACTIVITY_TYPES = ("read", "edit", "command", "search", "web", "agent", "plan", "permission")
ACTIVITY_TARGET_MAX = 40


class Activity(TypedDict):
    type: str  # one of ACTIVITY_TYPES
    target: str  # short, privacy-safe: a file name, a command name, a pattern…
    phase: str  # "pre" (about to run / running) or "post" (just finished)


def _short(value: str, limit: int = ACTIVITY_TARGET_MAX) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("tool_input", "input", "arguments", "params"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return {"_raw": value}
            if isinstance(parsed, dict):
                return parsed
            return {"_raw": value}
    return {}


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _file_name(path: str) -> str:
    return os.path.basename(path.rstrip("/")) or path


SAFE_SUBCOMMAND = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,19}")


def summarize_command(command: Any) -> str:
    """Program name plus a plain subcommand ("git push", "npm test", "pytest"), never arguments
    — those can carry tokens, passwords or private paths."""
    if isinstance(command, list):
        tokens = [str(token) for token in command]
    elif isinstance(command, str):
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
    else:
        return ""
    # `bash -lc "real command"` (Codex) → look inside.
    if len(tokens) >= 3 and _file_name(tokens[0]) in ("bash", "sh", "zsh") and tokens[1] in ("-c", "-lc"):
        return summarize_command(tokens[2])
    while tokens and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]) or tokens[0] in ("sudo", "env", "time", "nohup")):
        tokens.pop(0)
    if not tokens:
        return ""
    program = _file_name(tokens[0])
    if len(tokens) > 1 and SAFE_SUBCOMMAND.fullmatch(tokens[1]) and not tokens[1].startswith("-"):
        return _short(f"{program} {tokens[1]}")
    return _short(program)


PATCH_FILE = re.compile(r"\*\*\* (?:Update|Add|Delete) File: (.+)")


def describe_activity(event: str, tool: str, payload: dict[str, Any]) -> Activity | None:
    """A short description of what the agent is doing, from a Claude Code / Codex hook payload."""
    event_l = event.lower()
    tool_l = tool.lower().split(".")[-1]
    data = _tool_input(payload)

    def activity(kind: str, target: str, phase: str = "pre") -> Activity | None:
        target = _short(target)
        return {"type": kind, "target": target, "phase": phase} if target or kind == "plan" else None

    if event_l == "notification":
        message = payload.get("message")
        if isinstance(message, str) and contains_any(message.lower(), ("permission", "approve", "approval")):
            match = re.search(r"\buse ([A-Za-z][A-Za-z0-9_.-]*)", message)
            return activity("permission", match.group(1) if match else "this")
        return None
    if event_l == "permissionrequest":
        command = summarize_command(data.get("command") or data.get("cmd"))
        return activity("permission", command or tool or "this")
    if event_l not in ("pretooluse", "posttooluse"):
        return None
    phase = "post" if event_l == "posttooluse" else "pre"

    if tool_l in ("read", "notebookread", "view"):
        return activity("read", _file_name(_first_text(data, ("file_path", "notebook_path", "path"))), phase)
    if tool_l in ("edit", "multiedit", "write", "notebookedit", "str_replace_editor", "create"):
        return activity("edit", _file_name(_first_text(data, ("file_path", "notebook_path", "path"))), phase)
    if tool_l in ("apply_patch", "patch"):
        raw = _first_text(data, ("input", "patch", "_raw"))
        match = PATCH_FILE.search(raw)
        return activity("edit", _file_name(match.group(1).strip()) if match else "a few files", phase)
    if tool_l in ("bash", "shell", "exec_command", "local_shell", "run_command", "terminal"):
        description = _first_text(data, ("description",))
        return activity("command", description or summarize_command(data.get("command") or data.get("cmd")), phase)
    if tool_l in ("grep", "glob", "search", "find", "ls", "list_dir"):
        return activity("search", _first_text(data, ("pattern", "query", "path")), phase)
    if tool_l == "webfetch":
        url = _first_text(data, ("url",))
        return activity("web", urllib.parse.urlparse(url).hostname or url, phase)
    if tool_l in ("websearch", "web_search"):
        return activity("web", _first_text(data, ("query",)), phase)
    if tool_l in ("task", "agent"):
        return activity("agent", _first_text(data, ("description", "subagent_type")), phase)
    if tool_l in ("todowrite", "update_plan"):
        return activity("plan", "", phase)
    return None


def parse_activity(value: Any) -> Activity | None:
    """Validate an activity read back from a status file (the widget side)."""
    if not isinstance(value, dict):
        return None
    kind, target, phase = value.get("type"), value.get("target"), value.get("phase", "pre")
    if kind not in ACTIVITY_TYPES or not isinstance(target, str) or phase not in ("pre", "post"):
        return None
    return {"type": kind, "target": _short(target), "phase": phase}
