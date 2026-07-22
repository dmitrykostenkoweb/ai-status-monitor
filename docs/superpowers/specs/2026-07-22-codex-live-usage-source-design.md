# Codex Live Usage Source Design

## Goal

Make the Codex weekly usage shown by the widget current even when no interactive
Codex session is running. Prevent an older session record from being presented
as freshly collected usage.

## Source priority

The Codex collector will use the installed Codex CLI app-server as its primary
source. It will start a short-lived `codex app-server --stdio` process,
initialize the JSONL protocol, call `account/rateLimits/read`, normalize the
weekly window whose duration is 10080 minutes, and terminate the process.

The collector will not read, copy, log, or cache the Codex OAuth credential.
Authentication remains owned by the installed Codex CLI.

Recent Codex session JSONL metadata remains a compatibility fallback when the
CLI is missing, the app-server method is unsupported, the request times out, or
the response is malformed. Existing normalized cache behavior remains the last
fallback and continues to mark retained values as stale.

## Process and error handling

The app-server subprocess will have a bounded timeout and captured text streams.
Only the JSON response matching the rate-limit request ID will be parsed;
notifications and unrelated output will be ignored. The subprocess will always
be terminated or allowed to exit after the one request.

An app-server failure will not fail the widget refresh if the local session
fallback returns a valid weekly limit. If neither live nor local data is valid,
the existing provider-specific stale or unavailable behavior applies. Claude
collection and GTK rendering are unchanged.

## Data flow

1. The widget starts its existing background usage refresh.
2. The Codex collector invokes the short-lived app-server client.
3. A valid `account/rateLimits/read` response is normalized to the existing
   `UsageLimit` structure.
4. If that step fails, the collector searches bounded recent session JSONL.
5. `refresh_usage` applies the existing sanitized cache and display lifecycle.

No new persistent configuration or secret storage is introduced.

## Testing

Tests will drive the change through an injected subprocess runner:

- a valid app-server response produces the current weekly percentage;
- protocol notifications and unrelated responses are ignored;
- malformed output, timeout, missing executable, and non-zero exit fall back to
  recent session JSONL;
- the app-server response takes precedence over an older session value;
- no credential or raw authenticated response is written to the usage cache;
- the complete existing unit-test suite and Python syntax checks remain green.

## Compatibility

The implementation targets the non-experimental
`account/rateLimits/read` method exposed by the installed Codex 0.145.0 schema.
Because `codex app-server` itself may change between Codex releases, all
protocol interaction stays isolated behind the existing collector and retains
the session JSONL fallback.
