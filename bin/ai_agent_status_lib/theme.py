"""Design tokens for the comic look (dark = primary, light = optional theme).

Plain data, no GUI toolkit: the widget paints with these values and the tests can
check them. Source: the "AI Status Monitor — Comic Redesign" design handoff.
"""

from __future__ import annotations

from dataclasses import dataclass

# Brand / state colours shared by both themes.
CLAUDE = "#FF9B7A"
CODEX = "#7DD3FC"
YELLOW = "#FFD23F"
YELLOW_HOVER = "#FFF3B0"
RED = "#E63946"
INK_ON_COLOUR = "#111111"  # text on any light/colour fill (circles, chips, bubbles, badges)
WHITE = "#FFFFFF"
POLAROID = "#F4EEDC"
POLAROID_INK = "#0B0B10"

AGENT_COLORS = {"claude": CLAUDE, "codex": CODEX}
BAR_FILLS = {"ok": "#4ADE80", "warn": "#FB923C", "crit": "#F43F5E"}
WARN_PERCENT = 75.0
CRIT_PERCENT = 90.0


@dataclass(frozen=True)
class Theme:
    name: str
    card: str          # card surface
    inner: str         # inner blocks, neutral buttons
    track: str         # progress-bar track
    ink: str           # outlines and primary text
    shadow: str        # hard offset shadows
    text: str
    text_secondary: str   # "resets …"
    text_tertiary: str    # "project · time"
    header: str
    header_dots: tuple[int, int, int, float]
    idle_badge: str
    muted_chip: str       # done / idle / stale status chips
    bar_inks: dict[str, str]


DARK = Theme(
    name="dark",
    card="#24263A",
    inner="#2E3150",
    track="#15162A",
    ink="#F4EEDC",
    shadow="#000000",
    text="#F4EEDC",
    text_secondary="#A9A6C0",
    text_tertiary="#C9C6DD",
    header=CLAUDE,
    header_dots=(200, 40, 30, 0.55),
    idle_badge="#8E8BA6",
    muted_chip="#8E8BA6",
    bar_inks={"ok": "#86EFAC", "warn": "#FDBA74", "crit": "#FB7185"},
)

LIGHT = Theme(
    name="light",
    card="#FFF8E1",
    inner="#FFFFFF",
    track="#F1EAD2",
    ink="#111111",
    shadow="#111111",
    text="#111111",
    text_secondary="#555555",
    text_tertiary="#333333",
    header=YELLOW,
    header_dots=(230, 57, 70, 0.35),
    idle_badge="#D6D3C4",
    muted_chip="#D6D3C4",
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


# Status chip (background, text) per structured status kind; muted kinds use the theme.
STATUS_CHIPS = {
    "thinking": (YELLOW, INK_ON_COLOUR),
    "reading": (YELLOW, INK_ON_COLOUR),
    "analyzing": (YELLOW, INK_ON_COLOUR),
    "coding": ("#4ADE80", INK_ON_COLOUR),
    "command": ("#5EEAD4", INK_ON_COLOUR),
    "waiting": (RED, WHITE),
    "error": (RED, WHITE),
}
MUTED_KINDS = frozenset({"done", "idle", "stale", "neutral"})


def status_chip(kind: str, theme: Theme) -> tuple[str, str]:
    return STATUS_CHIPS.get(kind, (theme.muted_chip, INK_ON_COLOUR))


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


# Header badge: (label template, background, text).
def badge_style(state: str, theme: Theme, waiting_count: int = 0) -> tuple[str, str, str]:
    if state == "alert":
        return f"▲ {waiting_count} ALERT!", RED, WHITE
    if state == "live":
        return "● LIVE", "#4ADE80", INK_ON_COLOUR
    return "● IDLE", theme.idle_badge, INK_ON_COLOUR
