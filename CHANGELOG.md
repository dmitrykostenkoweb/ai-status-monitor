# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/a44e0da...HEAD
[0.2.1]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/c2e15ae...a44e0da
