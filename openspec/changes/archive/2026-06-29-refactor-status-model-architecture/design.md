## Context

`ai-cli-status-monitor` is intentionally a lightweight local tool: hooks write status files under `~/.cache/ai-cli-status-monitor`, the GTK widget reads those files, and helper scripts provide panel output, process control, installation, and health checks. There is no package manager, daemon, service, network dependency, or build step.

The current status record already contains useful structured fields such as `agent`, `event`, `tool`, `project`, `cwd`, timestamps, and `client_pids`, but the actual state category is implicit in the localized `status` string. The widget then infers state by matching words such as `czeka`, `koduje`, `analiz`, or `kończył`. That makes display copy part of the behavior contract.

The change should preserve the existing script-based deployment while making status semantics explicit and reusable.

## Goals / Non-Goals

**Goals:**

- Add a machine-readable status kind to persisted status JSON records.
- Keep the localized display text available for current UI and panel behavior.
- Make hook event mapping produce explicit semantics instead of only display strings.
- Make the widget prefer the structured kind for color, sorting, stale/done filtering, notification, and alert behavior.
- Preserve compatibility with older cache records that do not yet contain the new field.
- Keep the implementation self-contained and suitable for direct copying by `install.sh`.

**Non-Goals:**

- Do not introduce a background daemon, server, database, network calls, or package-manager build step.
- Do not redesign the GTK visual layout as part of this architectural change.
- Do not remove `combined.txt` or the existing text panel output.
- Do not require users to clear existing cache files during upgrade.
- Do not change Claude or Codex hook event coverage unless needed to preserve current behavior.

## Decisions

### Persist `kind` Alongside `status`

Status JSON records should include a stable `kind` field, for example:

```json
{
  "agent": "codex",
  "kind": "command",
  "status": "Codex: wykonuje komendę"
}
```

`status` remains the user-facing label and compatibility output. `kind` becomes the behavior contract used by the widget and future health checks.

Alternative considered: replace `status` with structured fields only. This would be cleaner long-term, but it would break `combined.txt`, existing cache readers, and any user scripts depending on the current text output.

### Use a Small Closed Set of State Kinds

The initial state kinds should match the UI states already present in the widget:

- `thinking`
- `reading`
- `coding`
- `command`
- `analyzing`
- `waiting`
- `error`
- `done`
- `idle`
- `stale`
- `neutral`

Hook-generated records should normally use active event kinds such as `thinking`, `reading`, `coding`, `command`, `analyzing`, `waiting`, `error`, `done`, or `neutral`. Widget-derived freshness states such as `idle` and `stale` may remain display-time transformations rather than hook output.

Alternative considered: make kinds agent-specific, such as `codex-permission-request` or `claude-pre-tool-use`. That would preserve more source detail but would leak hook event details into UI behavior and increase branching in the widget.

### Keep Compatibility Fallbacks in the Widget

The widget should read `kind` when present. If an old status file does not contain `kind`, it should fall back to the existing text classifier. This lets installed users upgrade without deleting cache files and allows graceful handling of malformed or hand-written status files.

Alternative considered: migrate or delete old cache files during install. That is unnecessary and less friendly for a local user tool.

### Centralize Semantics Without Heavy Packaging

The preferred structure is to extract pure status semantics into importable Python code while keeping executable scripts in `bin/`. A small local module can hold shared constants and functions for:

- known state kinds
- agent event-to-kind mapping
- display label formatting
- status JSON normalization

This avoids duplicating core rules across the hook, widget, and doctor while preserving direct script execution.

Alternative considered: leave every script self-contained. This keeps copying simple but continues the current drift risk. Another alternative is a full Python package with setup metadata, but that adds deployment weight that does not fit the project.

### Treat `combined.txt` as a Compatibility Projection

`combined.txt` should continue to be generated from structured status records as text. It should not become the primary state source for the widget when structured JSON is available.

Alternative considered: remove `combined.txt` once JSON is available. That would simplify internals, but it would remove the simplest panel and troubleshooting interface.

## Risks / Trade-offs

- Existing installed scripts may temporarily mix new and old cache records -> mitigate by keeping text-classification fallback for records without `kind`.
- A shared local module can make direct copied scripts more sensitive to missing files -> mitigate by installing the module together with scripts and keeping the fallback surface small.
- Introducing `kind` without tests can move the hidden coupling rather than remove it -> mitigate with simulated Claude and Codex payload checks that verify both `kind` and `status`.
- If `kind` names are too broad, future UI behavior may need extra metadata -> mitigate by preserving raw `event` and `tool` fields for diagnostics and future refinement.

## Migration Plan

1. Add structured kind generation to hook status building while continuing to write the existing `status` text and `combined.txt`.
2. Update widget session loading to prefer `kind` from JSON and fall back to text classification only when needed.
3. Update widget ordering, alert detection, stale/done handling, and notification decisions to use normalized session kind.
4. Update doctor checks only where structured status improves validation; keep existing stale timestamp behavior.
5. Verify Python syntax and simulate representative Claude and Codex payloads.

Rollback is straightforward: because `status` and `combined.txt` remain compatible, reverting widget use of `kind` restores the previous behavior without requiring cache cleanup.

## Open Questions

- Should shared code live under `bin/ai_agent_status_lib/` for install-time copying, or under a top-level `lib/` copied by `install.sh`?
- Should `kind` be the only new field, or should the hook also emit a `label` field while keeping `status` as legacy formatted text?
- Should stale and idle be persisted by the hook, or remain widget-derived from timestamps?
