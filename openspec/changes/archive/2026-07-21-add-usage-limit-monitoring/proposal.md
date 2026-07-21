## Why

The widget shows whether Claude Code and Codex sessions are active, but users must leave it and open each CLI's usage screen to learn when account limits are close to exhaustion. Showing current utilization and reset times in the existing desktop monitor makes capacity visible before a coding session is interrupted.

## What Changes

- Add a compact usage-limits section to the widget with Claude Code 5-hour and weekly utilization plus Codex weekly utilization.
- Show each available limit as a percentage with its reset time and provider identity.
- Refresh all providers automatically every two minutes and make each provider logo a provider-specific manual refresh control.
- Preserve the last successful values when a provider temporarily fails, mark those values as stale, and show `Unavailable` when no usable value exists.
- Isolate provider failures so Claude and Codex usage can be displayed independently.
- Read the existing Claude Code OAuth credential only in memory for the usage request; never copy credentials into the monitor cache or logs.
- Keep status monitoring functional offline and when usage data is unavailable.

## Capabilities

### New Capabilities

- `usage-limit-monitoring`: Retrieve, cache, refresh, and present Claude Code and Codex account-limit utilization with safe credential handling and graceful degradation.

### Modified Capabilities

None.

## Impact

- Widget layout and refresh lifecycle in `bin/ai-agent-status-widget`.
- New reusable provider and cache logic under `bin/ai_agent_status_lib/`.
- Read-only access to Claude Code credentials and Codex session metadata in the user's home directory.
- A periodic HTTPS request to Anthropic's Claude Code usage endpoint; Codex usage remains local-file based.
- Installer packaging, documentation, and manual validation paths may require updates for the new shared module and UI state.
- No breaking changes to hook payloads, persisted session-status records, or text compatibility output.
