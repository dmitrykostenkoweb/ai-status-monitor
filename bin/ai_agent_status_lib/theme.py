"""Design tokens for the minimal comic look on translucent glass (dark = primary, light = optional).

Plain data, no GUI toolkit: the widget paints with these values and the tests can
check them. Source: the "AI Status Monitor — Comic Minimal (translucent)" design
handoff (it replaced the earlier heavy comic skin: thick borders, halftone header).
Colours with transparency are CSS-style ``rgba(r,g,b,a)`` strings; ``rgba()`` parses them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Brand / state colours shared by both themes.
CLAUDE = "#FF9B7A"
CODEX = "#7DD3FC"
YELLOW = "#FFD23F"
RED = "#E63946"
GREEN = "#4ADE80"
INK_ON_COLOUR = "#111111"  # text on any light/colour fill (bubbles, polaroid, hovered jump button)
WHITE = "#FFFFFF"
POLAROID = "rgba(244,238,220,0.92)"
POLAROID_INK = "#111111"

AGENT_COLORS = {"claude": CLAUDE, "codex": CODEX}
BAR_FILLS = {"ok": GREEN, "warn": "#FB923C", "crit": "#F43F5E"}
WARN_PERCENT = 75.0
CRIT_PERCENT = 90.0

# Card surface opacity (Settings → Card opacity, AI_STATUS_SURFACE_OPACITY, in percent).
# Qt cannot blur the desktop behind a window, so the default sits at the handoff's
# "no blur" fallback (.82) rather than its blurred .58.
MIN_SURFACE_OPACITY = 40
MAX_SURFACE_OPACITY = 95
DEFAULT_SURFACE_OPACITY = 82

_RGBA = re.compile(r"^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$")


def rgba(value: str) -> tuple[int, int, int, float]:
    """``#RRGGBB`` or ``rgba(r,g,b,a)`` → (r, g, b, alpha 0–1)."""
    match = _RGBA.match(value.strip())
    if match:
        r, g, b, a = match.groups()
        return int(r), int(g), int(b), max(0.0, min(1.0, float(a)))
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"not a colour: {value!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), 1.0


def with_alpha(value: str, alpha: float) -> str:
    r, g, b, _a = rgba(value)
    return f"rgba({r},{g},{b},{alpha:g})"


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str          # glass card fill (RGB; alpha comes from the opacity setting)
    dialog: str           # opaque fill for Settings / menus
    outline: str          # 1.5 px card outline
    divider: str          # dashed rule under the header
    divider_soft: str     # dashed rule between providers / rows
    shadow: str           # hard 3 px offset shadow, no blur
    title: str            # header title
    text: str
    text_secondary: str   # "resets …", "project · time", flat buttons
    hover: str            # flat button hover fill
    track: str            # progress-bar track
    track_outline: str
    jump_outline: str     # ➜ button outline
    idle_badge: str
    bar_inks: dict[str, str]


DARK = Theme(
    name="dark",
    surface="#1C1D2C",
    dialog="#1C1D2C",
    outline="rgba(244,238,220,0.9)",
    divider="rgba(244,238,220,0.25)",
    divider_soft="rgba(244,238,220,0.2)",
    shadow="rgba(0,0,0,0.55)",
    title=CLAUDE,
    text="#F4EEDC",
    text_secondary="#A9A6C0",
    hover="rgba(244,238,220,0.12)",
    track="rgba(0,0,0,0.25)",
    track_outline="rgba(244,238,220,0.7)",
    jump_outline="rgba(244,238,220,0.5)",
    idle_badge="#A9A6C0",
    bar_inks={"ok": "#86EFAC", "warn": "#FDBA74", "crit": "#FB7185"},
)

LIGHT = Theme(
    name="light",
    surface="#FFF8E1",
    dialog="#FFF8E1",
    outline="rgba(17,17,17,0.85)",
    divider="rgba(17,17,17,0.25)",
    divider_soft="rgba(17,17,17,0.18)",
    shadow="rgba(0,0,0,0.35)",
    title="#D9480F",
    text="#111111",
    text_secondary="#55546A",
    hover="rgba(17,17,17,0.08)",
    track="rgba(0,0,0,0.06)",
    track_outline="rgba(17,17,17,0.6)",
    jump_outline="rgba(17,17,17,0.45)",
    idle_badge="#6B6980",
    bar_inks={"ok": "#15803D", "warn": "#C2410C", "crit": "#C1121F"},
)

THEMES = {"dark": DARK, "light": LIGHT}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, DARK)


def bar_tone(used_percent: float) -> str:
    """``ok`` below 75 %, ``warn`` from 75 %, ``crit`` from 90 %."""
    if used_percent >= CRIT_PERCENT:
        return "crit"
    if used_percent >= WARN_PERCENT:
        return "warn"
    return "ok"


# Session status dot per structured status kind (8 px dot + 3 px ring at 20 % alpha).
STATUS_DOTS = {
    "thinking": YELLOW,
    "reading": YELLOW,
    "analyzing": YELLOW,
    "coding": GREEN,
    "command": "#5EEAD4",
    "waiting": RED,
    "error": RED,
    "done": CODEX,
}
DOT_RING_ALPHA = 0.2
MUTED_KINDS = frozenset({"idle", "stale", "neutral"})


def status_dot(kind: str, theme: Theme) -> str:
    return STATUS_DOTS.get(kind, theme.idle_badge)


# Speech-bubble fill per sticker key.
BUBBLE_FILLS = {
    "analyzing": YELLOW,
    "coding": "#A7F3D0",
    "waiting": "#FFB4BC",
    "error": "#FFB4BC",
    "done": "#A7F3D0",
    "limit": "#FDBA74",
    "idle": "#E5E1D3",
}


def bubble_fill(sticker_key: str) -> str:
    return BUBBLE_FILLS.get(sticker_key, "#E5E1D3")


# Header badge: an outline-only pill, (label, colour) — text and outline share the colour.
def badge_style(state: str, theme: Theme, waiting_count: int = 0) -> tuple[str, str]:
    if state == "alert":
        return f"▲ {waiting_count} ALERT", theme.bar_inks["crit"]
    if state == "live":
        return "● LIVE", GREEN if theme.name == "dark" else theme.bar_inks["ok"]
    return "● IDLE", theme.idle_badge
