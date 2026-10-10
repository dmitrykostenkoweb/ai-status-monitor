from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from ai_agent_status_lib import stickers  # noqa: E402
from ai_agent_status_lib import theme  # noqa: E402
from ai_agent_status_lib.env_config import load_settings  # noqa: E402


class ThemeTokenTests(unittest.TestCase):
    def test_dark_is_primary_and_unknown_names_fall_back_to_it(self) -> None:
        self.assertIs(theme.get_theme("dark"), theme.DARK)
        self.assertIs(theme.get_theme("light"), theme.LIGHT)
        self.assertIs(theme.get_theme("neon"), theme.DARK)
        self.assertEqual(theme.DARK.card, "#24263A")
        self.assertEqual(theme.DARK.ink, "#F4EEDC")
        self.assertEqual(theme.LIGHT.header, theme.YELLOW)

    def test_bar_thresholds_follow_the_handoff(self) -> None:
        self.assertEqual(theme.bar_tone(0), "ok")
        self.assertEqual(theme.bar_tone(74.9), "ok")
        self.assertEqual(theme.bar_tone(75), "warn")
        self.assertEqual(theme.bar_tone(89.9), "warn")
        self.assertEqual(theme.bar_tone(90), "crit")
        self.assertEqual(theme.DARK.bar_inks["warn"], "#FDBA74")
        self.assertEqual(theme.LIGHT.bar_inks["crit"], "#C1121F")

    def test_status_chips_and_badges(self) -> None:
        self.assertEqual(theme.status_chip("analyzing", theme.DARK), (theme.YELLOW, theme.INK_ON_COLOUR))
        self.assertEqual(theme.status_chip("coding", theme.DARK), ("#4ADE80", theme.INK_ON_COLOUR))
        self.assertEqual(theme.status_chip("waiting", theme.LIGHT), (theme.RED, theme.WHITE))
        self.assertEqual(theme.status_chip("done", theme.LIGHT), (theme.LIGHT.muted_chip, theme.INK_ON_COLOUR))
        self.assertEqual(theme.badge_style("alert", theme.DARK, 2), ("▲ 2 ALERT!", theme.RED, theme.WHITE))
        self.assertEqual(theme.badge_style("live", theme.DARK)[0], "● LIVE")
        self.assertEqual(theme.badge_style("idle", theme.LIGHT)[1], "#D6D3C4")

    def test_every_sticker_has_a_bubble_fill_and_sound_effects(self) -> None:
        for key in stickers.STICKER_KEYS:
            with self.subTest(key=key):
                self.assertTrue(theme.bubble_fill(key).startswith("#"))
                self.assertTrue(stickers.STICKER_SFX[key])


class ThemeSettingTests(unittest.TestCase):
    def test_theme_accepts_dark_or_light_only(self) -> None:
        warnings: list[str] = []
        settings = load_settings(environ={"HOME": "/h"}, dotenv_values={"AI_STATUS_THEME": " Light "}, legacy={})
        self.assertEqual(settings.theme, "light")
        fallback = load_settings(environ={"HOME": "/h"}, dotenv_values={"AI_STATUS_THEME": "neon"}, legacy={},
                                 diagnostic=warnings.append)
        self.assertEqual(fallback.theme, "dark")
        self.assertTrue(any("AI_STATUS_THEME" in message for message in warnings))

    def test_new_switches_default_on_and_parse(self) -> None:
        settings = load_settings(environ={"HOME": "/h"}, dotenv_values={}, legacy={})
        self.assertTrue(settings.show_limits)
        self.assertTrue(settings.autostart)
        off = load_settings(environ={"HOME": "/h"}, legacy={},
                            dotenv_values={"AI_STATUS_SHOW_LIMITS": "no", "AI_STATUS_AUTOSTART": "false"})
        self.assertFalse(off.show_limits)
        self.assertFalse(off.autostart)
        self.assertEqual(off.as_env()["AI_STATUS_AUTOSTART"], "false")

    def test_comic_defaults(self) -> None:
        settings = load_settings(environ={"HOME": "/h"}, dotenv_values={}, legacy={})
        self.assertEqual(settings.card_width, 294)
        self.assertEqual(settings.title, "AI Agents Status!")


if __name__ == "__main__":
    unittest.main()
