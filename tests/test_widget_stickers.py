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


class WidgetStickerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("xvfb-run"), "xvfb-run is required")
    def test_status_changes_pop_stickers_and_serious_mode_silences_them(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys
            import time
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="widget_stickers_smoke")
            GLib = module["GLib"]
            widget = module["StatusWidget"](demo=True)
            overlay = widget.sticker_overlay
            assert overlay is not None

            def pump(condition, seconds=3.0):
                deadline = time.monotonic() + seconds
                context = GLib.MainContext.default()
                while time.monotonic() < deadline:
                    if condition():
                        return True
                    context.iteration(False)
                    time.sleep(0.01)
                return condition()

            def session(kind, sid="claude:app"):
                return {"id": sid, "kind": kind}

            widget.update_stickers([session("thinking")])
            assert widget.sticker_debounce is None, "first pass only primes"

            widget.update_stickers([session("coding")])
            assert pump(lambda: overlay.visible)
            assert overlay.choice.key == "coding"
            assert overlay.choice.source == "local", overlay.choice
            assert overlay.choice.image.name == "keys.gif"
            assert overlay.sticky is False and overlay.hold_source is not None

            widget.update_stickers([session("waiting")])
            assert pump(lambda: overlay.choice is not None and overlay.choice.key == "waiting")
            assert overlay.sticky is True and overlay.hold_source is None
            assert overlay.choice.source == "placeholder"

            widget.update_stickers([session("coding")])
            assert overlay.phase == "out", overlay.phase
            assert pump(lambda: overlay.choice is not None and overlay.choice.key == "coding" and overlay.phase != "out")

            widget.update_stickers([session("command")])  # same sticker key → no new sticker
            assert widget.sticker_debounce is None

            widget.update_setting("AI_STATUS_SERIOUS_MODE", "true")
            assert not overlay.visible
            widget.update_stickers([session("done")])
            assert widget.sticker_debounce is None
            widget.update_setting("AI_STATUS_SERIOUS_MODE", "false")

            widget.update_setting("AI_STATUS_KLIPY_API_KEY", "super-secret-key")
            assert widget.sticker_source.klipy is not None
            log_text = Path(sys.argv[1], "widget.log").read_text()
            assert "super-secret-key" not in log_text
            assert "AI_STATUS_KLIPY_API_KEY=(hidden)" in log_text
            widget.update_setting("AI_STATUS_KLIPY_API_KEY", "")
            assert widget.sticker_source.klipy is None

            widget.note_usage_limits({"providers": {"claude": [
                {"window": "5h", "used_percent": 93.0, "resets_at": "2030-01-01T00:00:00+00:00"},
            ]}}, trigger=True)
            assert pump(lambda: overlay.choice is not None and overlay.choice.key == "limit")
            debounce_before = widget.sticker_request
            widget.note_usage_limits({"providers": {"claude": [
                {"window": "5h", "used_percent": 95.0, "resets_at": "2030-01-01T00:00:00+00:00"},
            ]}}, trigger=True)
            assert widget.sticker_request == debounce_before, "same limit window pops only once"

            widget.destroy()
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            shutil.copytree(ROOT / "assets", data_dir)
            (data_dir / "gifs" / "coding").mkdir(parents=True)
            shutil.copy(ROOT / "assets" / "gifs" / "analyzing" / "eyes.png", data_dir / "gifs" / "coding" / "keys.gif")
            cache_dir = Path(directory) / "cache"
            environment = {key: value for key, value in os.environ.items() if not key.startswith("AI_STATUS_")}
            environment.update({
                "AI_STATUS_ENV_FILE": str(Path(directory) / ".env"),
                "AI_STATUS_CACHE_DIR": str(cache_dir),
                "AI_STATUS_CONFIG_DIR": str(Path(directory) / "config"),
                "AI_STATUS_DATA_DIR": str(data_dir),
            })
            completed = subprocess.run(
                ["xvfb-run", "-a", sys.executable, "-c", probe, str(cache_dir)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


    @unittest.skipUnless(shutil.which("xvfb-run"), "xvfb-run is required")
    def test_window_hints_target_own_window_and_hover_survives_spurious_leaves(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys
            import time
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="widget_hints_smoke")
            GLib = module["GLib"]
            stickers = module["stickers"]
            widget = module["StatusWidget"](demo=True)
            widget.show_all()
            context = GLib.MainContext.default()
            for _ in range(50):
                context.iteration(False)

            # wmctrl must address this widget by window id, never by a title substring
            # that a terminal ("... AI Agents Status ...") could also match.
            calls = []
            module["shutil"].which = lambda name: "/usr/bin/" + name
            module["subprocess"].run = lambda args, **kwargs: calls.append(args)
            assert widget.apply_wmctrl_hints() is True
            window_id = widget.own_window_id()
            assert window_id and window_id.startswith("0x"), window_id
            assert calls[-1][1:4] == ["-i", "-r", window_id], calls[-1]

            # Hover: a leave event while the pointer is still on the row must not tuck.
            overlay = widget.sticker_overlay
            choice = stickers.StickerChoice("coding", None, "hi", "placeholder")
            widget.last_stickers["claude:app"] = choice
            widget.sticker_owner = "claude:app"
            widget.sticker_hovered = "claude:app"
            overlay.present_sticker(choice, sticky=False, hold_ms=None)
            widget.pointer_inside = lambda _box: True
            class Crossing:
                detail = module["Gdk"].NotifyType.NONLINEAR
            widget.on_row_leave(widget, Crossing(), "claude:app")
            assert overlay.phase == "in" and widget.sticker_hovered == "claude:app"

            # After a row rebuild the hover is re-checked; pointer gone → tuck.
            widget.row_hover_boxes = {}
            widget.verify_hover()
            assert overlay.phase == "out" and widget.sticker_hovered is None
            widget.destroy()
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


if __name__ == "__main__":
    unittest.main()
