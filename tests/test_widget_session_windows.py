from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SessionWindowTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("xvfb-run"), "xvfb-run is required")
    def test_each_session_gets_a_window_with_its_own_sticker(self) -> None:
        probe = textwrap.dedent(
            """
            import json
            import runpy
            import sys
            import time
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="session_windows_smoke")
            GLib = module["GLib"]
            widget = module["StatusWidget"](demo=True)
            widget.show_all()
            config_dir = Path(sys.argv[1])

            def pump(condition, seconds=3.0):
                deadline = time.monotonic() + seconds
                context = GLib.MainContext.default()
                while time.monotonic() < deadline:
                    if condition():
                        return True
                    context.iteration(False)
                    time.sleep(0.01)
                return condition()

            def session(sid, kind, agent="claude"):
                row = widget.make_session(agent, kind, sid, "12:00", kind=kind)
                row["id"] = sid
                return row

            assert widget.session_windows is True
            # Startup: only the usage panel; no intro splash and no idle lockup animation.
            assert widget.intro is False
            assert not widget.body.get_visible() and widget.spinning == []
            current_sessions = []
            widget.collect_sessions = lambda: list(current_sessions)
            widget.refresh_status()
            assert not widget.body.get_visible() and widget.spinning == []

            def sync(sessions):
                # Keep the widget's own refreshes (e.g. after a settings change) in step.
                current_sessions[:] = sessions
                widget.sync_session_cards(sessions)
            sync([session("a", "coding"), session("b", "waiting", "codex")])
            assert list(widget.session_cards) == ["a", "b"]
            card_a, card_b = widget.session_cards["a"], widget.session_cards["b"]
            assert card_a.get_title() == "AI agent session"
            assert "waiting" in card_b.card.get_style_context().list_classes()

            # every card picks its own sticker and keeps it up (no 4 s timeout)
            assert pump(lambda: card_a.overlay.visible and card_b.overlay.visible)
            assert pump(lambda: card_a.overlay.choice is not None and card_b.overlay.choice is not None)
            assert card_a.overlay.choice.key == "coding" and card_b.overlay.choice.key == "waiting"
            assert card_a.overlay.sticky and card_a.overlay.hold_source is None

            # GIF rotation: on by default (every 120 s); 1 s here, then off again.
            assert card_a.rotate_source is not None
            before = card_a.sticker_request
            widget.update_setting("AI_STATUS_STICKER_ROTATE_SECONDS", "1")
            assert pump(lambda: card_a.sticker_request > before, 4), "a fresh GIF is requested"
            widget.update_setting("AI_STATUS_STICKER_ROTATE_SECONDS", "0")
            assert pump(lambda: card_a.sticker_debounce is None and card_a.overlay.phase == "shown", 4)
            assert card_a.rotate_source is None
            before = card_a.sticker_request
            card_a.show_another_gif()
            assert card_a.sticker_request == before + 1
            assert pump(lambda: card_a.sticker_debounce is None and card_a.overlay.phase == "shown", 4)

            # The bubble says what the agent is doing now: a new activity swaps the text only.
            before = card_a.sticker_request
            gif_before = card_a.overlay.choice.label
            editing = session("a", "coding")
            editing["activity"] = {"type": "edit", "target": "stickers.py", "phase": "pre"}
            sync([editing, session("b", "waiting", "codex")])
            assert card_a.sticker_request == before, "same GIF, no new pick"
            assert "stickers.py" in card_a.overlay.choice.bubble, card_a.overlay.choice.bubble
            assert card_a.overlay.choice.label == gif_before

            # After a few seconds the bubble goes back to a funny line (timer fired by hand).
            card_a.on_activity_bubble_done()
            assert card_a.overlay.choice.bubble in module["stickers"].DEFAULT_BUBBLES["coding"]

            # coding <-> analyzing on the same task: no GIF reshuffle, just the colour.
            post_edit = session("a", "analyzing")
            post_edit["activity"] = {"type": "edit", "target": "stickers.py", "phase": "post"}
            sync([post_edit, session("b", "waiting", "codex")])
            assert card_a.sticker_request == before
            assert card_a.overlay.color == module["stickers"].STICKER_COLORS["analyzing"]

            # A new topic (tests) gets a new GIF, but not more often than every 15 s.
            testing = session("a", "coding")
            testing["activity"] = {"type": "command", "target": "Run the tests", "phase": "pre"}
            sync([testing, session("b", "waiting", "codex")])
            assert card_a.sticker_request == before, "too soon after the last GIF"
            assert "Run the tests" in card_a.overlay.choice.bubble
            card_a.last_pick_at = 0.0
            sync([testing, session("b", "waiting", "codex")])
            assert card_a.sticker_request == before + 1 and card_a.sticker_topic == "testing"
            assert pump(lambda: card_a.sticker_debounce is None and card_a.overlay.phase == "shown", 4)
            assert "Run the tests" in card_a.overlay.choice.bubble, "new GIF keeps the fresh task bubble"
            back = session("a", "coding")
            sync([back, session("b", "waiting", "codex")])

            # docked cards stack under the widget in first-seen order
            for _ in range(30):
                GLib.MainContext.default().iteration(False)
            widget.layout_cards()
            assert card_a.floating is False and card_b.floating is False

            # same sticker status → same GIF; done → sticker tucks away, card stays
            first_choice = card_a.overlay.choice
            sync([session("a", "command"), session("b", "waiting", "codex")])
            assert card_a.sticker_debounce is None and card_a.overlay.choice is first_choice
            sync([session("a", "done"), session("b", "waiting", "codex")])
            assert card_a.overlay.phase == "out" and widget.session_cards["a"] is card_a

            # a dragged (floating) card remembers its position; docking forgets it
            card_b.floating = True
            widget.save_card_position("b", 40, 500)
            saved = json.loads((config_dir / "session_windows.json").read_text())
            assert saved["b"]["x"] == 40 and saved["b"]["y"] == 500
            widget.dock_card("b")
            assert card_b.floating is False
            assert "b" not in json.loads((config_dir / "session_windows.json").read_text())

            # Serious mode hides every card sticker; switching it off brings them back
            widget.update_setting("AI_STATUS_SERIOUS_MODE", "true")
            assert not card_b.overlay.visible or card_b.overlay.phase == "out"
            widget.update_setting("AI_STATUS_SERIOUS_MODE", "false")
            assert card_b.sticker_debounce is not None

            # a session that disappears closes its window
            sync([session("b", "waiting", "codex")])
            assert list(widget.session_cards) == ["b"] and card_a.closed

            # the classic list layout closes all session windows
            widget.update_setting("AI_STATUS_SESSION_WINDOWS", "false")
            assert widget.session_cards == {} and card_b.closed
            widget.destroy()
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            shutil.copytree(ROOT / "assets", data_dir)
            config_dir = Path(directory) / "config"
            environment = {key: value for key, value in os.environ.items() if not key.startswith("AI_STATUS_")}
            environment.update({
                "AI_STATUS_ENV_FILE": str(Path(directory) / ".env"),
                "AI_STATUS_CACHE_DIR": str(Path(directory) / "cache"),
                "AI_STATUS_CONFIG_DIR": str(config_dir),
                "AI_STATUS_DATA_DIR": str(data_dir),
            })
            completed = subprocess.run(
                ["xvfb-run", "-a", sys.executable, "-c", probe, str(config_dir)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
