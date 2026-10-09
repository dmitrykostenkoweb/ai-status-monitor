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


class WidgetAgentFilterTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("xvfb-run"), "xvfb-run is required")
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
            widget.destroy()
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


if __name__ == "__main__":
    unittest.main()
