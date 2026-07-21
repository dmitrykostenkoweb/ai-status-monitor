## 1. Usage Data Model and Parsers

- [x] 1.1 Add standard-library unit tests and fixtures for normalized usage records, Claude `five_hour`/`seven_day` responses, and Codex weekly `token_count` rate-limit events.
- [x] 1.2 Implement normalized provider/window records and strict percentage/reset timestamp validation in `bin/ai_agent_status_lib/usage_limits.py` until the parser tests pass.
- [x] 1.3 Add tests proving malformed newest Codex records are skipped and recent-file/line scanning remains bounded.
- [x] 1.4 Implement Codex home discovery and newest-valid weekly window collection from local session JSONL files.

## 2. Claude Collection and Secure Caching

- [x] 2.1 Add tests for missing/unreadable Claude credentials, request timeouts, malformed responses, and exception/cache output that must not contain credential material.
- [x] 2.2 Implement in-memory Claude OAuth token loading and the bounded authenticated usage request without logging or persisting credentials.
- [x] 2.3 Add tests for atomic cache replacement, provider-specific merging, stale fallback, and invalidation after a window reset.
- [x] 2.4 Implement `usage_limits.json` serialization and provider fallback rules using only normalized non-secret fields.
- [x] 2.5 Add and satisfy orchestration tests showing a failure from one provider does not discard a successful result from the other.

## 3. Widget Usage Section

- [x] 3.1 Add deterministic demo states for current, refreshing, stale, partially unavailable, and fully unavailable usage data.
- [x] 3.2 Build the compact `Usage limits` GTK section with Claude `5h`/`Weekly`, Codex `Weekly`, percentage indicators, local reset times, stale labels, and unavailable states.
- [x] 3.3 Add one shared `↻` button and single-flight background refresh lifecycle with a 120-second automatic timer, bounded provider work, `GLib.idle_add` UI updates, and disabled-button feedback while refreshing.
- [x] 3.4 Keep usage rendering independent from session-body signatures and verify idle, active, waiting, sound, and terminal-switch behavior remain unchanged.

## 4. Packaging, Documentation, and Verification

- [x] 4.1 Verify `install.sh` deploys the new shared module through the existing recursive library copy and make only packaging changes required by that check.
- [x] 4.2 Document displayed limits, refresh behavior, data sources, credential handling, offline behavior, and troubleshooting in `README.md` and contributor guidance where relevant.
- [x] 4.3 Run the unit suite, Python syntax compilation, Claude and Codex hook simulations in a temporary cache, `git diff --check`, and strict OpenSpec validation.
- [x] 4.4 Run widget demo/manual smoke checks for refresh responsiveness and all usage states, then inspect monitor cache and logs to confirm no OAuth token or raw credential object was persisted.

## 5. Provider-Branded Usage Layout

- [x] 5.1 Add presentation tests for provider grouping and green/orange/red color thresholds, including the 60% and 85% boundaries.
- [x] 5.2 Render one provider block per Claude and Codex logo, with Claude `5h` and `Weekly` bars stacked beside its logo and Codex `Weekly` beside its logo.
- [x] 5.3 Apply neutral progress tracks and threshold-based fill classes without changing stale, unavailable, reset-time, or shared-refresh behavior.
- [x] 5.4 Run unit, syntax, OpenSpec, demo, installation, and live-widget smoke checks for the redesigned section.

## 6. Clickable Provider Refresh Controls

- [x] 6.1 Add tests proving a targeted refresh invokes only the selected provider collector and preserves the other provider's cached records.
- [x] 6.2 Remove the visible usage title and shared refresh button, then vertically center each logo against its provider's complete limit stack.
- [x] 6.3 Make provider logos accessible refresh controls and add smooth rotation for only the active provider, or both logos during automatic refresh, while preserving global single-flight behavior.
- [x] 6.4 Update documentation and run unit, syntax, OpenSpec, demo, installation, live-widget, config-preservation, and credential-leak checks.
