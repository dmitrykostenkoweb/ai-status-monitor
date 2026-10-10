# ai-cli-status-monitor

<img src="assets/lockup.gif" alt="AI Status Monitor lockup" width="100%" />

A mini floating widget for **Linux, macOS and Windows** that shows the last known status of the Claude Code CLI and the Codex CLI.

It is a lightweight local tool: Python 3 and Qt (PySide6). No Electron, no web server and no Docker. Network access is limited to the documented update check and Claude Code usage lookup.

## 1. What it is

`ai-cli-status-monitor` hooks into the Claude Code and Codex CLIs, writes statuses to `~/.cache/ai-cli-status-monitor/`, and a small Qt widget reads the freshest entries and shows one or two lines of status.

Example:

```text
Claude: reading code [unitbox-front] 14:22
Codex: running command [ai-cli-status-monitor] 14:23
```

## 2. Appearance

The widget has a **comic-book** look: thick ink outlines, hard offset shadows, halftone dots and Bangers / Comic Neue / Space Mono type (bundled, SIL Open Font License). **Dark** is the default; a **light** theme is one switch away in Settings (`Light theme`, or `AI_STATUS_THEME=light`).

- **Main card**: a halftone header with a slowly sweeping radar mark, `AI Agents Status!`, a tilted state badge (`● LIVE` / `▲ N ALERT!` / `● IDLE`), a `⚙` settings button and a red `X`. Below it are the usage limits: one inked block per provider (Anthropic, OpenAI) with its logo on a coloured disc and halftone quota bars. Bars are green below 75 %, orange from 75 % and red from 90 %. Click a provider disc to refresh its usage.
- **Session windows** (default): every active session (run) gets its own draggable card, docked in a column under the widget. A card shows:
  - a yellow `➜` button that jumps to that terminal;
  - the agent's logo disc and its stroked name;
  - a status chip: yellow while analyzing/reading, green while coding, red when it waits for you or hit an error;
  - the `project · time` line.

  A card waiting for you pulses its outline red. A dragged card stays where you drop it (remembered per session; right-click → `Dock under the widget` brings it back). Turn session windows off in Settings for the classic list below.
