# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A lightweight local status monitor for **Claude Code CLI** and **Codex CLI** on Linux Mint / Cinnamon. CLI hooks emit JSON events; a small GTK3 floating widget shows the latest known status of each agent. Pure Python 3 + GTK3/PyGObject + Bash — no Electron, no web server, no daemon, no network calls. User-facing strings and docs are in Polish.

## Commands

There is no build step or package manager. The scripts in `bin/` run directly.

```bash
# Syntax-check the Python scripts (the only "build" gate)
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget bin/ai-agent-status-doctor bin/ai_agent_status_lib/env_config.py
bash -n install.sh bin/ai-agent-status-env bin/ai-agent-status-panel bin/ai-agent-status-widget-*

# Install / refresh into ~/.local, ~/.config, ~/.cache (idempotent; merges hooks, backs up configs)
./install.sh

# Run the widget UI directly from the repo (requires GTK deps installed)
bin/ai-agent-status-widget --demo        # rotating fake statuses, no hooks needed

# Exercise the hook → status-file → combined.txt pipeline with synthetic events
bin/ai-agent-status-hook --agent claude --test
bin/ai-agent-status-hook --agent codex --test

# Health-check an installed setup (scripts, cache, hooks, GTK import, wmctrl)
~/.local/bin/ai-agent-status-doctor

# GTK runtime deps (installer will not sudo for you)
sudo apt install python3-gi gir1.2-gtk-3.0 wmctrl
```

There is no test framework. Validation = `py_compile` + `--test` (pipeline) + `--demo` (UI).

## Architecture

**Producer/consumer split over the filesystem — the two halves never communicate directly.**

