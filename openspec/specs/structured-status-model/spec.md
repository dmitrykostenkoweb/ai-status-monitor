# Structured Status Model Specification

## Purpose

Define the stable machine-readable status contract shared by hooks, the widget, health checks, and compatibility text outputs.

## Requirements

### Requirement: Persisted statuses expose a machine-readable kind
The system SHALL write each structured agent status record with a machine-readable `kind` field in addition to the existing human-readable `status` field.

#### Scenario: Hook writes a structured active status
- **WHEN** the status hook receives a supported Claude or Codex event payload
- **THEN** the written JSON status record contains `agent`, `kind`, `status`, `event`, `tool`, `project`, `cwd`, `timestamp_iso`, `timestamp_hhmm`, `client_pids`, and `raw_payload_path`
- **AND** `kind` is one of the supported status kinds used by the widget behavior
- **AND** `status` remains a human-readable label suitable for existing text outputs

#### Scenario: Hook handles malformed payloads
- **WHEN** the status hook receives malformed JSON or an unexpected non-object payload
- **THEN** the written JSON status record still contains a valid `kind`
- **AND** the hook preserves debug information for troubleshooting
- **AND** the hook does not prevent `combined.txt` from being regenerated

### Requirement: Event mapping produces stable status semantics
The system SHALL map Claude and Codex hook events to stable status kinds independently from localized display text.

#### Scenario: Tool execution is classified by behavior
- **WHEN** a pre-tool event identifies a shell or command tool
- **THEN** the resulting status kind is `command`
- **AND** the display status can remain localized without changing that behavior

#### Scenario: Permission or user interaction is classified as waiting
- **WHEN** a hook event or notification indicates permission, approval, confirmation, or user input is needed
- **THEN** the resulting status kind is `waiting`
- **AND** widget alert behavior can be driven from `kind` rather than from matching words in `status`

#### Scenario: Completed and failed events have explicit kinds
- **WHEN** a stop event is processed
- **THEN** the resulting status kind is `done`
- **WHEN** a failure or malformed payload status is processed
- **THEN** the resulting status kind is `error`

### Requirement: Widget behavior prefers structured kinds
The widget SHALL use the structured status kind as the primary source for session color, ordering, alert detection, stale/done handling, and notification decisions.

#### Scenario: Status text changes without changing behavior
- **WHEN** a structured status record contains `kind` set to `waiting`
- **AND** the human-readable `status` text is changed to different localized copy
- **THEN** the widget still displays the session as an alert state
- **AND** the widget still prioritizes the session as waiting
- **AND** the widget does not depend on matching localized words in the display text

#### Scenario: Freshness transforms retain semantic behavior
- **WHEN** a structured status record becomes stale or idle based on configured age thresholds
- **THEN** the widget applies the derived stale or idle presentation consistently
- **AND** the original persisted status kind remains available for diagnostics

### Requirement: Legacy status files remain readable
The widget SHALL remain compatible with existing status JSON files that do not include the new `kind` field.

#### Scenario: Widget reads an old cache record
- **WHEN** the widget loads a status JSON record without `kind`
- **THEN** it falls back to the existing status-text classification behavior
- **AND** the session remains visible when it would have been visible before this change
- **AND** the widget logs or handles malformed records without crashing

### Requirement: Text compatibility outputs are preserved
The system SHALL continue producing the existing text compatibility outputs while structured JSON is available.

#### Scenario: Combined panel output is regenerated
- **WHEN** the hook processes a status payload
- **THEN** `combined.txt` is regenerated from available status records
- **AND** each line remains formatted from the human-readable status, project, and timestamp

#### Scenario: Panel command reads text output
- **WHEN** the panel helper is invoked after a status update
- **THEN** it can continue reading `combined.txt`
- **AND** it does not need to parse the structured JSON status model

### Requirement: Health checks validate structured status without requiring cache cleanup
The doctor command SHALL account for structured status records while continuing to tolerate legacy cache files during upgrade.

#### Scenario: Doctor checks live Codex status age
- **WHEN** the doctor inspects recent Codex status files
- **THEN** it can use `timestamp_iso` from either new structured records or legacy records
- **AND** the presence of older records without `kind` does not cause the live status check to fail by itself
