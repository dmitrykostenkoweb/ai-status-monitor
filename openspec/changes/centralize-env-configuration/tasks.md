## 1. Environment Files and Safety

- [x] 1.1 Add a documented `.env.default` with every supported `AI_STATUS_*` variable and safe defaults.
- [x] 1.2 Create the local `.env` from the template and update `.gitignore` to ignore local dotenv, credential, certificate, and private-key files while explicitly allowing `.env.default`.

## 2. Shared Configuration Loading

- [x] 2.1 Add a dependency-free Python configuration module that parses the restricted dotenv syntax without evaluation, preserves process-environment precedence, expands supported path forms, and validates typed values.
- [x] 2.2 Add a shared Bash configuration helper with the same restricted syntax, known-variable allowlist, path defaults, and non-executing behavior.
- [x] 2.3 Verify representative comments, quoted values, command-substitution literals, booleans, integers, invalid values, and precedence behave consistently across both loaders.

## 3. Runtime Integration

- [x] 3.1 Update the hook to use resolved cache and status paths from the shared Python configuration.
- [x] 3.2 Update the widget to use resolved paths, presentation values, timeout settings, and environment-over-legacy-JSON precedence while keeping window coordinates in `widget.json`.
- [x] 3.3 Update the doctor to use resolved paths and timeout settings and to report effective environment configuration locations.
- [x] 3.4 Update the panel and widget start, stop, and toggle helpers to load resolved paths through the shared Bash helper.

## 4. Installation and Migration

- [x] 4.1 Install the shared Python and Bash configuration support with the existing entry points.
- [x] 4.2 Create the installed runtime `.env` with mode `0600` from repository `.env` or `.env.default` only when it does not already exist.
- [x] 4.3 Migrate valid legacy widget settings into the first installed `.env`, preserve `x` and `y` in `widget.json`, and report when an existing environment file is left unchanged.
- [x] 4.4 Ensure desktop launchers and hooks continue to start the configured entry points without requiring repository access.

## 5. Documentation and Verification

- [x] 5.1 Document supported variables, file locations, precedence, migration, local-secret handling, and example customization in `README.md` and update architecture notes in `CLAUDE.md`.
- [x] 5.2 Run Python compilation and Bash syntax checks for every modified executable and helper.
- [x] 5.3 Run hook and installer smoke tests with a temporary `HOME`, covering no environment file, repository override, legacy JSON migration, existing installed `.env` preservation, and custom directory paths.
- [x] 5.4 Confirm `.env` is ignored, `.env.default` is tracked, no secret-like value is introduced, and the OpenSpec change validates successfully.
