# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A lightweight local status monitor for **Claude Code CLI** and **Codex CLI** on Linux Mint / Cinnamon. CLI hooks emit JSON events; a small GTK3 floating widget shows the latest known status of each agent. Pure Python 3 + GTK3/PyGObject + Bash — no Electron, no web server, no daemon. User-facing strings and docs are in **English**. Network access is limited to the best-effort GitHub update check (see "Distribution & updates" below) and the opt-in KLIPY GIF search for stickers; everything else is local.

## Commands

There is no build step or package manager. The scripts in `bin/` run directly.

```bash
# Syntax-check the Python scripts (the only "build" gate)
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget bin/ai-agent-status-doctor bin/ai_agent_status_lib/*.py
bash -n install.sh bin/ai-agent-status-env bin/ai-agent-status-panel bin/ai-agent-status-update bin/ai-agent-status-widget-*

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

Unit tests use stdlib `unittest`: `python3 -m unittest discover -s tests` (GTK tests need `xvfb-run`, PyGObject for the running Python, and `AI_STATUS_DATA_DIR=$PWD/assets` when nothing is installed). Plus `--test` (pipeline) and `--demo` (UI).

## Architecture

**Producer/consumer split over the filesystem — the two halves never communicate directly.**

1. **Producer: `bin/ai-agent-status-hook`** (run by the CLIs as a hook). Reads a hook JSON payload on stdin, classifies it into a human status string, and writes status files under `~/.cache/ai-cli-status-monitor/`. Key functions:
   - `claude_semantic()` / `codex_semantic()` (in `ai_agent_status_lib/status_model.py`) — map `(event, tool)` → a `StatusSemantic` = `{kind, status}`, where `kind` is one of the structured `StatusKind`s (`thinking`, `reading`, `coding`, `command`, `analyzing`, `waiting`, `error`, `done`, `idle`, …) and `status` is the English display string (e.g. `Claude: coding`, `Codex: running command`, `Codex: waiting for approval`, `Claude: done`). This is where event→status logic lives.
   - `stable_session_id()` — derives a per-session key from `session_id`/`transcript_path` when present (Claude). When absent (Codex sends only `cwd` + event), `fallback_session_key()` keys on the POSIX **session leader** (`os.getsid(0)`, i.e. the terminal's shell) — stable for the whole session and unique per window/tab, and resistant to the transient per-event wrapper that spawns the hook (so one session stays one row instead of flooding `statuses/`). Last-resort fallback is `ppid + cwd`.
   - `handle_payload()` writes: `statuses/<id>.json` (per session), legacy `claude.json`/`codex.json` (single latest per agent, kept for compatibility), `<agent>.txt`, and the merged `combined.txt`.
   - `ancestor_pids()` records the hook's process-ancestor chain (hook → CLI → shell → terminal emulator) into each status as `client_pids`, so the widget can raise the correct terminal window by PID.
   - Malformed/non-dict payloads are saved to `debug_payloads/` and still produce a status — the hook must never crash the calling CLI.

2. **Consumer: `bin/ai-agent-status-widget`** (long-lived GTK window). Polls status files **once per second**, prefers `statuses/*.json`, falls back to legacy `<agent>.json`, then `combined.txt`. Each session is turned into a row via `make_session()`, driven by the structured `kind` written by the hook (falling back to `classify()` only for legacy records without a `kind`); `kind` → colour from `STATE_COLORS`. Renders up to `MAX_ROWS` (5) rows ordered waiting → in-progress → done, with a `+N finished, hidden automatically` footer and a horizontal-lockup **empty/idle** state (`build_lockup`: the `LogoMark` radar logo + "AI Status Monitor" + idle text) when nothing is active. On startup the same lockup shows as a **3 s intro splash** (`build_intro` → `end_intro`, gated by the `intro` flag so the 1 s poll can't pre-empt it). Time-based transitions (stale → `no new events` → idle → hidden, auto-hiding `done`) are computed here from age vs. thresholds in `widget.json`. A second **200 ms animation tick** drives trailing `...`, the waiting dot's expanding ring, the red border pulse, the LIVE-badge pulse, and the lockup logo sweep; rows are rebuilt **only when a content signature changes** (avoids per-second flicker and window jitter). Plays `notification.mp3` only on transition *into* a `waiting` state or *into* `done`. A few seconds after startup it also runs a one-shot GitHub update check on a daemon thread (`start_update_check` → `ai_agent_status_lib/updates.py`); if a newer `VERSION` is published it shows an `update ↑` header pill and menu entry that shell out to `ai-agent-status-update`.
   - Glowing status dots and the radar glyph are drawn with **cairo** (optional dependency — `CAIRO_OK` falls back to flat discs / a Unicode-free no-op if pycairo is missing).
   - Every row shows a right-aligned, vertically-centered, text-styled clickable `przełącz →` (neutral grey; on dim/done rows the opacity fade is applied to the logo+text only, so the switch stays crisp) that calls `switch_to_session()`: it lists windows (`list_windows` ← `wmctrl -lp`), narrows to those whose PID is in the session's `client_pids`, and raises it (`wmctrl -i -a`). When one emulator process owns several windows (gnome-terminal), it disambiguates the PID candidates by **window title** (project/cwd); with one process per window (alacritty/kitty/xterm) the PID match is already exact. Title-only match is the last fallback. Cannot target a specific *tab* within a window, and degrades quietly under tmux/ssh/Wayland or without `wmctrl`.

3. **Configuration:** `bin/ai_agent_status_lib/env_config.py` parses runtime dotenv as data (never shell), validates typed values, and resolves process env → runtime `.env` → legacy `widget.json` → built-in defaults. `bin/ai-agent-status-env` provides the equivalent restricted loader for Bash helpers. `AI_STATUS_ENV_FILE` is the bootstrap override for the runtime file. `AI_STATUS_AGENTS` (`claude,codex` / `claude` / `codex`) filters which agents' rows and usage bars the widget shows; the right-click `Show agents` menu rewrites just that key in the runtime `.env` via `write_env_value()`. The `SettingsWindow` (header `⚙` / `Settings…`) edits agents, sound, max rows, the four timing thresholds, Serious mode and the KLIPY key through `StatusWidget.update_setting()`, which applies the value live and persists it the same way; title, card width and paths still need a restart.

4. **GIF stickers:** `ai_agent_status_lib/stickers.py` (GTK-free, unit tested) maps `kind` → sticker key (`KIND_TO_STICKER`: analyzing/coding/waiting/done/error/idle, plus `limit` derived from usage ≥ 90%), loads bubble texts and KLIPY queries (`DEFAULT_BUBBLES`/`DEFAULT_QUERIES`, overridable in `<config>/stickers.json`), and `StickerSource.pick()` chooses KLIPY → local pool (`<data>/gifs/<key>/`) → striped placeholder, never repeating a file twice in a row. In the widget, `update_stickers()` diffs per-session sticker keys on each poll (first poll only primes; disabled in `--demo`), `request_sticker()` debounces 500 ms and picks on a worker thread, and `StickerOverlay` — a separate click-through RGBA POPUP window placed off the card's top-right corner — draws the tilted sticker, GIF frames (GdkPixbuf) and speech bubble (PangoCairo) with the spec's pop-in/tuck-away motion. `waiting`/`error` stay until the status changes; row hover re-shows the last sticker. Design spec + reference: `docs/design/gif-sticker/`. Preview with `--sticker <key|all>`.

5. **Session windows** (`AI_STATUS_SESSION_WINDOWS`, default on): `sync_session_cards()` keeps one `SessionCard` (undecorated, sticky, keep-above toplevel titled `AI agent session` — deliberately not containing the widget title) per visible session, built from the same `build_row()` (animated parts register in the card's own lists, which `tick_animation` also drives). Each card owns a `StickerOverlay` that stays up while the session works/waits, re-picks only on a sticker-key change and tucks on done/idle. Docked cards stack under the widget in first-seen order (`layout_cards`, re-run on widget move/resize); dragging makes a card floating and saves its position to `<config>/session_windows.json` (14-day TTL). The main card then shows only header + usage — the body is always collapsed, and there is no intro splash or idle lockup in this mode (both exist only in the classic list). `apply_wmctrl_hints` re-asserts sticky/above for every card by window id.

6. **Helpers (Bash):** `*-start` / `*-stop` manage the process via `widget.pid`; `ai-agent-status-panel` dumps `combined.txt` for debugging. All source `ai-agent-status-env` from the same installed `bin` directory.

### The cross-file contract: the structured `kind`, not the display string

The data contract between the two halves is the structured **`kind`** field, not the human text. The hook writes `{kind, status}` into each `statuses/<id>.json`; the widget keys colors, the LIVE/ALERT/IDLE badge, the per-state palette, ordering, auto-hide, and sound off `kind` (see `IN_PROGRESS_KINDS` / `INACTIVE_KINDS` and `STATE_COLORS`). Because of this you can **freely change any display `status` string** — including translating it — without touching the widget, as long as the `kind` stays correct.

`classify_status_text()` in `status_model.py` is only a **fallback** for legacy cache records written before `kind` existed; it recognizes both the current English strings (`thinking`, `coding`, `waiting`, `done`, `no new events`, …) and the old Polish stems (`myśl`, `koduje`, `czeka`/`zgod`, `kończył`, `brak nowych`, `błąd`, …), so old `~/.cache` files still classify. If you add a **new** `StatusKind`, update `STATUS_KINDS`, the `IN_PROGRESS_KINDS`/`INACTIVE_KINDS` sets, and `STATE_COLORS` together.

### Filesystem layout (runtime)

- `~/.cache/ai-cli-status-monitor/` — `statuses/`, `last_payloads/`, `debug_payloads/`, `combined.txt`, `<agent>.json`, `widget.log`, `widget.pid` (path configurable).
- `~/.config/ai-cli-status-monitor/.env` — installed runtime configuration, created with mode `0600` and preserved on reinstall.
- `~/.config/ai-cli-status-monitor/session_windows.json` — positions of dragged (floating) session windows, per session id.
- `~/.config/ai-cli-status-monitor/widget.json` — saved window position (`x`/`y`) plus legacy configuration fallback.
- `~/.local/share/ai-cli-status-monitor/` — `notification.mp3`, agent logos, `gifs/<sticker>/` (local sticker pool, seeded from `assets/gifs`), `VERSION` (installed version), `install_source` (path the installer ran from, used by the updater), `src/` (managed clone created on demand by `curl|bash` or the updater) (path configurable).
- Hook wiring: `~/.claude/settings.json` (events: UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop, StopFailure) and `~/.codex/hooks.json` (adds PermissionRequest, SubagentStop; uses `"matcher": "*"`). Examples in `examples/`. Codex may also need `/hooks` → trust.

### Distribution & updates

Shipped via **public GitHub**, versioned by the repo-root `VERSION` file (semver). `install.sh` copies `VERSION` and records where it ran from (`install_source`); when piped through `curl … | bash` it self-bootstraps by cloning into `~/.local/share/.../src` and re-execing. `ai-agent-status-update` pulls that clone (or reclones) and re-runs the idempotent `install.sh`, which now **restarts** the widget so updates take effect. The widget's startup check and the updater both read `AI_STATUS_UPDATE_REPO` (`owner/repo`, default `dmitrykostenkoweb/ai-status-monitor`) and `AI_STATUS_UPDATE_BRANCH` (default `main`), comparing versions via `updates.parse_version` (tuple compare; garbage → `()` sorts lowest). **Bump `VERSION` when publishing** or clients won't see the update.

## Conventions & constraints

- **Keep it lightweight — no background services or new runtime dependencies.** The value proposition is "lightweight local, no daemon". The **one** sanctioned network call is the best-effort GitHub update check (`ai_agent_status_lib/updates.py`, `ai-agent-status-update`): a single request on a short-lived daemon thread at startup, fully failure-tolerant (offline = silent no-op). The **only other** sanctioned network access is the opt-in KLIPY GIF search for stickers (`ai_agent_status_lib/stickers.py`): it runs only when the user has set `AI_STATUS_KLIPY_API_KEY` and Serious mode is off, only on a sticker-status change, on a short-lived worker thread, with search results (URL lists) reused for 1 h. Per KLIPY's integration requirements, media is loaded directly from the returned `*.klipy.com` URL into memory (`GdkPixbuf.PixbufLoader`) and **must never be written to disk, mirrored or re-hosted** — do not reintroduce a media cache (the widget deletes the legacy `<cache>/stickers/` dir at startup). Results must not be reordered/filtered beyond picking one; any failure falls back to the local GIF pool. Never log the KLIPY key (it is part of the request URL). Do not add other network calls or a polling loop. (cairo is used only when present and degrades gracefully; `wmctrl` is already required for always-on-top and is reused for the `→` window switch.)
- **`install.sh` must preserve user config**: merge or back up (`*.bak.<timestamp>`) files under `~/.claude`, `~/.codex`, `~/.config/ai-cli-status-monitor`; never overwrite silently. Hook merging is idempotent (skips an already-present command).
- The hook is defensive by design — keep it from raising on bad input.
- Python: 4-space indent, `snake_case`, uppercase path/default constants, type hints where useful, scripts self-contained and executable. Bash: `set -euo pipefail`, quote path vars.
- `.env.default`, `DEFAULT_VALUES` in `env_config.py`, and defaults in `ai-agent-status-env` must stay in sync.
