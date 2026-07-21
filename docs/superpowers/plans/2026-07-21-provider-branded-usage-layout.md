# Provider-Branded Usage Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace generic usage rows with provider-branded Claude and Codex blocks whose progress fills change from green to orange to red as utilization rises.

**Architecture:** Keep provider grouping and threshold selection as pure presentation helpers in `usage_limits.py`, then make the GTK widget consume that model. Reuse the logos already loaded for session rows and preserve the existing cache, refresh lifecycle, stale state, and unavailable behavior.

**Tech Stack:** Python 3, GTK3/PyGObject, GTK CSS, standard-library `unittest`, OpenSpec.

## Global Constraints

- Claude displays stacked `5h` and `Weekly` limits; Codex displays one `Weekly` limit.
- Progress fill is green below 60%, orange from 60% through 84%, and red from 85% through 100%.
- The unfilled progress track stays neutral.
- Existing stale, unavailable, reset-time, automatic-refresh, and global single-flight behavior must not change.
- Reuse `assets/anthropic-logo.png` and `assets/openai-logo.svg`; add no dependencies or new assets.
- Work in the current checkout and do not create a commit unless the user asks.

---

### Task 1: Pure Provider Presentation Model

**Files:**
- Modify: `tests/test_usage_limits.py`
- Modify: `bin/ai_agent_status_lib/usage_limits.py`

**Interfaces:**
- Consumes: `build_usage_rows(snapshot, *, now=None, local_timezone=None) -> list[UsageDisplayRow]`
- Produces: `usage_color_class(used_percent: object) -> str`
- Produces: `build_usage_groups(snapshot, *, now=None, local_timezone=None) -> list[UsageDisplayGroup]`

- [x] **Step 1: Write failing threshold tests**

Add table-driven assertions proving `0` and `59.9` return `usage-green`, `60` and `84.9` return `usage-orange`, and `85` and `100` return `usage-red`. Add safe fallback cases for non-numeric input.

```python
def test_assigns_progress_color_at_threshold_boundaries(self) -> None:
    cases = ((0, "usage-green"), (59.9, "usage-green"),
             (60, "usage-orange"), (84.9, "usage-orange"),
             (85, "usage-red"), (100, "usage-red"))
    for value, expected in cases:
        with self.subTest(value=value):
            self.assertEqual(usage_color_class(value), expected)
```

- [x] **Step 2: Write a failing provider-group test**

Build a snapshot with reversed Claude input order and assert the result has two groups in `claude`, `codex` order, Claude windows in `5h`, `Weekly` order, and a color class on every available row.

```python
groups = build_usage_groups(snapshot, now=FETCHED_AT, local_timezone=timezone.utc)
self.assertEqual([group["provider_key"] for group in groups], ["claude", "codex"])
self.assertEqual([row["window"] for row in groups[0]["rows"]], ["5h", "Weekly"])
self.assertEqual(groups[0]["rows"][0]["color_class"], "usage-orange")
```

- [x] **Step 3: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.test_usage_limits.UsagePresentationTests -v`

Expected: import failures for `usage_color_class` and `build_usage_groups`.

- [x] **Step 4: Implement the minimal presentation helpers**

Add `color_class` to `UsageDisplayRow`, define a `UsageDisplayGroup` containing `provider`, `provider_key`, and `rows`, and group the existing normalized rows in fixed provider order. Unavailable rows receive an empty color class; valid rows call `usage_color_class`.

```python
def usage_color_class(used_percent: object) -> str:
    if isinstance(used_percent, bool) or not isinstance(used_percent, (int, float)):
        return ""
    if float(used_percent) >= 85.0:
        return "usage-red"
    if float(used_percent) >= 60.0:
        return "usage-orange"
    return "usage-green"
```

- [x] **Step 5: Run presentation and full unit suites**

Run `python3 -m unittest tests.test_usage_limits.UsagePresentationTests -v`, then `python3 -m unittest discover -s tests -v`.

Expected: all tests pass.

### Task 2: GTK Provider Blocks and Threshold Styling

**Files:**
- Modify: `bin/ai-agent-status-widget`

**Interfaces:**
- Consumes: `build_usage_groups(...)`, each group with `provider_key` and ordered `rows`
- Consumes: `self.logo_pixbufs[provider_key]`
- Preserves: `render_usage_limits()`, `start_usage_refresh()`, and `usage_refresh_tick()` behavior

- [x] **Step 1: Replace generic row CSS with provider-block CSS**

Add compact styles for `#usageProviderBlock`, `#usageProviderLogo`, `#usageLimitStack`, `#usageLimit`, and a neutral `#usageProgress trough`. Style `.usage-green progress`, `.usage-orange progress`, and `.usage-red progress` with green `#4ADE80`, orange `#F59E0B`, and red `#FB7060`.

- [x] **Step 2: Render the provider identity once per block**

In `render_usage_limits`, iterate over `build_usage_groups`. Create one horizontal block, place a 22px logo container on the left, and reuse the provider pixbuf scaled for the block. Keep a text fallback when an asset is missing.

```python
for group in usage_limits.build_usage_groups(self.usage_snapshot):
    provider_key = str(group["provider_key"])
    block = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    block.set_name("usageProviderBlock")
```

- [x] **Step 3: Stack labeled limit bars beside each logo**

