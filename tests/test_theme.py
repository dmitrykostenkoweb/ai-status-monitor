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
        self.assertEqual(theme.DARK.surface, "#1C1D2C")
        self.assertEqual(theme.DARK.text, "#F4EEDC")
        self.assertEqual(theme.rgba(theme.DARK.outline), (244, 238, 220, 0.9))
        self.assertEqual(theme.rgba(theme.DARK.shadow), (0, 0, 0, 0.55))
        self.assertEqual(theme.DARK.title, theme.CLAUDE)

    def test_bar_thresholds_follow_the_handoff(self) -> None:
        self.assertEqual(theme.bar_tone(0), "ok")
        self.assertEqual(theme.bar_tone(74.9), "ok")
        self.assertEqual(theme.bar_tone(75), "warn")
        self.assertEqual(theme.bar_tone(89.9), "warn")
        self.assertEqual(theme.bar_tone(90), "crit")
        self.assertEqual(theme.DARK.bar_inks["warn"], "#FDBA74")
        self.assertEqual(theme.LIGHT.bar_inks["crit"], "#C1121F")

    def test_status_dots_and_badges(self) -> None:
        self.assertEqual(theme.status_dot("analyzing", theme.DARK), theme.YELLOW)
        self.assertEqual(theme.status_dot("coding", theme.DARK), "#4ADE80")
        self.assertEqual(theme.status_dot("waiting", theme.LIGHT), theme.RED)
        self.assertEqual(theme.status_dot("done", theme.DARK), theme.CODEX)
        self.assertEqual(theme.status_dot("idle", theme.DARK), theme.DARK.idle_badge)
        self.assertEqual(theme.badge_style("alert", theme.DARK, 2), ("▲ 2 ALERT", "#FB7185"))
        self.assertEqual(theme.badge_style("live", theme.DARK), ("● LIVE", "#4ADE80"))
        self.assertEqual(theme.badge_style("idle", theme.DARK), ("● IDLE", "#A9A6C0"))

    def test_rgba_parses_hex_and_css(self) -> None:
        self.assertEqual(theme.rgba("#FF9B7A"), (255, 155, 122, 1.0))
        self.assertEqual(theme.rgba("rgba(28, 29, 44, .58)"), (28, 29, 44, 0.58))
        self.assertEqual(theme.with_alpha("#FFD23F", 0.2), "rgba(255,210,63,0.2)")
        with self.assertRaises(ValueError):
            theme.rgba("teal")

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
        self.assertEqual(settings.card_width, 340)
        self.assertEqual(settings.title, "AI Agents Status")
        self.assertEqual(settings.surface_opacity, theme.DEFAULT_SURFACE_OPACITY)

    def test_surface_opacity_is_range_checked(self) -> None:
        warnings: list[str] = []
        ok = load_settings(environ={"HOME": "/h"}, dotenv_values={"AI_STATUS_SURFACE_OPACITY": "58"}, legacy={})
        self.assertEqual(ok.surface_opacity, 58)
        self.assertEqual(ok.as_env()["AI_STATUS_SURFACE_OPACITY"], "58")
        for bad in ("20", "100", "0.6"):
            settings = load_settings(environ={"HOME": "/h"}, dotenv_values={"AI_STATUS_SURFACE_OPACITY": bad},
                                     legacy={}, diagnostic=warnings.append)
            self.assertEqual(settings.surface_opacity, theme.DEFAULT_SURFACE_OPACITY)
        self.assertTrue(any("AI_STATUS_SURFACE_OPACITY" in message for message in warnings))


if __name__ == "__main__":
    unittest.main()
