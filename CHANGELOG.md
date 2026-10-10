# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Fold the usage limits away with the new `▴`/`▾` header button, Settings → `Usage limits`, the right-click menu or `AI_STATUS_SHOW_LIMITS=false`. The agents' session cards and their GIFs stay; hidden limits are not fetched.
- Settings → `Start at login` turns the login entry (Linux `.desktop`, macOS LaunchAgent, Windows Run key) on or off. It is saved as `AI_STATUS_AUTOSTART`, and re-installing keeps it off.

### Fixed

- Linux: the Qt widget and session windows stay on top again (and on every workspace, off the taskbar). The widget now gives its X11 windows the same shape as the old GTK widget did, through libX11 directly instead of `wmctrl`: UTILITY window type, not transient for the application's group. It re-asserts "above" every second, because Muffin/Mutter drop it now and then. Before, the state was only re-asserted every 4 s through `wmctrl`, and never when `wmctrl` was missing.

### Changed

- **Comic redesign.** The widget, session windows, stickers, Settings, the KLIPY guide and menus now use the comic-book look from the design handoff: thick ink outlines, hard offset shadows, halftone header and bars, a tilted LIVE/ALERT/IDLE badge, stroked Bangers titles and agent names, coloured status chips, a yellow `➜` jump button, and logo discs for agents and providers. Stickers are now tilted polaroids with a sound-effect caption ("HMMM…", "CLACK!", "AHEM!") and a comic speech bubble, and they pop in with the handoff's bounce. The fonts (Bangers, Comic Neue, Space Mono; SIL OFL) are bundled for offline use.
- Dark comic theme by default, plus a light theme: Settings → `Light theme`, or `AI_STATUS_THEME=light`. It switches live. `AI_STATUS_THEME` now accepts only `dark` or `light`.
- The comic cards are drawn at 70 % of the design's size; the GIF stickers keep their full size. The default card width is 294 px (was 344) and the default title is `AI Agents Status!`. Re-installing upgrades these old defaults in an existing `.env`; values you changed are kept. Docked session windows leave room for each card's sticker.
- **The widget now runs on Linux, macOS and Windows.** It was rewritten from GTK3/PyGObject to Qt (PySide6) and keeps the same look and features: rows and session windows, GIF stickers with speech bubbles, usage limits, Settings, the KLIPY key guide, the `→` window switch, sounds and self-update. KLIPY media is still decoded from memory only (`QBuffer` → `QMovie`) and never written to disk.
- The installer sets PySide6 up automatically. When the installing Python cannot import it, `install.py` creates `<data dir>/venv` and installs `PySide6-Essentials` there (one-time download). It records the interpreters in `<data dir>/interpreters.json`, which autostart and the start/update helpers use. Running `ai-agent-status-widget` with a Python that lacks PySide6 re-runs it under that interpreter. `AI_STATUS_WIDGET_PYTHON` picks your own interpreter, and `AI_STATUS_SKIP_PIP=1` skips the download.
- Linux needs `libxcb-cursor0` (Qt 6.5+ on X11) instead of `python3-gi`/`gir1.2-gtk-3.0`; `wmctrl` is still used. The installer and doctor print the `apt` command. On Wayland the widget runs through XWayland so it can place its own windows.
- The doctor checks the PySide6 import of the widget's interpreter instead of GTK.
- `ai-agent-status-widget-start`, `-stop`, `-panel` and `-update` are now Python scripts, so they also run on Windows and with macOS's Bash 3.2.
- The hook reads stdin as UTF-8 on every platform, and on Windows it also records `console_window`.
- The installer backs up `~/.claude/settings.json` / `~/.codex/hooks.json` only when it actually changes them.

### Added

- Cross-platform groundwork for macOS and Windows. The new `install.py` installer works on Linux, macOS and Windows. `install.sh` is now a thin `curl | bash` bootstrap around it, and the new `install.ps1` does the same on Windows. Autostart uses a `.desktop` file (Linux), a LaunchAgent (macOS) or the `HKCU` Run key (Windows).
- `ai_agent_status_lib/platform_support.py` holds the OS-specific parts: default directories (`AppData` on Windows), the process-ancestor chain (`/proc`, `ps`, Toolhelp32), the per-terminal session key (`getsid` or the Windows console window), the sound player (`afplay`/PowerShell), opening files and URLs, and detached processes.
- `ai_agent_status_lib/window_switch.py`: the `→` window switch now has a macOS path (System Events) and a Windows path (`EnumWindows` + `SetForegroundWindow`) next to `wmctrl`.
- On macOS, Claude usage limits are read from the login Keychain when `~/.claude/.credentials.json` is absent.

## [0.3.8] - 2026-10-09

### Reverted

- Sticker bubbles and GIF picking are back to their 0.3.4 behaviour: funny bubble lines only (no task descriptions) and the broader KLIPY search phrases across several result pages. The 0.3.6 activity bubbles and meme-only queries and the 0.3.7 task-matched GIFs are removed; the hook no longer records `activity`. Everything else (KLIPY key guide, session windows, settings) is unchanged.

