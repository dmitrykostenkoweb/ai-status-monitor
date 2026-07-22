## Purpose

Define reliable, private, and non-blocking collection and presentation of Claude Code and Codex usage-limit windows while preserving existing session-monitoring behavior.

## Requirements

### Requirement: Provider usage windows are collected accurately
The system SHALL collect Claude Code 5-hour and weekly utilization and Codex weekly utilization from the newest valid data available for each provider. Each collected window SHALL include a provider identifier, window identifier, used percentage, reset timestamp, and fetch timestamp.

#### Scenario: Claude usage data is available
- **WHEN** the authenticated Claude usage source returns valid 5-hour and 7-day utilization records
- **THEN** the system normalizes them as Claude `5h` and `Weekly` windows with their used percentages and reset timestamps

#### Scenario: Live Codex weekly usage is available
- **WHEN** the authenticated installed Codex CLI app-server returns a valid rate-limit window of 10080 minutes
- **THEN** the system normalizes that window as Codex `Weekly` using its used percentage and reset timestamp
- **AND** the monitor does not read or persist the Codex OAuth credential

#### Scenario: Live Codex usage is unavailable
- **WHEN** the Codex CLI app-server is missing, unsupported, times out, or returns malformed data
- **THEN** the system searches recent Codex session metadata for a valid rate-limit window of 10080 minutes

#### Scenario: Newest provider data is malformed
- **WHEN** the newest candidate record is malformed or incomplete
- **THEN** the system ignores it and searches the bounded recent provider data for the newest valid record

### Requirement: Usage limits are visible in the widget
The widget SHALL display a compact usage section independently from the session-status rows and without a visible section heading. It SHALL group limits by provider in horizontal blocks with the provider's logo on the left, vertically centered against the provider's complete limit stack on the right. Every available limit SHALL show its window label, used percentage, proportional usage indicator, and reset time in the user's local timezone.

#### Scenario: All requested windows are available
- **WHEN** Claude 5-hour, Claude weekly, and Codex weekly records are valid
- **THEN** the widget displays the Claude logo beside stacked `5h` and `Weekly` indicators
- **AND** displays the Codex logo beside its `Weekly` indicator

#### Scenario: Provider blocks are rendered
- **WHEN** the usage section is visible
- **THEN** no usage-section title or standalone refresh button consumes vertical space
- **AND** each provider logo is vertically centered against its complete limit stack

#### Scenario: Utilization is below the warning threshold
- **WHEN** a limit uses less than 60 percent
- **THEN** its progress fill is green

#### Scenario: Utilization reaches the warning threshold
- **WHEN** a limit uses from 60 percent through 84 percent
- **THEN** its progress fill is orange

#### Scenario: Utilization reaches the critical threshold
- **WHEN** a limit uses 85 percent or more
- **THEN** its progress fill is red

#### Scenario: A utilization bar is displayed
- **WHEN** the widget renders any available limit
- **THEN** the unused progress track remains neutral regardless of the fill color

#### Scenario: Session list is empty
- **WHEN** no Claude or Codex session status is active
- **THEN** the usage section remains visible alongside the widget's idle state

#### Scenario: A provider has no usable record
- **WHEN** a provider has neither current data nor a valid cached value
- **THEN** the widget keeps that provider's logo visible and displays `Unavailable` beside it without hiding other providers

### Requirement: Automatic and provider-specific refresh share one lifecycle
The system SHALL refresh both providers automatically every 120 seconds and SHALL use each provider logo as a manual refresh control for only that provider. At most one usage refresh SHALL run at a time.

#### Scenario: Automatic refresh interval elapses
- **WHEN** 120 seconds have elapsed since the scheduled refresh
- **THEN** the system starts a background refresh for Claude and Codex usage

#### Scenario: User requests a manual refresh
- **WHEN** the user activates the Claude or Codex logo while no refresh is running
- **THEN** the system refreshes only the selected provider
- **AND** preserves the other provider's displayed and cached values without invoking its collector
- **AND** both logo controls remain disabled until the refresh finishes
- **AND** only the selected logo rotates while work is in flight

#### Scenario: Automatic refresh is running
- **WHEN** the 120-second refresh requests both providers
- **THEN** both provider logos rotate until the refresh result is applied

#### Scenario: Refresh is already running
- **WHEN** an automatic tick or logo activation occurs during an active refresh
- **THEN** the system does not start or queue another overlapping refresh

### Requirement: Provider failures degrade independently
Failure, timeout, missing authentication, or malformed data from one provider MUST NOT prevent the other provider from refreshing or displaying valid usage data. Usage collection MUST NOT block the GTK main loop or interfere with session-status refresh, alerts, sounds, or terminal switching.

#### Scenario: Claude refresh fails and Codex succeeds
- **WHEN** the Claude request fails but valid Codex metadata is available
- **THEN** the widget updates Codex usage and handles Claude using its provider-specific fallback state

#### Scenario: Network request is slow
- **WHEN** the Claude endpoint does not respond before the configured bounded timeout
- **THEN** collection ends as a Claude failure without freezing widget interaction

#### Scenario: All usage sources are unavailable
- **WHEN** neither provider can return valid usage data
- **THEN** existing session monitoring continues to operate normally

### Requirement: Last successful usage is cached without secrets
The system SHALL atomically cache normalized successful provider results without credentials or raw authenticated responses. After a refresh failure, an unexpired last-successful value SHALL remain visible and SHALL be marked `stale`; a cached window whose reset time has passed SHALL be treated as unavailable.

#### Scenario: Provider fails before cached window resets
- **WHEN** a provider refresh fails and its cached usage window has not reached its reset timestamp
- **THEN** the widget displays the cached value with a visible `stale` indication

#### Scenario: Cached window has reset
- **WHEN** a cached usage window's reset timestamp is in the past
- **THEN** the widget does not present its old percentage as current or stale usage
- **AND** displays `Unavailable` when no newer valid value exists

#### Scenario: Cache write is interrupted
- **WHEN** a cache update cannot be completed atomically
- **THEN** the system retains or recovers the previous valid cache instead of consuming a partial record

### Requirement: Claude credentials remain private
The system MUST use the existing Claude Code OAuth access token only in memory for the authenticated usage request. It MUST NOT copy or serialize the token into monitor cache files, status records, logs, diagnostics, UI text, or exception messages.

#### Scenario: Claude credential is present
- **WHEN** the system performs an authenticated Claude usage request
- **THEN** it reads the access token for that request without persisting another copy

#### Scenario: Claude credential is absent or unreadable
- **WHEN** no usable Claude OAuth access token can be read
- **THEN** Claude collection fails safely without changing authentication files
- **AND** Codex usage and session monitoring remain available

#### Scenario: Claude endpoint returns an error
- **WHEN** an authenticated request fails with an HTTP or parsing error
- **THEN** logs and diagnostics contain no access token or raw credential object

### Requirement: Existing status contracts remain compatible
Usage-limit monitoring SHALL be additive and SHALL NOT change hook payload processing, structured session-status records, compatibility text output, or the behavior of installations that are offline or lack provider usage data.

#### Scenario: Existing installation upgrades
- **WHEN** the updated widget starts with existing status and configuration files but no usage cache
- **THEN** session statuses remain readable and the usage section initializes through normal collection or unavailable states

#### Scenario: Runtime remains offline
- **WHEN** the widget cannot reach the Claude usage endpoint
- **THEN** local status monitoring and locally available Codex usage continue without requiring network access
