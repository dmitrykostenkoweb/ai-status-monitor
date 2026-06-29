## ADDED Requirements

### Requirement: Safe environment file convention
The project SHALL provide a tracked `.env.default` containing only safe documented defaults, SHALL keep the local `.env` untracked, and MUST NOT require secrets in the tracked template.

#### Scenario: Repository contains local overrides
- **WHEN** a developer creates or edits the repository `.env`
- **THEN** Git ignores that file while continuing to track `.env.default`

#### Scenario: Default template is published
- **WHEN** `.env.default` is committed to a public repository
- **THEN** it contains no credentials or machine-specific sensitive values

### Requirement: Supported configuration values
The system SHALL support environment configuration for cache, configuration, and data directories; widget title, width, and row limit; notification sound; stale, done, idle, and hide timeouts; and theme. The process-level `AI_STATUS_ENV_FILE` variable SHALL select a non-default runtime environment file.

#### Scenario: User changes a supported value
- **WHEN** a valid supported variable is defined in the effective environment configuration
- **THEN** every entry point that consumes that setting uses the configured value

#### Scenario: Runtime environment file is relocated
- **WHEN** `AI_STATUS_ENV_FILE` is exported before a monitor entry point starts
- **THEN** the entry point loads configuration from that file instead of the default runtime path

### Requirement: Deterministic configuration precedence
For each supported configurable value, the system SHALL prefer an exported process value over the runtime `.env`, the runtime `.env` over a corresponding legacy `widget.json` value, and a legacy JSON value over the built-in default.

#### Scenario: Process value and file value conflict
- **WHEN** the same supported variable exists in both the process environment and runtime `.env`
- **THEN** the process environment value is used

#### Scenario: Environment file is absent
- **WHEN** no process value or runtime `.env` value exists and `widget.json` contains a valid legacy setting
- **THEN** the legacy JSON setting is used

#### Scenario: No configuration source defines a value
- **WHEN** a supported setting is absent from the process environment, runtime `.env`, and legacy JSON
- **THEN** the built-in default is used

### Requirement: Non-executing dotenv parsing
The system MUST parse dotenv configuration as data and MUST NOT execute shell commands, substitutions, or arbitrary syntax contained in the file. The supported syntax SHALL include blank lines, comments, `KEY=VALUE` assignments, and single- or double-quoted values.

#### Scenario: Configuration contains command substitution
- **WHEN** a dotenv value contains shell command-substitution syntax
- **THEN** the parser treats it as literal or invalid data and does not execute the command

#### Scenario: Configuration contains comments and quoted spaces
- **WHEN** a dotenv file contains comments and a quoted widget title containing spaces
- **THEN** the parser ignores the comments and returns the title without surrounding quotes

### Requirement: Typed values fail safely
The system SHALL validate boolean, integer, and path values independently. An invalid value MUST NOT prevent the monitor from starting and SHALL fall back to the next valid configuration source or built-in default with a diagnostic.

#### Scenario: Timeout is not an integer
- **WHEN** a timeout variable contains a non-integer value
- **THEN** the monitor records a diagnostic and uses the next valid value

#### Scenario: Boolean uses a supported spelling
- **WHEN** the sound setting contains a documented true or false spelling
- **THEN** the system converts it to the corresponding boolean value consistently in Python and Bash consumers

### Requirement: Installation preserves configuration
The installer SHALL create `~/.config/ai-cli-status-monitor/.env` with mode `0600` when it does not exist and SHALL leave an existing installed environment file unchanged.

#### Scenario: First installation with repository override
- **WHEN** the repository `.env` exists and the installed runtime `.env` does not
- **THEN** the installer creates the installed runtime file from the repository override with private file permissions

#### Scenario: Reinstallation with existing runtime configuration
- **WHEN** the installed runtime `.env` already exists
- **THEN** the installer preserves its contents and reports that it was not overwritten

### Requirement: Legacy widget configuration migration
On first creation of the installed runtime `.env`, the installer SHALL preserve valid existing widget configuration values by carrying them into the corresponding environment values. Window coordinates SHALL remain in `widget.json` and SHALL NOT be moved into `.env`.

#### Scenario: Existing installation has customized timeout
- **WHEN** `widget.json` contains a valid customized timeout and no installed runtime `.env` exists
- **THEN** the created runtime `.env` contains the equivalent timeout value

#### Scenario: Existing installation has saved window coordinates
- **WHEN** `widget.json` contains `x` and `y` coordinates
- **THEN** those coordinates remain in `widget.json` and continue to control the window position

### Requirement: Backward-compatible operation
All monitor entry points SHALL continue to operate with built-in defaults and valid legacy configuration when no environment file exists. No external service, network access, or third-party dotenv dependency SHALL be required.

#### Scenario: Upgrade without environment file
- **WHEN** an existing user runs an updated entry point before reinstalling or creating `.env`
- **THEN** the entry point starts using legacy configuration or built-in defaults

#### Scenario: Offline installation and runtime
- **WHEN** the project is installed and run without network access
- **THEN** environment configuration works using only repository and standard-library code
