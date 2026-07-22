# Smooth Provider Refresh Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render provider-logo refresh rotation at approximately 30 FPS while leaving every other widget animation at its current cadence.

**Architecture:** Keep the existing 200 ms `tick_animation` loop unchanged for general widget effects. Add a dedicated, single-instance 33 ms GLib timer owned by `StatusWidget`; it advances and redraws only provider logos selected for the active refresh and is stopped and reset on every completion path.

**Tech Stack:** Python 3, GTK3/PyGObject, GLib timers, Cairo drawing, standard-library `unittest`, Xvfb for GTK smoke coverage.

## Global Constraints

- The provider refresh animation interval is 33 ms, approximately 30 FPS.
- Preserve the existing perceived rotation speed rather than multiplying it by the higher frame rate.
- Manual refresh animates only the selected provider; automatic refresh animates both providers.
- Keep the existing 200 ms general animation timer unchanged.
- Maintain at most one provider-animation GLib source and clean it up after success or failure.

---

### Task 1: Dedicated provider refresh animation lifecycle

**Files:**
- Create: `tests/test_widget_animation.py`
- Modify: `bin/ai-agent-status-widget:38-44, 300-315, 1084-1191`

**Interfaces:**
- Consumes: `StatusWidget.usage_refreshing`, `StatusWidget.usage_refreshing_providers`, and `StatusWidget.usage_logo_widgets`.
- Produces: `USAGE_ANIMATION_INTERVAL_MS: int`, `USAGE_ROTATION_RADIANS_PER_TICK: float`, `StatusWidget.start_usage_animation() -> None`, `StatusWidget.stop_usage_animation() -> None`, and `StatusWidget.tick_usage_animation() -> bool`.

- [ ] **Step 1: Write the failing GTK lifecycle smoke test**

Create `tests/test_widget_animation.py`. Run a small probe under `xvfb-run` so the normal test suite can verify GTK behavior without using the user's desktop:

```python
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WidgetAnimationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("xvfb-run"), "xvfb-run is required")
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
            widget.destroy()
            """
        )
        completed = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", probe],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run: `python3 -m unittest tests.test_widget_animation -v`

Expected: FAIL because `USAGE_ANIMATION_INTERVAL_MS` and the dedicated animation lifecycle do not exist yet.

- [ ] **Step 3: Add the dedicated 30 FPS animation lifecycle**

In `bin/ai-agent-status-widget`, add constants that preserve the current speed of `0.36 radians / 200 ms`:

```python
USAGE_ANIMATION_INTERVAL_MS = 33
USAGE_ROTATION_RADIANS_PER_TICK = 0.36 * USAGE_ANIMATION_INTERVAL_MS / 200
```

Initialize the timer state in `StatusWidget.__init__`:

```python
self.usage_animation_source_id: int | None = None
self.usage_animation_angle = 0.0
```

After `render_usage_limits()` in `start_usage_refresh`, call `self.start_usage_animation()`. Before clearing refresh state in both `on_usage_result` and `finish_demo_usage_refresh`, call `self.stop_usage_animation()`.

Add the lifecycle methods:

```python
def start_usage_animation(self) -> None:
    if self.usage_animation_source_id is not None:
        return
    self.usage_animation_angle = 0.0
    self.usage_animation_source_id = GLib.timeout_add(
        USAGE_ANIMATION_INTERVAL_MS,
        self.tick_usage_animation,
    )

def stop_usage_animation(self) -> None:
    source_id = self.usage_animation_source_id
    self.usage_animation_source_id = None
    if source_id is not None:
        GLib.source_remove(source_id)
    self.usage_animation_angle = 0.0
    for provider_key in self.usage_refreshing_providers:
        logo = self.usage_logo_widgets.get(provider_key)
        if logo is not None:
            logo.angle = 0.0
            logo.queue_draw()

def tick_usage_animation(self) -> bool:
    if not self.usage_refreshing or not self.usage_refreshing_providers:
        self.usage_animation_source_id = None
        return False
    self.usage_animation_angle = (
        self.usage_animation_angle + USAGE_ROTATION_RADIANS_PER_TICK
    ) % (2 * math.pi)
    for provider_key in self.usage_refreshing_providers:
        logo = self.usage_logo_widgets.get(provider_key)
        if logo is not None:
            logo.angle = self.usage_animation_angle
            logo.queue_draw()
    return True
```

Remove the provider-logo rotation block from the general `tick_animation` method.

- [ ] **Step 4: Run focused verification**

Run: `python3 -m unittest tests.test_widget_animation -v`

Expected: `test_provider_refresh_uses_dedicated_30_fps_timer_and_resets ... ok`.

- [ ] **Step 5: Run repository verification**

Run:

```bash
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget \
  bin/ai-agent-status-doctor bin/ai_agent_status_lib/*.py
python3 -m unittest discover -s tests -v
timeout 5s xvfb-run -a bin/ai-agent-status-widget --demo
git diff --check
```

Expected: compilation succeeds, all unit tests pass, the demo exits only because of the five-second timeout without GTK errors, and `git diff --check` prints no errors.

- [ ] **Step 6: Commit the implementation**

```bash
git add bin/ai-agent-status-widget tests/test_widget_animation.py
git commit -m "fix(widget): smooth provider refresh animation"
```
