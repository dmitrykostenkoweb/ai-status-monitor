# Repository Guidelines

## Project Structure & Module Organization

This repository is a lightweight local status monitor for Claude Code and Codex CLI on Linux Mint/Cinnamon. Runtime scripts live in `bin/`:

- `ai-agent-status-hook`: receives hook payloads and writes status files.
- `ai-agent-status-widget`: GTK3 floating widget UI.
- `ai-agent-status-doctor`: local installation and health checks.
- `ai-agent-status-widget-start`, `-stop`, and `-toggle`: process helpers.

Static media and launcher assets live in `assets/`. Hook configuration examples live in `examples/`. `install.sh` copies scripts and assets into the user-local locations under `~/.local`, `~/.config`, and `~/.cache`.

## Build, Test, and Development Commands

There is no package manager or build step. Validate Python syntax with:

```bash
python3 -m py_compile bin/ai-agent-status-hook bin/ai-agent-status-widget bin/ai-agent-status-doctor
```

Run a UI demo after installing GTK dependencies:

```bash
bin/ai-agent-status-widget --demo
```

Install or refresh the local user installation:

```bash
./install.sh
```

Check the installed setup:

```bash
~/.local/bin/ai-agent-status-doctor
```

## Coding Style & Naming Conventions

Python scripts use Python 3 with type hints where useful, 4-space indentation, `snake_case` functions, and uppercase constants for paths and defaults. Keep scripts executable and self-contained. Bash scripts should use clear variable names, quote path variables, and prefer simple POSIX-compatible command usage unless Bash features are already required.

## Testing Guidelines

No formal test framework is present. For changes to hook parsing, simulate payloads through `bin/ai-agent-status-hook --agent codex` or `--agent claude` and inspect `~/.cache/ai-cli-status-monitor/combined.txt` or a temporary `HOME`. For widget changes, run `--demo` and verify no GTK runtime errors occur.

## Commit & Pull Request Guidelines

Git history is not available from this checkout, so use concise imperative commit messages such as `Fix multi-session Codex statuses` or `Improve widget layout`. Pull requests should describe the user-visible behavior change, list validation commands run, and include screenshots or screen recordings for UI changes when possible.

## Security & Configuration Tips

Do not add network calls or background services. Preserve user config during installation: `install.sh` should merge or back up files under `~/.claude`, `~/.codex`, and `~/.config/ai-cli-status-monitor` instead of overwriting them silently.
