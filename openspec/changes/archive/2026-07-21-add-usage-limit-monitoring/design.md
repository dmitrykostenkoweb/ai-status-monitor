## Context

The widget currently polls local status JSON once per second and rebuilds the GTK body only when the session signature changes. Account-limit data is separate from hook status: Claude Code exposes 5-hour and 7-day utilization through its authenticated usage endpoint, while Codex emits rate-limit metadata in local session JSONL `token_count` events. Neither source is guaranteed to be available, and the Claude request must never block GTK or expose the user's OAuth credential.

The accepted UI adds a persistent compact usage section below session rows. It shows Claude `5h` and `Weekly`, Codex `Weekly`, and reset times without a separate section title. Each centered provider logo is the manual refresh control for only that provider. Automatic refresh runs every two minutes for both providers.

## Goals / Non-Goals

**Goals:**

- Normalize provider-specific data into one small model containing provider, window, used percentage, reset time, fetch time, and freshness.
- Keep session monitoring responsive and fully usable when either provider is unavailable.
- Protect Claude credentials by reading the existing token only for an in-memory request and never logging or caching it.
- Support automatic and user-triggered refresh without overlapping requests.
- Preserve last-known valid data per provider while it is still meaningful.

**Non-Goals:**

- Estimating usage from token counts or predicting when a limit will be exhausted.
- Supporting API-key billing quotas, organization dashboards, credits, or providers other than Claude Code and Codex.
- Modifying Claude/Codex authentication, hook payloads, or session files.
- Depending on TUI screen scraping or undocumented command-output formatting.

## Decisions

### 1. Add a provider-neutral usage module

Create `bin/ai_agent_status_lib/usage_limits.py` with pure parsing functions and provider collectors. A normalized result contains zero or more window records plus a provider-scoped error; malformed data from one provider cannot invalidate the other.

This keeps credentials, filesystem discovery, validation, and cache rules outside the GTK script. The alternative—implementing everything in `ai-agent-status-widget`—would deepen the existing UI monolith and make parser testing difficult.

### 2. Read Claude utilization through the endpoint used by Claude Code

The Claude collector reads `claudeAiOauth.accessToken` from `~/.claude/.credentials.json`, sends a bounded HTTPS GET to `https://api.anthropic.com/api/oauth/usage`, and accepts only numeric `utilization` plus parseable `resets_at` values from `five_hour` and `seven_day`. The request uses a short timeout and a fixed monitor user agent. Credential values are excluded from exceptions, diagnostics, cache objects, and logs.

Parsing `/usage` from an interactive terminal was rejected because it would require launching a TUI and would couple the monitor to presentation text. Estimating Claude utilization locally was rejected because account usage is shared across Claude surfaces and cannot be reconstructed from local sessions.

### 3. Read Codex utilization from recent local session events

The Codex collector locates the Codex home directory, examines recent session JSONL files newest-first, and selects the newest valid `event_msg`/`token_count` rate-limit record. It identifies the weekly window by `window_minutes == 10080` rather than assuming it is always `primary`, then normalizes `used_percent` and `resets_at`.

This avoids another authenticated network integration and uses data already written by Codex. Parsing the `/usage` TUI was rejected for the same stability and process-management reasons as Claude screen scraping. The collector will bound the number of files and lines inspected so refresh cost does not grow with complete session history.

### 4. Use a non-secret, per-provider cache

Write normalized successful results atomically to `usage_limits.json` under the existing monitor cache directory. Cache only utilization, reset/fetch timestamps, and provider/window identifiers. On a provider failure, use its last successful records with a `stale` presentation. Once a cached window's reset time has passed, treat it as unavailable instead of presenting obsolete utilization.

A single combined cache is preferred over extending session-status records because account limits are global, not session-specific, and refresh on a different cadence.

### 5. Refresh asynchronously with provider-specific manual controls

Start a short-lived background worker after the intro, then schedule it every 120 seconds. Provider calls are individually guarded so one failure does not suppress the other's result. GTK mutations return to the main loop through `GLib.idle_add`.