1. **Producer: `bin/ai-agent-status-hook`** (run by the CLIs as a hook). Reads a hook JSON payload on stdin, classifies it into a human status string, and writes status files under `~/.cache/ai-cli-status-monitor/`. Key functions:
   - `claude_status()` / `codex_status()` — map `(event, tool)` → a Polish status string (e.g. `Claude: koduje`, `Codex: wykonuje komendę`, `Codex: czeka na zgodę`, `Claude: zakończył`). This is where event→status logic lives.
   - `stable_session_id()` — derives a per-session key from `session_id`/`transcript_path` when present (Claude). When absent (Codex sends only `cwd` + event), `fallback_session_key()` keys on the POSIX **session leader** (`os.getsid(0)`, i.e. the terminal's shell) — stable for the whole session and unique per window/tab, and resistant to the transient per-event wrapper that spawns the hook (so one session stays one row instead of flooding `statuses/`). Last-resort fallback is `ppid + cwd`.
   - `handle_payload()` writes: `statuses/<id>.json` (per session), legacy `claude.json`/`codex.json` (single latest per agent, kept for compatibility), `<agent>.txt`, and the merged `combined.txt`.
   - `ancestor_pids()` records the hook's process-ancestor chain (hook → CLI → shell → terminal emulator) into each status as `client_pids`, so the widget can raise the correct terminal window by PID.
   - Malformed/non-dict payloads are saved to `debug_payloads/` and still produce a status — the hook must never crash the calling CLI.

2. **Consumer: `bin/ai-agent-status-widget`** (long-lived GTK window). Polls status files **once per second**, prefers `statuses/*.json`, falls back to legacy `<agent>.json`, then `combined.txt`. Each session is turned into a row via `make_session()` + `classify()` (status string → state *kind* → colour from `STATE_COLORS`). Renders up to `MAX_ROWS` (5) rows ordered waiting → in-progress → done, with a `+N zakończone ukryte automatycznie` footer and a horizontal-lockup **empty/idle** state (`build_lockup`: the `LogoMark` radar logo + "AI Status Monitor" + idle text) when nothing is active. On startup the same lockup shows as a **3 s intro splash** (`build_intro` → `end_intro`, gated by the `intro` flag so the 1 s poll can't pre-empt it). Time-based transitions (stale → `brak nowych eventów` → idle → hidden, auto-hiding `zakończył`) are computed here from age vs. thresholds in `widget.json`. A second **200 ms animation tick** drives trailing `...`, the waiting dot's expanding ring, the red border pulse, the LIVE-badge pulse, and the lockup logo sweep; rows are rebuilt **only when a content signature changes** (avoids per-second flicker and window jitter). Plays `notification.mp3` only on transition *into* a waiting state (`czeka`) or *into* done.
   - Glowing status dots and the radar glyph are drawn with **cairo** (optional dependency — `CAIRO_OK` falls back to flat discs / a Unicode-free no-op if pycairo is missing).
   - Every row shows a right-aligned, vertically-centered, text-styled clickable `przełącz →` (neutral grey; on dim/done rows the opacity fade is applied to the logo+text only, so the switch stays crisp) that calls `switch_to_session()`: it lists windows (`list_windows` ← `wmctrl -lp`), narrows to those whose PID is in the session's `client_pids`, and raises it (`wmctrl -i -a`). When one emulator process owns several windows (gnome-terminal), it disambiguates the PID candidates by **window title** (project/cwd); with one process per window (alacritty/kitty/xterm) the PID match is already exact. Title-only match is the last fallback. Cannot target a specific *tab* within a window, and degrades quietly under tmux/ssh/Wayland or without `wmctrl`.

3. **Configuration:** `bin/ai_agent_status_lib/env_config.py` parses runtime dotenv as data (never shell), validates typed values, and resolves process env → runtime `.env` → legacy `widget.json` → built-in defaults. `bin/ai-agent-status-env` provides the equivalent restricted loader for Bash helpers. `AI_STATUS_ENV_FILE` is the bootstrap override for the runtime file.

4. **Helpers (Bash):** `*-start` / `*-stop` manage the process via `widget.pid`; `*-toggle` flips it; `ai-agent-status-panel` dumps `combined.txt` for debugging. All source `ai-agent-status-env` from the same installed `bin` directory.

### The critical cross-file coupling: the Polish status vocabulary

The hook emits status strings; the widget does **substring matching on those exact Polish words** to choose colors, the LIVE/ALERT/IDLE badge, the per-state palette, and whether to play sound:
- `classify()` (the single source of state-kind logic), `should_hide_status()`, and `set_badge()` in the widget all key off words like `myśli`, `czyta`, `koduje`, `wykon`/`komend`, `analiz`, `czeka`/`zgod`, `kończył` (the shared stem of `zakończył`/`skończył`), `brak nowych`, `idle`, `błąd`.

**If you change a status string in `claude_status`/`codex_status`, grep for the affected word in the widget's `classify()` and update it too**, or styling/sound/auto-hide will silently break. The data contract between the two halves is these strings, not a schema. Note `done` detection matches the stem `kończył`, so both the current `zakończył` and any legacy `skończył` cache files still register as done.

### Filesystem layout (runtime)

- `~/.cache/ai-cli-status-monitor/` — `statuses/`, `last_payloads/`, `debug_payloads/`, `combined.txt`, `<agent>.json`, `widget.log`, `widget.pid` (path configurable).
- `~/.config/ai-cli-status-monitor/.env` — installed runtime configuration, created with mode `0600` and preserved on reinstall.
- `~/.config/ai-cli-status-monitor/widget.json` — saved window position (`x`/`y`) plus legacy configuration fallback.
- `~/.local/share/ai-cli-status-monitor/` — `notification.mp3`, agent logos (path configurable).
- Hook wiring: `~/.claude/settings.json` (events: UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop, StopFailure) and `~/.codex/hooks.json` (adds PermissionRequest, SubagentStop; uses `"matcher": "*"`). Examples in `examples/`. Codex may also need `/hooks` → trust.

## Conventions & constraints

- **Never add network calls, background services, or new runtime dependencies** — the whole value proposition is "lightweight local, no daemon". (cairo is used only when present and degrades gracefully; `wmctrl` is already required for always-on-top and is reused for `przełącz →` window switching.)
- **`install.sh` must preserve user config**: merge or back up (`*.bak.<timestamp>`) files under `~/.claude`, `~/.codex`, `~/.config/ai-cli-status-monitor`; never overwrite silently. Hook merging is idempotent (skips an already-present command).
- The hook is defensive by design — keep it from raising on bad input.
- Python: 4-space indent, `snake_case`, uppercase path/default constants, type hints where useful, scripts self-contained and executable. Bash: `set -euo pipefail`, quote path vars.
- `.env.default`, `DEFAULT_VALUES` in `env_config.py`, and defaults in `ai-agent-status-env` must stay in sync.
