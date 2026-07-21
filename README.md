# ai-cli-status-monitor

<img src="assets/lockup.gif" alt="AI Status Monitor lockup" width="100%" />

A mini floating widget for Linux Mint / Cinnamon that shows the last known status of the Claude Code CLI and the Codex CLI.

It is a lightweight local tool: Python 3, GTK3/PyGObject and Bash. No Electron, no web server and no Docker. Network access is limited to the documented update check and Claude Code usage lookup.

## 1. What it is

`ai-cli-status-monitor` hooks into the Claude Code and Codex CLIs, writes statuses to `~/.cache/ai-cli-status-monitor/`, and a small GTK widget reads the freshest entries and shows one or two lines of status.

Example:

```text
Claude: reading code [unitbox-front] 14:22
Codex: running command [ai-cli-status-monitor] 14:23
```

## 2. Appearance

The widget looks like a small dark floating card / mini-player:

- dark background with a subtle border and rounded corners
- header: radar icon, `AI Agents Status`, a state badge (`● LIVE` / `▲ N ALERT` / `● IDLE`) and a `×` button
- one row per active session (up to 5), each with: a glowing dot in the state color, an agent logo tile, the agent name, the status (monospace), and a `project · time` line
- colors depend on the state (thinking, reading code, coding, running a command, analyzing output, waiting for approval, finished)
- active states get an animated `...`; `done` sessions are dimmed, and any overflow is collapsed behind a `+N finished, hidden automatically` footer
- each row has a clickable `→` on the right that activates the terminal window of that session; a `waiting for approval` row is additionally highlighted in red with a pulsing border
- when nothing is running: an empty/idle state shows the "AI Status Monitor" lockup (radar logo + wordmark) with a rotating radar sweep and `no active agents`
- on startup the same lockup is shown for ~3 seconds as an intro splash
- when a newer version is published on GitHub, a small `update ↑` pill appears in the header (see [Updates](#7b-updates))
- a compact usage section groups Claude Code 5-hour/weekly and Codex weekly utilization beside centered, clickable provider logos
- right-click menu: `Reload`, `Open logs folder`, `Check for updates` / `Update to …`, `Quit`

By default the widget is always-on-top, sticky across workspaces, and hidden from the taskbar.

## 3. Installation

Quick install (clones into `~/.local/share/ai-cli-status-monitor/src` and runs the installer):

```bash
curl -fsSL https://raw.githubusercontent.com/dmitrykostenkoweb/ai-status-monitor/main/install.sh | bash
```

Or from a local clone (lets you edit `.env` first):

```bash
git clone https://github.com/dmitrykostenkoweb/ai-status-monitor.git
cd ai-status-monitor
cp .env.default .env
# optional: edit your local .env
./install.sh
```

The installer is idempotent, so re-running it (or `ai-agent-status-update`) safely refreshes an existing install and restarts the widget.

The installer tries to configure the hooks automatically:

- Claude Code: `~/.claude/settings.json`
- Codex CLI: `~/.codex/hooks.json`
- autostart: `~/.config/autostart/ai-cli-status-widget.desktop`
- launcher in the Cinnamon menu: `AI CLI Status Widget`
- launcher icon: `~/.local/share/pixmaps/ai-cli-status-widget.png`
- notification sound: `~/.local/share/ai-cli-status-monitor/notification.mp3`
- OpenAI/Codex logo: `~/.local/share/ai-cli-status-monitor/openai-logo.svg`
- Anthropic/Claude logo: `~/.local/share/ai-cli-status-monitor/anthropic-logo.png`
- runtime configuration: `~/.config/ai-cli-status-monitor/.env`
- window position and legacy-config compatibility: `~/.config/ai-cli-status-monitor/widget.json`

If GTK or `wmctrl` are not available, the installer does not run `sudo`. It prints the command:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 wmctrl
```

## 4. Running the widget

```bash
~/.local/bin/ai-agent-status-widget
```

Appearance demo:

```bash
~/.local/bin/ai-agent-status-widget --demo
```

## 5. Start / stop

```bash
~/.local/bin/ai-agent-status-widget-start
~/.local/bin/ai-agent-status-widget-stop
```

After installation you can also launch it from the Cinnamon menu entry `AI CLI Status Widget`; right-click it to add it to the panel or the desktop.

## 6. Doctor

```bash
~/.local/bin/ai-agent-status-doctor
```

It checks:

- scripts in `~/.local/bin`
- the cache dir
- the autostart desktop file
- Claude hooks
- Codex hooks
- `wmctrl`
- the GTK import
- the hook's test mode
- the installed version and whether an update is available

## 7. Autostart

The installer creates:

```text
~/.config/autostart/ai-cli-status-widget.desktop
```

The widget should start automatically after you log in to Cinnamon.

## 7a. `.env` configuration

Public defaults live in `.env.default`. Your local `.env` is ignored by Git. On the first install a private `~/.config/ai-cli-status-monitor/.env` is created with `0600` permissions; subsequent installs do not overwrite it.

Available variables:

- `AI_STATUS_CACHE_DIR`, `AI_STATUS_CONFIG_DIR`, `AI_STATUS_DATA_DIR` — data directories
- `AI_STATUS_TITLE`, `AI_STATUS_CARD_WIDTH`, `AI_STATUS_MAX_ROWS` — widget appearance
- `AI_STATUS_SOUND_ENABLED` — `true`/`false`, `yes`/`no`, `on`/`off` or `1`/`0`
- `AI_STATUS_STALE_AFTER_SECONDS`, `AI_STATUS_HIDE_DONE_AFTER_SECONDS`, `AI_STATUS_IDLE_AFTER_SECONDS`, `AI_STATUS_HIDE_STALE_AFTER_SECONDS` — timeouts
- `AI_STATUS_THEME` — theme name
- `AI_STATUS_ENV_FILE` — path to a different runtime file; this variable must be exported in the process, it is not read from `.env`

Example of a local override:

```dotenv
AI_STATUS_TITLE="Agent status"
AI_STATUS_MAX_ROWS=8
AI_STATUS_SOUND_ENABLED=false
```

Value precedence: a variable exported in the process → runtime `.env` → legacy value from `widget.json` → built-in value. `widget.json` still stores the window position (`x`/`y`); on the first install, existing widget settings are migrated into the runtime `.env`.

`.env` prevents accidental commits but does not encrypt secrets. If a credential ends up in Git or on GitHub, you must revoke and rotate it.

Behavior:

- a fresh status is shown normally
- after `stale_after_seconds` the line is dimmed and shows `no new events`
- after `idle_after_seconds` the line transitions to `idle`
- after `hide_stale_after_seconds` the old status is hidden
- `done` disappears after `hide_done_after_seconds`, by default after 3 minutes
- a `waiting` state turns on the red color, the red border/pulse and the sound, if `sound_enabled` is `true`

## 7b. Updates

The widget knows its own version (see `VERSION`) and can update itself from GitHub.

```bash
# update now (pull latest source, reinstall, restart the widget)
~/.local/bin/ai-agent-status-update

# just check without changing anything
~/.local/bin/ai-agent-status-update --check

# print the installed version
~/.local/bin/ai-agent-status-widget --version
```

A few seconds after startup the widget makes a single, best-effort request to GitHub for the latest published `VERSION`. If it is newer, an `update ↑` pill appears in the header and an `Update to …` entry is added to the right-click menu — clicking either runs `ai-agent-status-update` for you. If you are offline the check silently does nothing.

`ai-agent-status-update` pulls the source clone recorded at install time (`~/.local/share/ai-cli-status-monitor/install_source`), or clones a fresh copy into `~/.local/share/ai-cli-status-monitor/src` if none is found, then re-runs `install.sh` (which restarts the widget).

The repository is configurable for forks/mirrors via `AI_STATUS_UPDATE_REPO` (`owner/repo`) and `AI_STATUS_UPDATE_BRANCH`.

## 7c. Usage limits

The widget refreshes both account limits automatically every two minutes. Click the Claude or Codex logo to refresh only that provider; the active logo spins until its refresh finishes. The controls remain temporarily disabled while a refresh is already running.

Claude's `5h` and `Weekly` bars are stacked beside the Claude logo; Codex's `Weekly` bar sits beside the Codex logo. Progress fill is green below 60% utilization, orange from 60% through 84%, and red from 85% upward. The unused track remains neutral.

- Claude Code: 5-hour and weekly utilization from Claude Code's authenticated usage endpoint
- Codex: weekly utilization from the newest valid local `rate_limits` event under `~/.codex/sessions/`
- cache: normalized, non-secret values in `~/.cache/ai-cli-status-monitor/usage_limits.json`

The Claude request reuses the OAuth access token already stored by Claude Code in `~/.claude/.credentials.json`. The monitor reads it only in memory for the request; it does not copy the token into its cache or logs. API-key billing quotas are not supported.

Provider failures are independent. When a refresh fails, an unexpired last-known value remains visible as `stale`; after its reset time passes it becomes `Unavailable`. The status widget and local Codex usage continue to work offline even if Claude usage cannot refresh.

## 8. Claude Code hooks

The installer tries to safely merge the hooks into:

```text
~/.claude/settings.json
```

If the file exists, it makes a backup:

```text
~/.claude/settings.json.bak.<timestamp>
```

Added events:

- `UserPromptSubmit`
- `PreToolUse`
- `PostToolUse`
- `Notification`
- `Stop`
- `StopFailure`

A manual example is in:

```text
examples/claude-settings-snippet.json
```

## 9. Codex CLI hooks

The installer tries to safely merge the hooks into:

```text
~/.codex/hooks.json
```

If the file exists, it makes a backup:

```text
~/.codex/hooks.json.bak.<timestamp>
```

Added events:

- `UserPromptSubmit`
- `PreToolUse`
- `PermissionRequest`
- `PostToolUse`
- `SubagentStop`
- `Stop`

For the Codex CLI you may still need to enter `/hooks` and approve the hooks.

A manual example is in:

```text
examples/codex-hooks.json
```

## 10. Troubleshooting

Run the doctor:

```bash
~/.local/bin/ai-agent-status-doctor
```

Check the panel output:

```bash
~/.local/bin/ai-agent-status-panel
```

Check the files:

```bash
ls -la ~/.cache/ai-cli-status-monitor/
ls -la ~/.cache/ai-cli-status-monitor/last_payloads/
ls -la ~/.cache/ai-cli-status-monitor/debug_payloads/
cat ~/.cache/ai-cli-status-monitor/usage_limits.json
cat ~/.cache/ai-cli-status-monitor/widget.log
```

Test the hooks:

```bash
~/.local/bin/ai-agent-status-hook --agent claude --test
~/.local/bin/ai-agent-status-hook --agent codex --test
```

If Codex does not fire the hooks, enter `/hooks` and approve/trust the new hooks.

With multiple consoles running, statuses are kept separately in:

```text
~/.cache/ai-cli-status-monitor/statuses/
```

The `claude.json` and `codex.json` files still point to the latest status of each agent, for compatibility with older scripts.

The widget plays `notification.mp3` only when entering a state that requires your interaction, e.g. waiting for approval or waiting for a reply. If you hear no sound, check `~/.cache/ai-cli-status-monitor/widget.log`; the widget uses whatever local player is available, e.g. `mpv`, `ffplay`, `mpg123`, `gst-play-1.0` or `paplay`.

If the widget is not above all windows, check:

```bash
command -v wmctrl
```

## 11. Limitations

- The status is event-based; it is not a real view of the "model's thoughts".
- The `thinking` status is inferred from prompts and tool events.
- The `waiting for you` status depends on the available notification, stop and permission events.
- Usage-limit integrations are best-effort and may temporarily show `Unavailable` if Claude or Codex changes its private local/API data shape.
- Claude usage requires an active Claude Code OAuth login; API-key spend and billing limits are outside this widget's scope.
- Always-on-top and all-workspaces work best on X11/Cinnamon.
- Wayland may limit the sticky/above/skip-taskbar behavior.
- Each AI session has its own row. Session identity comes from `session_id` (Claude), and when it is missing (Codex) — from the POSIX session leader (the terminal's shell), so one session = one stable row, even without `session_id`.
- The `→` switch matches a window by the terminal process PID, and when a single emulator process owns multiple windows (e.g. gnome-terminal) it disambiguates them by window title. Full certainty comes from a one-process-per-window terminal (alacritty, kitty, xterm); `wmctrl` cannot switch to a specific tab. It requires `wmctrl`/X11; under Wayland, tmux, screen or ssh it may not hit the right window. A diagnostic entry lands in `widget.log`.
