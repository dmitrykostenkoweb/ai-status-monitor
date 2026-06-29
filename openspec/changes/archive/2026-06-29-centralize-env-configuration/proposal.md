## Why

Runtime and installation settings are currently duplicated across Python and Bash scripts, while the repository has no safe convention for local or potentially sensitive overrides. Centralizing user-configurable values in an ignored `.env` file with a tracked `.env.default` template reduces configuration drift and lowers the risk of publishing local values.

## What Changes

- Add a tracked `.env.default` containing safe, documented defaults and create a local `.env` for overrides.
- Ignore `.env` and common private key or credential file variants while keeping `.env.default` tracked.
- Load the same environment configuration from the hook, widget, doctor, process helpers, and installer.
- Install the resolved runtime configuration under `~/.config/ai-cli-status-monitor/.env` without silently overwriting an existing user configuration.
- Keep `widget.json` backward compatible for persisted window position and existing widget settings; explicit environment values take precedence over corresponding JSON settings.
- Document configuration variables, precedence, installation behavior, and the rule that secrets belong only in `.env`, never in `.env.default`.
- Keep Git author-history rewriting out of scope; removing the previously published work email remains a separate destructive operation requiring explicit approval before force-pushing.

## Capabilities

### New Capabilities

- `environment-configuration`: Defines safe environment templates, runtime loading, precedence, installation, and backward compatibility for configurable monitor values.

### Modified Capabilities

None.

## Impact

- Affected files include `.gitignore`, `.env.default`, the local ignored `.env`, `install.sh`, runtime scripts under `bin/`, shared Python configuration support, and configuration documentation in `README.md` and `CLAUDE.md`.
- Existing installations continue to work without an environment file by using built-in defaults and current `widget.json` values.
- No external services, network calls, or third-party Python dependencies are introduced.
- Rollback consists of removing environment loading and returning each script to its existing built-in paths and defaults.
