## Why

The status monitor currently uses human-readable Polish status text as both UI copy and the implicit state contract between the hook, widget, panel, and doctor. This works for the current small script set, but it makes future changes fragile because changing labels can accidentally change classification, colors, sorting, sounds, or stale/done behavior.

## What Changes

- Introduce an explicit structured status model for persisted agent status records, including a machine-readable state kind separate from display text.
- Update hook output so Claude and Codex event mapping produces both a stable state kind and a display label.
- Update widget session loading, ordering, filtering, styling, alert detection, and notification logic to prefer the structured state kind instead of re-classifying localized text.
- Keep compatibility with existing cache files and the `combined.txt` panel output during the transition.
- Centralize shared status semantics enough that hook, widget, and doctor do not each need to infer the same concepts independently.
- Preserve the lightweight local-script deployment model: no background service, no network calls, and no package-manager build step.

## Capabilities

### New Capabilities

- `structured-status-model`: Defines the persisted status contract and how agent events map to stable status kinds, display labels, freshness, and compatibility outputs.

### Modified Capabilities

None. There are no existing OpenSpec capabilities in `openspec/specs/`.

## Impact

- Affected scripts: `bin/ai-agent-status-hook`, `bin/ai-agent-status-widget`, `bin/ai-agent-status-doctor`, and possibly `bin/ai-agent-status-panel`.
- Affected data files: JSON status files under `~/.cache/ai-cli-status-monitor/statuses/`, legacy `~/.cache/ai-cli-status-monitor/{claude,codex}.json`, and `combined.txt`.
- User-visible behavior should remain equivalent except for improved resilience when labels or UI copy change.
- Validation should cover Python syntax checks plus simulated hook payloads for Claude and Codex status kinds.
