# Subagent completion sound fix

## Problem

Codex emits `SubagentStop` whenever a short-lived subagent finishes. The status
model currently maps that event to `kind: done`. The widget interprets `done` as
the end of agent work and plays the same notification sound used for the main
agent's completion, even though the main Codex session is still processing the
subagent result.

## Design

Map Codex `SubagentStop` to:

- `kind: analyzing`
- `status: Codex: analyzing`

Keep the `SubagentStop` hook registered. This lets the event refresh the main
session status while accurately representing that Codex is processing the
subagent result. Do not add special-case sound suppression to the widget: the
existing sound behavior remains driven by the semantic status kind.

The regular Codex `Stop` event remains mapped to `kind: done` and continues to
trigger the completion sound. Waiting and error notifications are unchanged.

## Scope

The implementation changes only the Codex event mapping and its regression
tests. It does not change hook installation, widget presentation, sound
configuration, or Claude event handling.

## Verification

Add automated coverage proving that:

1. `SubagentStop` produces `analyzing` and never `done`.
2. `Stop` still produces `done`.
3. Existing status-model behavior remains passing.

Run the repository Python syntax checks and full `unittest` suite after the
focused regression test.
