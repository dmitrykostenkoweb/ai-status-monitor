# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Display provider usage limits for Claude and Codex in the widget.
- Read live Codex usage limits from local session data.

### Fixed

- Use the canonical GitHub repository address for update checks and self-updates.

## [0.2.1] - 2026-07-01

### Fixed

- Keep the widget reliably above other windows on GNOME/Mutter.

### Removed

- Remove the widget toggle command and launcher in favor of the explicit start and stop helpers.

[Unreleased]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/a44e0da...HEAD
[0.2.1]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/c2e15ae...a44e0da
