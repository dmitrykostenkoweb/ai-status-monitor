"""Toolkit-free window placement maths (monitor rescue, dialogs beside the widget)."""

from __future__ import annotations

from typing import Callable, NamedTuple, Sequence

# Breathing room kept between a rescued window and the edge of its monitor.
OFFSCREEN_MARGIN = 40
MIN_VISIBLE_HEIGHT = 120


class Rect(NamedTuple):
    x: int
    y: int
    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


def clamp_to_visible(
    x: int,
    y: int,
    areas: Sequence[Rect],
    window_width: int,
    log: Callable[[str], None] = lambda _message: None,
) -> tuple[int, int]:
    """Pull a saved position back onto a monitor that still exists.

    A multi-monitor desktop packs every monitor into one virtual screen, so a layout
    that is not one plain rectangle leaves dead zones: coordinates the window system
    accepts but no physical panel ever draws. A position saved under an earlier
    monitor arrangement can end up in such a zone, which leaves the widget running
    yet invisible. Fall back to the nearest monitor's work area instead.
    """
    if not areas:
        return x, y
    if any(area.contains(x, y) for area in areas):
        return x, y

    def squared_distance(area: Rect) -> int:
        dx = max(area.x - x, 0, x - (area.x + area.width - 1))
        dy = max(area.y - y, 0, y - (area.y + area.height - 1))
        return dx * dx + dy * dy

    target = min(areas, key=squared_distance)
    max_x = max(target.x, target.x + target.width - window_width - OFFSCREEN_MARGIN)
    max_y = max(target.y, target.y + target.height - MIN_VISIBLE_HEIGHT)
    clamped_x = min(max(x, target.x + OFFSCREEN_MARGIN), max_x)
    clamped_y = min(max(y, target.y + OFFSCREEN_MARGIN), max_y)
    log(f"saved position {x},{y} is off-screen, moved to {clamped_x},{clamped_y}")
    return clamped_x, clamped_y


def place_beside(anchor: Rect, size: tuple[int, int], area: Rect, gap: int = 12) -> tuple[int, int]:
    """Top-left for a dialog next to ``anchor``: right if it fits, else left, kept in ``area``."""
    width, height = size
    target_x = anchor.x + anchor.width + gap
    if target_x + width > area.x + area.width:
        target_x = anchor.x - width - gap
    target_x = max(area.x, min(target_x, area.x + area.width - width))
    target_y = max(area.y, min(anchor.y, area.y + area.height - height))
    return target_x, target_y
