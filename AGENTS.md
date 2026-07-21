# Repository Guidelines

## Project Structure & Module Organization

This repository is a Linux desktop status monitor for Claude Code and Codex CLI. Executable entry points live in `bin/`: the hook records agent events, the GTK3 widget displays them, the panel prints terminal output, and the doctor validates an installation. Start/stop helpers manage the widget process; `ai-agent-status-update` handles GitHub-based updates; `ai-agent-status-env` reads runtime settings.

Shared Python code belongs in `bin/ai_agent_status_lib/`, including environment loading, status models, update checks, and provider usage-limit collection. Standard-library tests live in `tests/`. Static images and sounds live in `assets/`, hook examples in `examples/`, and specifications in `openspec/specs/`. `install.sh` installs files, `.env.default` documents configuration, and `VERSION` identifies releases.

## Build, Test, and Development Commands

There is no package-manager build. Run these checks from the repository root:

```bash
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget \
  bin/ai-agent-status-doctor bin/ai_agent_status_lib/*.py
python3 -m unittest discover -s tests -v
AI_STATUS_CACHE_DIR="$(mktemp -d)" bin/ai-agent-status-hook --agent codex --test
bin/ai-agent-status-widget --demo
./install.sh
~/.local/bin/ai-agent-status-doctor
~/.local/bin/ai-agent-status-update --check
```

The first command checks Python syntax. The hook command exercises sample events in an isolated cache. Use the demo for visual GTK changes. The remaining commands refresh, diagnose, and check updates for the installed copy.

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, `snake_case` functions and variables, and uppercase constants. Add type hints where they clarify contracts. Keep executable scripts self-contained and preserve executable file modes. Bash scripts should use descriptive variables, quote paths, and follow the existing Bash style. Put reusable Python behavior in `ai_agent_status_lib` rather than duplicating it across entry points.

## Testing Guidelines

Tests use Python's standard-library `unittest`; no coverage threshold exists. Test both Claude and Codex hook paths with `--test`; use a temporary `AI_STATUS_CACHE_DIR` or temporary `HOME` to avoid altering live status data. Provider usage tests must use fixtures or injected transports and must never read live credentials. For widget changes, run `--demo` and check for GTK errors. For installer or configuration changes, rerun `./install.sh`, then the doctor, and verify that an existing private runtime `.env` remains intact.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit-style subjects such as `fix(widget): ...`, `feat(config): ...`, and `docs(readme): ...`. Keep each commit focused and use an imperative summary. Pull requests should explain user-visible behavior, list validation commands, link relevant issues or OpenSpec changes, and include screenshots or recordings for UI changes.

## Security & Configuration Tips

Never commit `.env` or credentials. Defaults belong in `.env.default`; installation must preserve `~/.config/ai-cli-status-monitor/.env` and Claude/Codex hook configuration. Never log or cache Claude's OAuth token. Keep network access limited to the documented GitHub version/update requests and Claude Code usage endpoint unless a change explicitly requires and documents another dependency.
