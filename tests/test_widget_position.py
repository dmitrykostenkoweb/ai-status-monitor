from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib.screen_geometry import Rect  # noqa: E402
from ai_agent_status_lib.screen_geometry import clamp_to_visible  # noqa: E402
from ai_agent_status_lib.screen_geometry import place_beside  # noqa: E402

CARD_WIDTH = 344


# A laptop panel parked below and to the right of two external screens: the virtual
# screen spans 5120x2520, but its bottom-left corner belongs to no monitor at all.
L_SHAPED_LAYOUT = [
    Rect(0, 0, 2560, 1440),
    Rect(2560, 0, 2560, 1440),
    Rect(1248, 1440, 1920, 1080),
]


def on_a_monitor(x: int, y: int, areas: list[Rect]) -> bool:
    return any(area.contains(x, y) for area in areas)


class ClampToVisibleTests(unittest.TestCase):
    def clamp(self, x: int, y: int, areas: list[Rect] | None = None) -> tuple[int, int]:
        return clamp_to_visible(x, y, L_SHAPED_LAYOUT if areas is None else areas, CARD_WIDTH)

    def test_position_on_a_monitor_is_left_alone(self) -> None:
        for x, y in ((40, 80), (4752, 0), (2000, 2000)):
            with self.subTest(position=(x, y)):
                self.assertEqual(self.clamp(x, y), (x, y))

    def test_dead_zone_of_an_l_shaped_layout_is_rescued(self) -> None:
        # Saved while the laptop sat further left; now inside the virtual screen but
        # on no physical panel, which used to leave the widget running yet invisible.
        rescued = self.clamp(460, 2211)
        self.assertNotEqual(rescued, (460, 2211))
        self.assertTrue(on_a_monitor(*rescued, L_SHAPED_LAYOUT))

    def test_position_beyond_every_monitor_is_rescued(self) -> None:
        for x, y in ((9000, 9000), (-500, -500), (0, 2519)):
            with self.subTest(position=(x, y)):
                self.assertTrue(on_a_monitor(*self.clamp(x, y), L_SHAPED_LAYOUT))

    def test_rescue_picks_the_nearest_monitor(self) -> None:
        # Just below the left screen, so the widget should come back on the left one.
        x, _ = self.clamp(460, 2211)
        self.assertLess(x, 2560)
        # Just right of the right screen: the rescue must not jump across the desk.
        x, _ = self.clamp(5300, 700)
        self.assertGreaterEqual(x, 2560)

    def test_rescued_window_keeps_its_width_on_screen(self) -> None:
        x, _ = self.clamp(9000, 9000)
        self.assertLessEqual(x + CARD_WIDTH, 5120)

    def test_no_reported_monitors_leaves_the_position_untouched(self) -> None:
        self.assertEqual(self.clamp(460, 2211, areas=[]), (460, 2211))


class PlaceBesideTests(unittest.TestCase):
    def test_prefers_the_right_side_and_falls_back_to_the_left(self) -> None:
        area = Rect(0, 0, 1920, 1080)
        self.assertEqual(place_beside(Rect(100, 50, 360, 200), (400, 600), area), (472, 50))
        self.assertEqual(place_beside(Rect(1500, 50, 360, 200), (400, 600), area), (1088, 50))

    def test_stays_inside_the_work_area(self) -> None:
        x, y = place_beside(Rect(10, 900, 360, 200), (400, 600), Rect(0, 0, 800, 1080))
        self.assertEqual((x, y), (382, 480))


if __name__ == "__main__":
    unittest.main()
