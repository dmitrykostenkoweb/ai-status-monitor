## 1. Shared Status Semantics

- [x] 1.1 Decide the concrete shared-code location for lightweight script deployment and install copying.
- [x] 1.2 Define the supported status kind constants: `thinking`, `reading`, `coding`, `command`, `analyzing`, `waiting`, `error`, `done`, `idle`, `stale`, and `neutral`.
- [x] 1.3 Extract or centralize status classification helpers so hook and widget can share the same supported kind set without requiring a packaging/build step.
- [x] 1.4 Add a status normalization helper that returns a valid kind when records are missing `kind` or contain an unknown value.

## 2. Hook Status Output

- [x] 2.1 Update Claude event mapping to return both machine-readable `kind` and existing localized display status.
- [x] 2.2 Update Codex event mapping to return both machine-readable `kind` and existing localized display status.
- [x] 2.3 Add `kind` to the structured JSON record written by `bin/ai-agent-status-hook`.
- [x] 2.4 Ensure malformed JSON and unexpected payload paths still write a valid `kind`, preserve debug payload output, and regenerate `combined.txt`.
- [x] 2.5 Keep `combined.txt`, `claude.txt`, and `codex.txt` formatted from the human-readable status text for compatibility.

## 3. Widget Status Consumption

- [x] 3.1 Update structured session loading to prefer persisted `kind` and fall back to text classification for legacy records.
- [x] 3.2 Update session color, ordering, alert detection, waiting count, and notification decisions to use normalized kind values.
- [x] 3.3 Update stale, idle, and done filtering so derived presentation states remain consistent while the original persisted kind remains available in loaded session data.
- [x] 3.4 Keep `combined.txt` parsing as a fallback path for environments where structured JSON is not available.

## 4. Doctor And Installation Compatibility

- [x] 4.1 Update doctor checks only where needed to tolerate mixed old and new status records without requiring cache cleanup.
- [x] 4.2 If shared helper files are introduced, update `install.sh` so local installation copies them together with executable scripts.
- [x] 4.3 Confirm widget start/stop/toggle and panel helper behavior do not require changes beyond the structured status compatibility contract.

## 5. Validation

- [x] 5.1 Run Python syntax validation for changed Python scripts and any shared helper modules.
- [x] 5.2 Simulate representative Codex hook payloads and verify written JSON contains expected `kind` and compatible `status` text.
- [x] 5.3 Simulate representative Claude hook payloads and verify written JSON contains expected `kind` and compatible `status` text.
- [x] 5.4 Verify a legacy status JSON record without `kind` is still readable by the widget session loader.
- [x] 5.5 Verify `combined.txt` and `bin/ai-agent-status-panel` still produce the expected text output after hook updates.
