# Codex Live Usage Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch current Codex weekly usage without requiring an interactive Codex session.

**Architecture:** Add an isolated app-server protocol parser and short-lived subprocess collector in the existing usage module. Make it the primary Codex source while retaining the bounded session JSONL collector as fallback.

**Tech Stack:** Python 3 standard library, JSONL over subprocess stdio, `unittest`.

## Global Constraints

- Do not read, copy, log, or cache Codex OAuth credentials.
- Bound the app-server call with a timeout.
- Preserve session JSONL and normalized cache fallbacks.
- Do not change Claude collection or GTK rendering.
- Do not create a commit.

---

### Task 1: Add the live Codex app-server source

**Files:**
- Modify: `bin/ai_agent_status_lib/usage_limits.py`
- Test: `tests/test_usage_limits.py`

**Interfaces:**
- Produces: `parse_codex_app_server_output(output: str, fetched_at: datetime | None = None) -> list[UsageLimit]`
- Produces: `collect_codex_live_usage(*, fetched_at: datetime | None = None, timeout: float = 5.0, runner: Any = subprocess.run) -> list[UsageLimit]`
- Changes: `collect_codex_usage(..., live_collector: Callable[[], list[UsageLimit]] | None = None) -> list[UsageLimit]`

- [x] **Step 1: Write failing parser and precedence tests**

Add tests that provide notification lines, the initialize response, and a matching request response containing camelCase app-server fields. Assert that `usedPercent: 2`, `windowDurationMins: 10080`, and `resetsAt` normalize correctly. Add a collector test where live usage is `2%` and session JSONL is `25%`; assert that `2%` wins.

- [x] **Step 2: Run focused tests and verify RED**

Run: `python3 -m unittest tests.test_usage_limits.CodexAppServerTests tests.test_usage_limits.CodexCollectorTests -v`

Expected: import or assertion failures because the new parser/collector behavior does not exist.

- [x] **Step 3: Implement the minimal app-server client**

Import `subprocess`. Parse only JSON objects whose `id` matches the rate-limit request. Convert app-server camelCase fields to the existing snake_case parser shape. Run `codex app-server --stdio` with three JSONL messages: `initialize`, `initialized`, and `account/rateLimits/read`; use captured text output, a five-second timeout, and no shell. Return an empty list on OS, subprocess, timeout, protocol, or validation failure.

- [x] **Step 4: Make live data primary with session fallback**

At the start of `collect_codex_usage`, call the injected/default live collector. Return a valid live result immediately. If it returns no valid limit or raises, continue through the unchanged bounded session JSONL search.

- [x] **Step 5: Run focused tests and verify GREEN**

Run: `python3 -m unittest tests.test_usage_limits.CodexAppServerTests tests.test_usage_limits.CodexCollectorTests -v`

Expected: all focused tests pass.

- [x] **Step 6: Run full verification**

Run:

```bash
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget \
  bin/ai-agent-status-doctor bin/ai_agent_status_lib/*.py
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: syntax checks exit zero, all tests pass, and `git diff --check` prints nothing.

- [x] **Step 7: Verify the live account result without persisting it**

Run `collect_codex_live_usage()` through `PYTHONPATH=bin` and print only the normalized limit. Confirm it returns the current weekly window without starting an interactive conversation or exposing credentials.

- [x] **Step 8: Update user documentation**

Change `README.md` so the Codex source is documented as the installed CLI app-server with recent session metadata as compatibility fallback. Run `git diff --check` again.
