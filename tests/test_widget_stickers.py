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


class WidgetStickerTests(unittest.TestCase):
    @unittest.skipUnless(GUI_TESTS_AVAILABLE, "xvfb-run and PySide6 are required")
    def test_status_changes_pop_stickers_and_serious_mode_silences_them(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys
            import time
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="widget_stickers_smoke")
            process_events = module["process_events"]
            widget = module["StatusWidget"](demo=True)
            overlay = widget.sticker_overlay
            assert overlay is not None

            def pump(condition, seconds=3.0):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if condition():
                        return True
                    process_events()
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

            # In-app "get a free key" guide: a failed check saves nothing, a passing one saves.
            widget.open_settings()
            widget.open_klipy_guide(widget.settings_window)
            guide = widget.klipy_guide
            assert guide is not None
            guide.on_verified("bad-key", "invalid")
            assert widget.klipy_api_key == ""
            guide.on_verified("good-key", "ok")
            assert widget.klipy_api_key == "good-key" and widget.sticker_source.klipy is not None
            assert widget.settings_window.klipy_entry.text() == "good-key"
            assert "works" in guide.status.text()
            guide.close()
            assert widget.klipy_guide is None
            # A check that finishes after the guide was closed still saves a good key.
            process_events(0.1)
            guide.on_verified("late-key", "ok")
            assert widget.klipy_api_key == "late-key"
            widget.settings_window.close()
            widget.update_setting("AI_STATUS_KLIPY_API_KEY", "")

            # KLIPY media arrives as in-memory bytes and still animates.
            import base64
            gif = base64.b64decode("R0lGODlhBAAEAPAAAP8AAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQACgAAACH/C0ltYWdlTWFnaWNrDmdhbW1hPTAuNDU0NTQ1ACwAAAAABAAEAAACBISPCQUAIfkEAAoAAAAh/wtJbWFnZU1hZ2ljaw5nYW1tYT0wLjQ1NDU0NQAsAAAAAAQABACAAAD/AAAAAgSEjwkFADs=")
            from_klipy = module["stickers"].StickerChoice("done", None, "ta-da", "klipy", data=gif, title="party-1")
            overlay.present_sticker(from_klipy, sticky=True)
            assert overlay.movie is not None and overlay.frame is not None
            assert from_klipy.label == "party-1"

            # Polaroid geometry: its box ends 14 px right of the card and 4 px below its top.
            overlay.place_for_card(500, 300)
            box = overlay.polaroid_rect()
            assert (overlay.x() + box.right(), overlay.y() + box.bottom()) == (514, 304)
            scale, opacity = module["pop_transform"](0.0)
            assert abs(scale - 0.6) < 1e-6 and opacity == 0.0
            assert max(module["pop_transform"](step / 100)[0] for step in range(101)) > 1.0
            assert module["pop_transform"](1.0) == (1.0, 1.0)
            assert overlay.sfx in module["stickers"].STICKER_SFX["done"]

            widget.note_usage_limits({"providers": {"claude": [
                {"window": "5h", "used_percent": 93.0, "resets_at": "2030-01-01T00:00:00+00:00"},
            ]}}, trigger=True)
            assert pump(lambda: overlay.choice is not None and overlay.choice.key == "limit")
            debounce_before = widget.sticker_request
            widget.note_usage_limits({"providers": {"claude": [
                {"window": "5h", "used_percent": 95.0, "resets_at": "2030-01-01T00:00:00+00:00"},
            ]}}, trigger=True)
            assert widget.sticker_request == debounce_before, "same limit window pops only once"

            widget.shutdown()
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


    @unittest.skipUnless(GUI_TESTS_AVAILABLE, "xvfb-run and PySide6 are required")
    def test_window_hints_target_own_window_and_hover_survives_spurious_leaves(self) -> None:
        probe = textwrap.dedent(
            """
            import runpy
            import sys
            import time
            from pathlib import Path

            sys.path.insert(0, "bin")
            module = runpy.run_path("bin/ai-agent-status-widget", run_name="widget_hints_smoke")
            process_events = module["process_events"]
            stickers = module["stickers"]
            widget = module["StatusWidget"](demo=True)
            widget.show()
            process_events(0.5)

            # wmctrl must address this widget by window id, never by a title substring
            # that a terminal ("... AI Agents Status ...") could also match.
            calls = []
            real_run = module["subprocess"].run
            real_which = module["shutil"].which
            module["shutil"].which = lambda name: "/usr/bin/" + name
            module["subprocess"].run = lambda args, **kwargs: calls.append(args)
            assert widget.apply_wmctrl_hints() is True
            window_id = widget.own_window_id()
            assert window_id and window_id.startswith("0x"), window_id
            assert calls[-1][1:4] == ["-i", "-r", window_id], calls[-1]
            module["subprocess"].run = real_run

            # Without wmctrl, libX11 gives the window GTK's shape: UTILITY, not transient.
            assert widget.apply_window_hints() is True
            assert widget.x11 is not None
            if real_which("xprop"):
                props = real_run(["xprop", "-id", window_id, "WM_TRANSIENT_FOR", "_NET_WM_WINDOW_TYPE"],
                                 capture_output=True, text=True).stdout
                assert "WM_TRANSIENT_FOR:  not found" in props, props
                assert "_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_UTILITY" in props, props

            # Hover: a leave event while the pointer is still on the row must not tuck.
            overlay = widget.sticker_overlay
            choice = stickers.StickerChoice("coding", None, "hi", "placeholder")
            widget.last_stickers["claude:app"] = choice
            widget.sticker_owner = "claude:app"
            widget.sticker_hovered = "claude:app"
            overlay.present_sticker(choice, sticky=False, hold_ms=None)
            widget.pointer_inside = lambda _box: True
            widget.on_row_leave(widget, "claude:app")
            assert overlay.phase == "in" and widget.sticker_hovered == "claude:app"

            # Leave events sent while the rows are being rebuilt are left to verify_hover().
            widget.pointer_inside = lambda _box: False
            widget.rebuilding = True
            widget.on_row_leave(widget, "claude:app")
            assert overlay.phase == "in" and widget.sticker_hovered == "claude:app"
            widget.rebuilding = False

            # After a row rebuild the hover is re-checked; pointer gone → tuck.
            widget.row_hover_boxes = {}
            widget.verify_hover()
            assert overlay.phase == "out" and widget.sticker_hovered is None
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


if __name__ == "__main__":
    unittest.main()
