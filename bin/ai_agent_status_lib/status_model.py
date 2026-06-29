from __future__ import annotations

import json
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
    """Legacy fallback for status records written before `kind` existed."""
    text = status.lower()
    if any(word in text for word in ("not running", "nie uruchomiony")):
        return "idle"
    if any(word in text for word in ("czeka", "zgod", "permission", "approval")):
        return "waiting"
    if any(word in text for word in ("błąd", "error", "failure", "malformed")):
        return "error"
    if "myśl" in text:
        return "thinking"
    if "czyta" in text:
        return "reading"
    if "koduje" in text:
        return "coding"
    if "wykon" in text or "komend" in text:
        return "command"
    if "analiz" in text:
        return "analyzing"
    if "kończył" in text or "done" in text or "finished" in text:
        return "done"
    if "brak nowych" in text:
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
        return {"kind": "thinking", "status": f"{agent}: myśli"}
    if event_l == "pretooluse":
        if contains_any(tool_l, ("askuserquestion", "ask_user", "question", "input")):
            return {"kind": "waiting", "status": f"{agent}: czeka na Ciebie"}
        if contains_any(tool_l, ("edit", "write", "multiedit", "notebookedit", "todowrite")):
            return {"kind": "coding", "status": f"{agent}: koduje"}
        if contains_any(tool_l, ("bash", "shell", "command")):
            return {"kind": "command", "status": f"{agent}: wykonuje komendę"}
        if contains_any(tool_l, ("read", "grep", "glob", "ls", "search", "webfetch", "websearch")):
            return {"kind": "reading", "status": f"{agent}: czyta kod"}
        return {"kind": "neutral", "status": f"{agent}: wykonuje akcję"}
    if event_l == "posttooluse":
        return {"kind": "analyzing", "status": f"{agent}: analizuje wynik"}
    if event_l == "notification":
        text = payload_search_text(payload)
        if contains_any(text, ("permission", "approval", "approve", "allow", "confirm", "trust", "zgod")):
            return {"kind": "waiting", "status": f"{agent}: czeka na zgodę"}
        if contains_any(text, ("idle", "input", "response", "user", "waiting", "czeka")):
            return {"kind": "waiting", "status": f"{agent}: czeka na Ciebie"}
    if event_l == "stop":
        return {"kind": "done", "status": f"{agent}: zakończył"}
    if event_l == "stopfailure":
        return {"kind": "error", "status": f"{agent}: błąd"}
    if event_l in ("malformed_json", "unexpected_payload"):
        return {"kind": "error", "status": f"{agent}: {event}"}
    return {"kind": "neutral", "status": f"{agent}: {event}"}


def codex_semantic(event: str, tool: str, payload: dict[str, Any]) -> StatusSemantic:
    event_l = event.lower()
    tool_l = tool.lower()
    agent = "Codex"

    if event_l == "userpromptsubmit":
        return {"kind": "thinking", "status": f"{agent}: myśli"}
    if event_l == "pretooluse":
        if contains_any(tool_l, ("shell", "bash", "exec", "command", "terminal")):
            return {"kind": "command", "status": f"{agent}: wykonuje komendę"}
        if contains_any(tool_l, ("apply_patch", "patch", "edit", "write")):
            return {"kind": "coding", "status": f"{agent}: koduje"}
        if contains_any(tool_l, ("read", "search", "rg", "grep", "find", "open", "cat", "sed", "ls")):
            return {"kind": "reading", "status": f"{agent}: czyta kod"}
    if event_l == "permissionrequest":
        return {"kind": "waiting", "status": f"{agent}: czeka na zgodę"}
    if event_l == "posttooluse":
        return {"kind": "analyzing", "status": f"{agent}: analizuje wynik"}
    if event_l == "stop":
        return {"kind": "done", "status": f"{agent}: zakończył"}
    if event_l == "subagentstop":
        return {"kind": "done", "status": "Codex subagent: zakończył"}
    if event_l in ("stopfailure", "malformed_json", "unexpected_payload"):
        return {"kind": "error", "status": f"{agent}: {event}"}
    return {"kind": "neutral", "status": f"{agent}: {event}"}


def agent_semantic(agent: str, event: str, tool: str, payload: dict[str, Any]) -> StatusSemantic:
    if agent == "claude":
        return claude_semantic(event, tool, payload)
    return codex_semantic(event, tool, payload)
