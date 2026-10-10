from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _pyside6_importable() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
    except Exception:
        return False
    return True


GUI_TESTS_AVAILABLE = bool(shutil.which("xvfb-run")) and _pyside6_importable()


class WidgetAgentFilterTests(unittest.TestCase):
    @unittest.skipUnless(GUI_TESTS_AVAILABLE, "xvfb-run and PySide6 are required")
    def test_agent_filter_hides_rows_usage_and_persists_menu_choice(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="widget_agents_smoke")
            widget = module["StatusWidget"](demo=True)
            env_file = Path(sys.argv[1])

            assert widget.agents == ("codex",)
            assert {s["agent"] for s in widget.collect_sessions()} == {"codex"}
            widget.render_usage_limits()
            assert set(widget.usage_logo_buttons) == {"codex"}
            assert widget.start_usage_refresh("claude") is False
            assert widget.usage_refreshing is False

            widget.set_agents(("claude",))
            assert {s["agent"] for s in widget.collect_sessions()} == {"claude"}
            assert set(widget.usage_logo_buttons) == {"claude"}
            assert "AI_STATUS_AGENTS=claude" in env_file.read_text().splitlines()
            assert "AI_STATUS_THEME=light" in env_file.read_text().splitlines()

            widget.set_agents(("claude", "codex"))
            assert {s["agent"] for s in widget.collect_sessions()} == {"claude", "codex"}
            assert set(widget.usage_logo_buttons) == {"claude", "codex"}
            widget.shutdown()
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("AI_STATUS_THEME=light\nAI_STATUS_AGENTS=codex\n", encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if key != "AI_STATUS_AGENTS"}
            environment["AI_STATUS_ENV_FILE"] = str(env_file)
            environment["AI_STATUS_CACHE_DIR"] = str(Path(directory) / "cache")
            environment["AI_STATUS_DATA_DIR"] = str(ROOT / "assets")
            completed = subprocess.run(
                ["xvfb-run", "-a", sys.executable, "-c", probe, str(env_file)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


    @unittest.skipUnless(GUI_TESTS_AVAILABLE, "xvfb-run and PySide6 are required")
    def test_settings_window_applies_and_saves_changes(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="widget_settings_smoke")
            widget = module["StatusWidget"](demo=True)
            env_file = Path(sys.argv[1])

            widget.open_settings()
            window = widget.settings_window
            assert window is not None
            widget.open_settings()
            assert widget.settings_window is window

            window.sound_switch.setChecked(False)
            assert widget.config["sound_enabled"] is False
            window.rows_spin.setValue(3)
            assert widget.max_rows == 3

            window.agent_checks["claude"].setChecked(False)
            assert widget.agents == ("codex",)
            window.agent_checks["codex"].setChecked(False)
            assert widget.agents == ("codex",)
            assert window.agent_checks["codex"].isChecked() is True

            widget.set_agents(("claude", "codex"))
            assert window.agent_checks["claude"].isChecked() is True

            widget.update_setting("AI_STATUS_IDLE_AFTER_SECONDS", "90")
            assert widget.config["idle_after_seconds"] == 90

            lines = env_file.read_text().splitlines()
            for expected in (
                "AI_STATUS_THEME=light",
                "AI_STATUS_SOUND_ENABLED=false",
                "AI_STATUS_MAX_ROWS=3",
                "AI_STATUS_AGENTS=claude,codex",
                "AI_STATUS_IDLE_AFTER_SECONDS=90",
            ):
                assert expected in lines, (expected, lines)

            window.close()
            assert widget.settings_window is None
            widget.shutdown()
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("AI_STATUS_THEME=light\n", encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("AI_STATUS_")}
            environment["AI_STATUS_ENV_FILE"] = str(env_file)
            environment["AI_STATUS_CACHE_DIR"] = str(Path(directory) / "cache")
            environment["AI_STATUS_CONFIG_DIR"] = str(Path(directory) / "config")
            environment["AI_STATUS_DATA_DIR"] = str(ROOT / "assets")
            completed = subprocess.run(
                ["xvfb-run", "-a", sys.executable, "-c", probe, str(env_file)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