## [0.3.7] - 2026-10-09

### Changed

- Sticker bubbles mix both: a new task from Claude/Codex is shown for 5 seconds, then a funny line until the next task.
- GIFs now match the task: editing, reading, searching, tests, `git push`, installs/builds, web, sub-agents, to-do updates and permission requests each have their own meme topic. A session window changes GIF only on a new topic (at most every 15 s; waiting/error at once), so the coding ↔ analyzing flip after every tool call no longer reshuffles GIFs.

## [0.3.6] - 2026-10-09

### Added

- Sticker speech bubbles now say what the agent is doing right now (`patching stickers.py`, `Run the sticker tests`, `hunting for 'KLIPY'`, `may I use git push?`). The hook records a privacy-safe `activity` (file names only, command descriptions or program + subcommand, never arguments or prompts); the bubble text updates live while the GIF stays. Polish activity templates are included in `examples/stickers.pl.json`.

### Fixed

- Off-topic GIFs: KLIPY searches now use only the most relevant first page (top 16) and specific, meme-style phrases instead of generic words and random deeper pages.

## [0.3.5] - 2026-10-09

### Added

- In-app "Get a free KLIPY key" guide (Settings → Stickers → `Get a free key…`, or the right-click menu while no key is set): step-by-step instructions, an `Open the KLIPY Partner Panel` button, `Copy` buttons for every form field, and `Test & save`, which checks the key with one search and saves it only when it works.

## [0.3.4] - 2026-10-09

### Added

- GIF variety: the last 200 GIFs shown are never re-picked, search phrases and bubble lines are dealt like a shuffled deck, and KLIPY searches fetch 50 results from a random page 1–3. New searches are capped at 60/hour.
- Session windows swap to a new GIF every 2 minutes while the agent works (`AI_STATUS_STICKER_ROTATE_SECONDS`, Settings → Stickers), plus a `Show another GIF` item in the window's right-click menu.
- More content: 14–22 bubble lines and 12–15 KLIPY phrases per sticker, and a bigger Polish set.

## [0.3.3] - 2026-10-09

### Changed

- With session windows the widget is only the usage panel: no intro splash and no idle lockup animation. Agent runs appear as their own windows with GIFs.

## [0.3.2] - 2026-10-09

### Changed

- KLIPY GIFs are now loaded directly from KLIPY's URLs into memory and never cached on disk, as KLIPY's integration requirements ask; the old `~/.cache/ai-cli-status-monitor/stickers/` cache is removed at startup. Searches request GIF-only results, only `*.klipy.com` media URLs are accepted, and stickers with KLIPY GIFs show a small `KLIPY` mark.

## [0.3.1] - 2026-10-09

### Added

- Many more sticker speech-bubble lines and KLIPY search phrases per status, plus a Polish bubble set in `examples/stickers.pl.json`.

## [0.3.0] - 2026-10-09

### Added

- Display provider usage limits for Claude and Codex in the widget.
- Read live Codex usage limits from local session data.
- Show the weekly Claude Fable usage limit as a third Claude bar when the account reports one.
- `AI_STATUS_AGENTS` setting and a right-click `Show agents` menu to show only Claude Code or only Codex.
- Settings window (`⚙` in the header or right-click → `Settings…`) for agents, sound, visible rows and timing, applied live and saved to the runtime `.env`.
- Session windows: each agent run in its own draggable window with its own always-on GIF sticker; docked windows stack under the widget, dragged ones keep their position (`AI_STATUS_SESSION_WINDOWS`, on by default).
- GIF stickers that pop out of the widget when an agent changes status, with a speech bubble, local GIF pool, optional KLIPY search (cached), Serious mode and a `--sticker` preview flag.

### Fixed

- Use the canonical GitHub repository address for update checks and self-updates.
- Keep the widget on every workspace: window hints now target the widget's own window id instead of the first window whose title contains the widget title (e.g. a terminal titled after this project).
- Stop the GIF sticker from flickering on row hover: the sticker window is truly click-through and spurious leave events are ignored.

## [0.2.1] - 2026-07-01

### Fixed

- Keep the widget reliably above other windows on GNOME/Mutter.

### Removed

- Remove the widget toggle command and launcher in favor of the explicit start and stop helpers.

[Unreleased]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/ac74f24...HEAD
[0.3.8]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/f59c6b8...ac74f24
[0.3.7]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/1068ad7...f59c6b8
[0.3.6]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/a24f26f...1068ad7
[0.3.5]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/d7003b8...a24f26f
[0.3.4]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/466f5b8...d7003b8
[0.3.3]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/afdac1d...466f5b8
[0.3.2]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/be5f35c...afdac1d
[0.3.1]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/639ff88...be5f35c
[0.3.0]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/a44e0da...639ff88
[0.2.1]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/c2e15ae...a44e0da