For every group row, render a label/percentage line, neutral-track progress bar, and reset text. Add the row's `color_class` to the progress style context. For unavailable providers, keep the logo and show `Unavailable` without a bar. For stale rows, preserve the visible stale indication and the utilization color.

- [x] **Step 4: Check syntax and run demo states**

Run `python3 -m py_compile bin/ai-agent-status-widget bin/ai_agent_status_lib/*.py`, then `timeout 12s bin/ai-agent-status-widget --demo`.

Expected: no syntax or GTK errors; Claude uses two stacked bars and Codex one in all demo states.

### Task 3: Documentation, Installation, and Completion Checks

**Files:**
- Modify: `README.md`
- Modify: `openspec/changes/add-usage-limit-monitoring/tasks.md`

**Interfaces:**
- Consumes: completed provider-block widget
- Produces: installed widget and checked-off OpenSpec tasks 5.1–5.4

- [x] **Step 1: Update the usage-layout documentation**

State that provider logos identify grouped limits and document the exact green `<60%`, orange `60–84%`, and red `>=85%` thresholds without changing the data-source or credential sections.

- [x] **Step 2: Run repository verification**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget \
  bin/ai-agent-status-doctor bin/ai_agent_status_lib/*.py
AI_STATUS_CACHE_DIR="$(mktemp -d)" bin/ai-agent-status-hook --agent claude --test
AI_STATUS_CACHE_DIR="$(mktemp -d)" bin/ai-agent-status-hook --agent codex --test
openspec validate add-usage-limit-monitoring
git diff --check
```

Expected: every command exits 0.

- [x] **Step 3: Install and validate the live widget**

Run `./install.sh`, then `~/.local/bin/ai-agent-status-doctor`. Restart the widget through its existing launcher and verify `~/.cache/ai-cli-status-monitor/usage_limits.json` remains non-secret and readable.

Expected: doctor checks pass, the widget stays responsive, and one shared refresh updates both branded provider blocks.

- [x] **Step 4: Mark the OpenSpec redesign tasks complete**

Change tasks 5.1–5.4 to `[x]`, rerun `openspec validate add-usage-limit-monitoring`, and confirm `openspec instructions apply --change add-usage-limit-monitoring --json` reports `all_done`.

### Task 4: Clickable Provider-Specific Refresh Logos

**Files:**
- Modify: `tests/test_usage_limits.py`
- Modify: `bin/ai_agent_status_lib/usage_limits.py`
- Modify: `bin/ai-agent-status-widget`
- Modify: `README.md`
- Modify: `openspec/changes/add-usage-limit-monitoring/tasks.md`

**Interfaces:**
- Extends: `refresh_usage(..., provider_keys: tuple[str, ...] = ("claude", "codex"))`
- Produces: `RotatingProviderLogo(Gtk.DrawingArea)` with `angle: float`
- Changes: `start_usage_refresh(provider_key: str | None = None, *_args) -> bool`
- Preserves: one global refresh in flight and the combined normalized cache

- [x] **Step 1: Write and run a failing targeted-refresh test**

Seed both providers in a temporary cache, call `refresh_usage` with `provider_keys=("claude",)`, and assert the Claude collector runs once, the Codex collector never runs, and the cached Codex record is retained.

```python
snapshot = refresh_usage(
    cache,
    now=FETCHED_AT,
    provider_keys=("claude",),
    claude_collector=successful_claude,
    codex_collector=unexpected_codex,
)
self.assertEqual(calls, ["claude"])
self.assertEqual(snapshot["providers"]["codex"][0]["used_percent"], 7.0)
```

Run `python3 -m unittest tests.test_usage_limits.UsageRefreshTests.test_targeted_refresh_preserves_other_provider -v`.

Expected: FAIL because `refresh_usage` does not accept `provider_keys`.

- [x] **Step 2: Implement and verify targeted collection**

Add `provider_keys` to `refresh_usage`, filter it to known collector keys, invoke only selected collectors, and persist the selected result together with untouched cached provider records. Run the focused test and the complete unit suite; expect all tests to pass.

- [x] **Step 3: Remove the usage header and add rotating logo controls**

Delete the `Usage limits` header and `↻` button. Add a `RotatingProviderLogo` drawing area that rotates its pixbuf around the widget center with Cairo. Wrap it in a relief-free `Gtk.Button`, center it vertically against the provider stack, attach a provider-specific tooltip, and connect it to `start_usage_refresh(provider_key)`.

```python
button.connect("clicked", lambda _button, key=provider_key: self.start_usage_refresh(key))
button.set_valign(Gtk.Align.CENTER)
```

- [x] **Step 4: Track provider animation state and preserve single-flight**

Use `usage_refreshing_providers: set[str]`. A manual click sets one provider; automatic refresh sets both. Disable both logo buttons while any refresh runs, rotate only active logo widgets in `tick_animation`, and clear state on success or failure.

- [x] **Step 5: Update docs, verify, install, and mark OpenSpec complete**

Document clickable provider logos and remove references to the shared button. Run the full unit suite, `py_compile`, hook simulations, OpenSpec validation, `git diff --check`, and a demo visual check. Run `./install.sh`, restart the live widget, run doctor, verify config preservation and credential absence, mark tasks 6.1–6.4 complete, and confirm OpenSpec reports `all_done`.
