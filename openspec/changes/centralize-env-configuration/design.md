## Context

The monitor currently derives storage paths independently in the hook, widget, doctor, panel, and process helpers. Widget behavior defaults are duplicated between the widget and installer, while mutable settings and window position are stored together in `widget.json`. The installed scripts run outside the repository, so a repository-only `.env` loader would not provide runtime configuration.

The solution must remain dependency-free, preserve existing installations, avoid executing arbitrary content from dotenv files, and keep local values out of Git.

## Goals / Non-Goals

**Goals:**

- Provide one documented set of user-configurable environment variables.
- Make repository overrides safe to keep locally and make the same values available after installation.
- Apply configuration consistently in Python and Bash entry points.
- Preserve existing `widget.json` settings and window position.
- Fail safely when configuration is missing or malformed.

**Non-Goals:**

- Store mutable runtime state, status payloads, PIDs, or window coordinates in `.env`.
- Introduce `python-dotenv` or another runtime dependency.
- Treat `.env` as a secret manager; it only prevents accidental Git tracking.
- Rewrite Git history or remove the published author email.
- Change the status model, hook event mapping, or widget appearance.

## Decisions

### 1. Use a tracked template and an ignored local override

`.env.default` is the public, tracked template. `.env` is ignored and may contain machine-local or sensitive overrides. The supported variables are:

- `AI_STATUS_CACHE_DIR`, `AI_STATUS_CONFIG_DIR`, and `AI_STATUS_DATA_DIR`
- `AI_STATUS_TITLE`, `AI_STATUS_CARD_WIDTH`, and `AI_STATUS_MAX_ROWS`
- `AI_STATUS_SOUND_ENABLED`
- `AI_STATUS_STALE_AFTER_SECONDS`, `AI_STATUS_HIDE_DONE_AFTER_SECONDS`, `AI_STATUS_IDLE_AFTER_SECONDS`, and `AI_STATUS_HIDE_STALE_AFTER_SECONDS`
- `AI_STATUS_THEME`

The runtime configuration file is discovered at `~/.config/ai-cli-status-monitor/.env` by default. A process-level `AI_STATUS_ENV_FILE` may select another file; this bootstrap variable is not read from the file it locates.

Alternative considered: retain only `widget.json`. This does not provide a conventional safe location for local or future secret values and does not configure Bash helpers.

### 2. Define one precedence order

For configurable values, precedence is:

1. An already exported process environment variable.
2. The installed runtime `.env` file.
3. A corresponding legacy value in `widget.json`.
4. A built-in code default.

Window coordinates remain exclusively in `widget.json`. Runtime state remains in the cache directory.

Alternative considered: let JSON override `.env`. That makes local environment overrides ineffective whenever an old JSON key exists.

### 3. Install configuration without destroying user changes

The installer reads the repository `.env` when present, otherwise `.env.default`. If the installed runtime `.env` does not exist, it creates it with mode `0600`. Before first creation on an existing installation, legacy widget settings are carried into the generated environment values so custom timeout or sound settings are retained. If the installed `.env` already exists, the installer leaves it unchanged and reports that decision.

The installed configuration is therefore independent of the repository after installation. Updating code does not silently replace user settings.

Alternative considered: source `.env` directly from the cloned repository at runtime. Installed scripts may outlive or move independently from that checkout, so this would be fragile.

### 4. Parse a restricted dotenv format without executing it

Python uses a small shared module under `ai_agent_status_lib` to parse `KEY=VALUE` lines, comments, blank lines, and single- or double-quoted values. Bash entry points source a shared parser/helper that accepts the same subset and exports only known `AI_STATUS_*` names. Neither implementation evaluates command substitution or arbitrary shell syntax.

Path values support `~` and `$HOME` expansion. Boolean and integer values are validated; invalid values produce a diagnostic and fall back to the next valid source rather than terminating the monitor.

Alternative considered: shell `source`. It is concise but executes arbitrary commands from the file and gives Python and Bash different parsing semantics.

### 5. Keep configuration mapping centralized by runtime language

The shared Python module owns defaults, type conversion, path expansion, and legacy JSON fallback for Python programs. A single Bash helper owns dotenv loading and path defaults for shell entry points. Names and defaults are declared in `.env.default` and verified against both loaders during smoke testing.

This keeps entry-point changes small while avoiding a new interpreter or dependency for each shell operation.

## Risks / Trade-offs

- [Python and Bash dotenv parsers diverge] → Support and document a deliberately small syntax subset and verify identical representative inputs.
- [Existing JSON customization is masked by a newly installed `.env`] → Migrate legacy values during first environment-file creation and never overwrite an existing installed file.
- [A malformed local value breaks startup] → Validate each typed value independently, log the invalid key, and continue with the next valid source or built-in default.
- [Users assume ignored `.env` encrypts secrets] → Document that it only reduces accidental commits and that exposed credentials still require rotation.
- [Configurable directories cause files to be split across old and new locations] → Treat directory changes as explicit opt-in behavior and have doctor report the resolved locations.

## Migration Plan

1. Add `.env.default`, ignore `.env`, and add defensive credential patterns to `.gitignore`.
2. Add shared Python and Bash configuration loaders.
3. Update all entry points to use resolved paths and values.
4. Update the installer to create or preserve the installed `.env` and migrate legacy widget values on first creation.
5. Update documentation and run syntax, parser, installation, and compatibility checks with a temporary `HOME`.

Rollback removes the loaders and environment installation logic. Existing `.env` files may remain unused; `widget.json` and cached statuses remain intact.

## Open Questions

None. The approved design establishes the file locations, precedence, compatibility behavior, and supported variable scope.