Automatic refresh requests both providers. Clicking the Claude or Codex logo requests only that provider and preserves the other provider's cached values without invoking its collector. A single global refresh remains in flight at a time to prevent concurrent writes to the combined cache; both logo controls are insensitive while it runs, and an automatic tick or another click during that time is skipped rather than queued. No persistent daemon or extra process is introduced.

Track the providers included in the active request as UI state. During a manual refresh only the clicked logo rotates; during an automatic refresh both logos rotate. The state clears and both controls become sensitive after the result is applied, including failure paths.

### 6. Render provider blocks with logos and stacked limit bars

Add a dedicated GTK box below the current session body without a heading or separate refresh button. Render one compact horizontal block per provider: its existing Claude Code or Codex logo sits on the left, vertically centered against the complete limit stack on the right. Claude shows `5h` and `Weekly`; Codex shows one `Weekly` bar. Each limit line places the window label at the left, the percentage at the right, a proportional bar below them, and the localized reset time in small secondary text.

Wrap each logo in a relief-free button with a provider-specific tooltip. Draw the pixbuf through a small Cairo widget so its angle can advance smoothly on the existing animation timer while that provider refreshes. Replacing the logo with `Gtk.Spinner` was rejected because provider identity would disappear; rotating the pixbuf only in 90-degree steps was rejected because the motion would be visibly abrupt.

Progress fill communicates urgency using fixed thresholds: green below 60%, orange from 60% through 84%, and red from 85% through 100%. The unfilled track remains neutral so color always represents consumed usage. Missing data displays `Unavailable`; cached fallback is visibly marked `stale` without changing its usage color. The section remains present in idle state but does not replace or affect status badge, alert, sound, or terminal-switch behavior.

The provider-block layout is preferred over a table because it keeps the provider identity visually clear without spanning a logo across rows. A single horizontal line per provider was rejected because two Claude bars would become too short at the widget's current width.

### 7. Test parsers, presentation rules, and failure behavior without live credentials

Cover normalization, Claude response parsing, Codex JSONL selection, cache expiry, partial-provider failures, targeted collector selection with untouched-provider preservation, deterministic provider grouping, and boundary values for the three progress-color bands using standard-library tests and temporary directories. Live endpoint access remains an explicit manual smoke test. GTK demo data will include available, refreshing, stale, and unavailable states so the provider-block layout and rotation can be inspected without credentials.

## Risks / Trade-offs

- **Claude's usage endpoint or credential shape changes** → Fail closed, retain unexpired cached data as stale, keep parsing isolated, and document the integration as best-effort.
- **Codex changes its session event schema or directory layout** → Validate every level, search only bounded recent data, and show unavailable rather than guessing.
- **Credential disclosure through diagnostics** → Never interpolate credential content into exceptions or logs; test cache and log output for token absence.
- **Network latency freezes the widget** → Perform all collection off the GTK thread with strict timeouts and single-flight refresh.
- **Old cache misrepresents a reset window** → Discard cached records after their reset timestamp.
- **Extra UI height makes the widget noisy** → Remove the usage heading and standalone refresh row, keep provider spacing tight, and use the existing logos as controls.
- **Provider-specific requests race while updating one cache** → Retain a global single-flight guard and preserve untouched provider records when a targeted refresh is persisted.

## Migration Plan

1. Add the normalized collector/cache module and parser tests.
2. Add asynchronous refresh state and the usage section to the widget.
3. Extend demo/manual validation and document the credential, network, and unavailable-state behavior.
4. Run the installer; its recursive `ai_agent_status_lib` copy deploys the new module with the widget.
5. Replace generic limit rows with provider-branded blocks and threshold-colored progress fills without changing collection or refresh behavior.
6. Remove the usage heading and shared refresh button, center each clickable logo, and add provider-specific refresh with smooth logo rotation.

The change is additive and requires no status-cache migration. Rollback restores the previous widget/module set; a leftover non-secret `usage_limits.json` can be ignored safely.

## Open Questions

None for the initial scope. Additional providers, configurable refresh intervals, and detailed credit information require separate changes.