- **Classic list**: the same rows inside the main card (up to 5), with a `+N finished, hidden automatically` footer. When nothing runs, and for ~3 s at startup, the "AI Status Monitor!" lockup shows instead.
- **GIF stickers**: a tilted polaroid with a reaction GIF, a sound-effect caption (`HMMM…`, `CLACK!`, `AHEM!`) and a speech bubble pops out of each card's top-right corner (see [GIF stickers](#7d-gif-stickers)).
- When a newer version is published on GitHub, a yellow `UPDATE ↑` button appears in the header (see [Updates](#7b-updates)).
- **Settings window** (`⚙`, or right-click → `Settings…`): shown agents, notification sound, visible rows, session windows, light theme, stickers and timing. Changes apply instantly and are saved to the runtime `.env`.
- Right-click menu: `Settings…`, `Show agents` (Claude Code + Codex / Claude Code only / Codex only), `Serious mode (no stickers)`, `Dock all session windows`, `Reload`, `Open logs folder`, `Check for updates` / `Update to …`, `Quit`.

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

The installer itself is `install.py` (Python 3.9+, cross-platform); `install.sh` only adds the `curl | bash` bootstrap on Linux and macOS.

### Requirements

- Python 3.9+ (the hook and helpers use only the standard library).
- The widget UI uses **PySide6** (Qt). If the Python running the installer cannot import it, the installer creates a private venv in the data directory (`<data dir>/venv`) and installs `PySide6-Essentials` there. This is a one-time download of about 100 MB. Set `AI_STATUS_WIDGET_PYTHON=/path/to/python` to use your own interpreter, or `AI_STATUS_SKIP_PIP=1` to skip the download (hooks and status files work without Qt).
- Linux: `wmctrl` (the `→` window switch, and a fallback for always-on-top) and `libxcb-cursor0` (needed by Qt 6.5+ on X11). On Debian/Ubuntu/Mint, `python3-venv` lets the installer create the venv: `sudo apt install python3-venv libxcb-cursor0 wmctrl`.

### macOS and Windows

macOS uses the same commands and directories as Linux (`~/.local/bin`, `~/.cache`, `~/.config`, `~/.local/share`). Autostart is a LaunchAgent (`~/Library/LaunchAgents/com.github.ai-cli-status-monitor.widget.plist`), and Claude usage limits are read from the login Keychain (`Claude Code-credentials`).

Windows (PowerShell; needs [Python 3.9+](https://www.python.org/downloads/) and, without a checkout, Git):

```powershell
irm https://raw.githubusercontent.com/dmitrykostenkoweb/ai-status-monitor/main/install.ps1 | iex
# or, from a clone:
powershell -ExecutionPolicy Bypass -File install.ps1
```

On Windows the scripts go to `%LOCALAPPDATA%\ai-cli-status-monitor\bin` (with `.cmd` wrappers such as `ai-agent-status-doctor.cmd`). The cache and data directories are under `%LOCALAPPDATA%\ai-cli-status-monitor`, and the runtime `.env` is in `%APPDATA%\ai-cli-status-monitor`. Autostart uses the `HKCU\…\Run` registry key. The hooks are written as `"<python.exe>" "<bin>/ai-agent-status-hook" --agent claude|codex`.

The installer is idempotent, so re-running it (or `ai-agent-status-update`) safely refreshes an existing install and restarts the widget.

The installer tries to configure the hooks automatically:

- Claude Code: `~/.claude/settings.json`
- Codex CLI: `~/.codex/hooks.json`
- autostart: `~/.config/autostart/ai-cli-status-widget.desktop` (Linux), a LaunchAgent (macOS), the `HKCU` Run key (Windows)
- launcher in the Cinnamon menu (Linux): `AI CLI Status Widget`
- launcher icon: `~/.local/share/pixmaps/ai-cli-status-widget.png`
- notification sound: `~/.local/share/ai-cli-status-monitor/notification.mp3`
- OpenAI/Codex logo: `~/.local/share/ai-cli-status-monitor/openai-logo.svg`
- Anthropic/Claude logo: `~/.local/share/ai-cli-status-monitor/anthropic-logo.png`
- runtime configuration: `~/.config/ai-cli-status-monitor/.env`
- window position and legacy-config compatibility: `~/.config/ai-cli-status-monitor/widget.json`

The installer never runs `sudo`. If something is missing on Linux, it prints the command:

```bash
sudo apt install python3-venv libxcb-cursor0 wmctrl
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
- `wmctrl` and `libxcb-cursor0` (Linux)
- that the widget's interpreter can import PySide6
- the hook's test mode
- the installed version and whether an update is available

## 7. Autostart

The installer creates:

```text
~/.config/autostart/ai-cli-status-widget.desktop
```

The widget should start automatically after you log in. On macOS the installer adds a LaunchAgent (`~/Library/LaunchAgents/com.github.ai-cli-status-monitor.widget.plist`). On Windows it adds the `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\ai-cli-status-monitor` registry value, which starts the widget with `pythonw.exe`, so no console window appears.

## 7a. `.env` configuration

Public defaults live in `.env.default`. Your local `.env` is ignored by Git. On the first install a private `~/.config/ai-cli-status-monitor/.env` is created with `0600` permissions; subsequent installs do not overwrite it.

Most of these can also be changed from the widget's **Settings** window (`⚙` in the header), which rewrites only the changed keys in the runtime `.env`. Title, card width and directories still need a manual edit and a widget restart.

Available variables:

- `AI_STATUS_CACHE_DIR`, `AI_STATUS_CONFIG_DIR`, `AI_STATUS_DATA_DIR` — data directories
- `AI_STATUS_TITLE` (default `AI Agents Status!`), `AI_STATUS_CARD_WIDTH` (default `420`), `AI_STATUS_MAX_ROWS` — widget appearance. Re-installing upgrades the previous defaults (`344`, `AI Agents Status`) to the new ones; values you changed are kept.
- `AI_STATUS_SOUND_ENABLED` — `true`/`false`, `yes`/`no`, `on`/`off` or `1`/`0`
- `AI_STATUS_STALE_AFTER_SECONDS`, `AI_STATUS_HIDE_DONE_AFTER_SECONDS`, `AI_STATUS_IDLE_AFTER_SECONDS`, `AI_STATUS_HIDE_STALE_AFTER_SECONDS` — timeouts
- `AI_STATUS_THEME` — `dark` (default) or `light` comic theme
- `AI_STATUS_AGENTS` — which agents the widget shows: `claude,codex` (default, also `all`), `claude` or `codex`. Hidden agents get no rows, no usage bars, no sounds and no usage requests. The right-click `Show agents` menu changes it live and saves the choice to the runtime `.env` (a value exported in the process still wins on the next start)
- `AI_STATUS_SESSION_WINDOWS` — `true` (default): each session in its own draggable window; `false`: the classic list inside the widget
- `AI_STATUS_STICKER_ROTATE_SECONDS` — how often a working session window swaps to a new GIF (default `120`, `0` = never)
- `AI_STATUS_SERIOUS_MODE` — `true` turns GIF stickers off (see [GIF stickers](#7d-gif-stickers))
- `AI_STATUS_KLIPY_API_KEY` — optional KLIPY API key for random sticker GIFs; empty = local GIFs only
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

`ai-agent-status-update` pulls the source clone recorded at install time (`~/.local/share/ai-cli-status-monitor/install_source`), or clones a fresh copy into `~/.local/share/ai-cli-status-monitor/src` if none is found, then re-runs `install.py` (which restarts the widget).

The repository is configurable for forks/mirrors via `AI_STATUS_UPDATE_REPO` (`owner/repo`) and `AI_STATUS_UPDATE_BRANCH`.

## 7c. Usage limits

The widget refreshes both account limits automatically every two minutes. Click the Claude or Codex logo to refresh only that provider; the active logo spins until its refresh finishes. The controls remain temporarily disabled while a refresh is already running.

Claude's `5h`, `Weekly` and `Fable` bars are stacked beside the Claude logo (the `Fable` bar appears only when the account has a separate weekly Fable allowance); Codex's `Weekly` bar sits beside the Codex logo. Progress fill is green below 60% utilization, orange from 60% through 84%, and red from 85% upward. The unused track remains neutral.

- Claude Code: 5-hour and weekly utilization from Claude Code's authenticated usage endpoint
- Codex: weekly utilization queried through the authenticated installed Codex CLI app-server; recent local `rate_limits` events under `~/.codex/sessions/` remain a compatibility fallback
- cache: normalized, non-secret values in `~/.cache/ai-cli-status-monitor/usage_limits.json`

The Claude request reuses the OAuth access token already stored by Claude Code in `~/.claude/.credentials.json`. The monitor reads it only in memory for the request; it does not copy the token into its cache or logs. Codex authentication remains owned by the installed CLI: the monitor neither reads nor copies its OAuth credential. API-key billing quotas are not supported.

Provider failures are independent. When a refresh fails, an unexpired last-known value remains visible as `stale`; after its reset time passes it becomes `Unavailable`. The status widget and local Codex usage continue to work offline even if Claude usage cannot refresh.

## 7d. GIF stickers

**With session windows (default)** every session window carries its own sticker, sticking out of its top-right corner. It stays up while the session works or waits, gets a new GIF only when the sticker status changes (e.g. `coding` → `waiting`), and tucks away when the session is `done` or `idle`.

**With the classic list**, a single sticker pops out of the widget's top-right corner when an agent's status changes, stays for 4 seconds and tucks away. `waiting` and `error` stickers stay until the status changes, because they need your attention. Hovering an agent row brings its last sticker back. The sticker lives in its own click-through window, so the widget never moves and clicks still reach the buttons underneath. It needs a compositing desktop (Cinnamon, GNOME, KDE, macOS and Windows have one by default).

| Sticker | Shown for |
|---|---|
| `analyzing` | thinking, reading, analyzing |
| `coding` | editing files, running commands |
| `waiting` | waiting for approval / your answer |
| `done` | finished |
| `error` | API or tool error |
| `limit` | a usage bar reaches 90% (once per limit window) |
| `idle` | a silent session turns idle |

**Getting a free KLIPY key (≈2 minutes):** open **⚙ Settings → Stickers → Get a free key…** (or right-click the widget → `Get GIFs from KLIPY (free key)…`, shown while no key is set). The guide walks you through it:

1. **Open the KLIPY Partner Panel** (<https://partner.klipy.com>) and sign up.
2. **Add your platform** — the guide has `Copy` buttons for the platform name (`AI Status Monitor`), website (this repository) and a ready-made description of the integration. Read and accept the KLIPY API Terms.
3. **Create an API key** — key name `AI-Status-Monitor-Linux`, URL = this repository, leave **"Enable the Ads API" OFF**.
4. **Paste the key and press `Test & save`** — the widget runs one test search and tells you whether the key works, was rejected, hit its hourly limit, or KLIPY could not be reached. Only a working key is saved.

Free test keys allow 100 requests per hour; the widget stays under 60.

**Where the GIFs come from:**

1. **KLIPY (optional)** — paste a KLIPY API key (free test keys at <https://partner.klipy.com>) into **Settings → Stickers**. On each status change the widget searches KLIPY for a phrase that fits the status (e.g. `thinking`, `typing fast`, `victory dance`) and shows a random GIF. Following KLIPY's [integration requirements](https://docs.klipy.com/integration-requirements), each GIF is loaded directly from KLIPY's URL into memory and is **never stored on disk**; only the search result list (URLs) is reused for an hour to spare the API. Requests run in the background; offline or on any error the widget silently falls back to the local pool. Stickers showing a KLIPY GIF carry a small `KLIPY` mark ("Powered by KLIPY").
2. **Local pool** — any `.gif`, `.webp`, `.png` or `.jpg` in `~/.local/share/ai-cli-status-monitor/gifs/<sticker>/`, e.g. `gifs/waiting/skeleton.gif`. The installer seeds `gifs/analyzing/` and never overwrites your files.
3. **Placeholder** — with neither, the sticker shows stripes in the status colour.

**Variety:** the widget remembers the last 200 GIFs shown (across all stickers and windows) and never re-picks them, deals search phrases and bubble lines like a shuffled deck (each one once before any repeats), and asks KLIPY for 50 results on a random page 1–3 — so each phrase can yield ~150 GIFs. Every sticker has 14–22 bubble lines and 12–15 search phrases. While an agent keeps working, its session window swaps to a new GIF every 2 minutes (**Settings → Stickers → New GIF every**, `0` = never), and right-click on a session window → `Show another GIF` swaps it right away. New searches are capped at 60 per hour (the free KLIPY test key allows 100/hour); past that the widget picks from results it already has. A ready-made **Polish** set lives in [`examples/stickers.pl.json`](examples/stickers.pl.json) — copy it to `~/.config/ai-cli-status-monitor/stickers.json` and restart the widget. Bubble texts and KLIPY search phrases can be overridden per sticker in that file:

```json
{
  "bubbles": {"waiting": ["Dima? Halo?", "halo? jest tam kto?"], "done": ["gotowe!"]},
  "queries": {"coding": ["hacker typing", "cat keyboard"]}
}
```

**Serious mode** (Settings, right-click menu or `AI_STATUS_SERIOUS_MODE=true`) turns stickers off completely — no stickers and no KLIPY requests. To preview every sticker: **Settings → Show test sticker**, or `bin/ai-agent-status-widget --sticker all` (or `--sticker waiting`, …).

The KLIPY key is stored in the runtime `.env` (mode `0600`) and is never written to logs.

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

The widget plays `notification.mp3` only when entering a state that requires your interaction, e.g. waiting for approval or waiting for a reply. If you hear no sound, check `~/.cache/ai-cli-status-monitor/widget.log`; the widget uses whatever player is available: `afplay` on macOS, PowerShell (Windows Media Player engine) on Windows, and on Linux `mpv`, `ffplay`, `mpg123`, `gst-play-1.0` or `paplay`.

If the widget is not above all windows on Linux, check that it runs on X11 (`(xcb)` in the log). Full-screen windows (videos, presentations) still cover it, by design of the window manager.

```bash
grep "widget started" ~/.cache/ai-cli-status-monitor/widget.log | tail -1
```

If the widget does not start on Linux with `Could not load the Qt platform plugin "xcb"` (or the doctor reports it), install `libxcb-cursor0`.

## 11. Limitations

- The status is event-based; it is not a real view of the "model's thoughts".
- The `thinking` status is inferred from prompts and tool events.
- The `waiting for you` status depends on the available notification, stop and permission events.
- Usage-limit integrations are best-effort and may temporarily show `Unavailable` if Claude or Codex changes its private local/API data shape.
- Claude usage requires an active Claude Code OAuth login; API-key spend and billing limits are outside this widget's scope.
- Always-on-top works on every OS. Staying visible on *every* workspace/desktop is enforced only on Linux/X11, where the widget re-asserts "above" and "all workspaces" every second (Cinnamon/Muffin and GNOME/Mutter drop "above" now and then). On macOS and Windows the widget stays on the desktop/Space where it was opened.
- On Wayland the widget runs through XWayland when `libxcb-cursor0` is installed, because Wayland does not let apps place their own windows (docked session windows, sticker overlay).
- Each AI session has its own row. Session identity comes from `session_id` (Claude). When it is missing (Codex), it comes from the terminal: the POSIX session leader (the terminal's shell) on Linux/macOS, or the console window on Windows. So one session = one stable row, even without `session_id`.
- The `→` switch matches a window by the terminal process PID:
  - Linux: `wmctrl`/X11. When one emulator process owns several windows (e.g. gnome-terminal), the window title disambiguates them. Full certainty comes from a one-process-per-window terminal (alacritty, kitty, xterm).
  - macOS: System Events. It brings the terminal app to the front and raises the window whose title contains the project. Grant Accessibility access to your Python/terminal if it asks.
  - Windows: Win32 `SetForegroundWindow`. It targets the Windows Terminal or console window.

  No platform can switch to a specific tab. Under tmux, screen or ssh it may not hit the right window. A diagnostic entry lands in `widget.log`.
