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


class WidgetAnimationTests(unittest.TestCase):
    @unittest.skipUnless(GUI_TESTS_AVAILABLE, "xvfb-run and PySide6 are required")
    def test_provider_refresh_uses_dedicated_30_fps_timer_and_resets(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys

            sys.path.insert(0, "bin")
            module = runpy.run_path(
                "bin/ai-agent-status-widget",
                run_name="widget_animation_smoke",
            )
            widget = module["StatusWidget"](demo=True)
            assert module["USAGE_ANIMATION_INTERVAL_MS"] == 33
            widget.start_usage_refresh("claude")
            source_id = widget.usage_animation_source_id
            assert source_id is not None
            assert widget.usage_refreshing_providers == {"claude"}
            assert widget.tick_usage_animation() is True
            assert widget.usage_logo_widgets["claude"].angle > 0
            assert widget.usage_logo_widgets["codex"].angle == 0
            widget.finish_demo_usage_refresh()
            assert widget.usage_animation_source_id is None
            assert all(logo.angle == 0 for logo in widget.usage_logo_widgets.values())
            widget.apply_demo_usage_state(1)
            demo_source_id = widget.usage_animation_source_id
            assert demo_source_id is not None
            widget.apply_demo_usage_state(1)
            assert widget.usage_animation_source_id == demo_source_id
            widget.apply_demo_usage_state(0)
            assert widget.usage_animation_source_id is None
            widget.shutdown()
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            environment = {key: value for key, value in os.environ.items() if not key.startswith("AI_STATUS_")}
            environment.update({
                "AI_STATUS_ENV_FILE": str(Path(directory) / ".env"),
                "AI_STATUS_CACHE_DIR": str(Path(directory) / "cache"),
                "AI_STATUS_CONFIG_DIR": str(Path(directory) / "config"),
                "AI_STATUS_DATA_DIR": str(ROOT / "assets"),
            })
            completed = subprocess.run(
                ["xvfb-run", "-a", sys.executable, "-c", probe],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
