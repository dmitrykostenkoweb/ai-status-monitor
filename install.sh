#!/usr/bin/env bash
set -euo pipefail

# Resolve our own location. When piped through `curl ... | bash` there is no
# script file, so BASH_SOURCE is unset (would trip `set -u`) — guard for that and
# leave project_dir empty, which triggers the bootstrap clone below.
self="${BASH_SOURCE[0]:-}"
if [[ -n "$self" && -f "$self" ]]; then
  project_dir="$(cd "$(dirname "$self")" && pwd)"
else
  project_dir=""
fi

# Bootstrap path: no local checkout (piped install) -> clone into the managed
# source dir and hand off to its install.sh.
if [[ -z "$project_dir" || ! -f "$project_dir/bin/ai-agent-status-hook" ]]; then
  repo_slug="${AI_STATUS_UPDATE_REPO:-dmitrykostenkoweb/ai-status-monitor}"
  repo_branch="${AI_STATUS_UPDATE_BRANCH:-main}"
  data_dir_boot="${AI_STATUS_DATA_DIR:-$HOME/.local/share/ai-cli-status-monitor}"
  data_dir_boot="${data_dir_boot/#\~/$HOME}"
  managed_src="$data_dir_boot/src"
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required to install via curl. Install it with: sudo apt install git" >&2
    exit 1
  fi
  echo "Cloning https://github.com/${repo_slug}.git ..."
  rm -rf "$managed_src"
  mkdir -p "$(dirname "$managed_src")"
  git clone --branch "$repo_branch" --depth 1 "https://github.com/${repo_slug}.git" "$managed_src"
  exec "$managed_src/install.sh"
fi

config_keys=(
  AI_STATUS_CACHE_DIR AI_STATUS_CONFIG_DIR AI_STATUS_DATA_DIR
  AI_STATUS_TITLE AI_STATUS_CARD_WIDTH AI_STATUS_MAX_ROWS
  AI_STATUS_SOUND_ENABLED AI_STATUS_STALE_AFTER_SECONDS
  AI_STATUS_HIDE_DONE_AFTER_SECONDS AI_STATUS_IDLE_AFTER_SECONDS
  AI_STATUS_HIDE_STALE_AFTER_SECONDS AI_STATUS_THEME
)
explicit_config_keys=()
for key in "${config_keys[@]}"; do
  if [[ -v "$key" ]]; then
    explicit_config_keys+=("$key")
  fi
done
export AI_STATUS_INSTALL_EXPLICIT_KEYS="${explicit_config_keys[*]}"

runtime_env="${AI_STATUS_ENV_FILE:-${HOME}/.config/ai-cli-status-monitor/.env}"
source_env="$project_dir/.env.default"
if [[ -f "$project_dir/.env" ]]; then
  source_env="$project_dir/.env"
fi
source "$project_dir/bin/ai-agent-status-env"
runtime_env="$(ai_status_expand_path "$runtime_env")"
if [[ -f "$runtime_env" ]]; then
  ai_status_load_env "$runtime_env"
else
  ai_status_load_env "$source_env"
fi
export AI_STATUS_ENV_FILE="$runtime_env"

bin_dir="${HOME}/.local/bin"
cache_dir="$AI_STATUS_CACHE_DIR"
config_dir="$AI_STATUS_CONFIG_DIR"
data_dir="$AI_STATUS_DATA_DIR"
autostart_dir="${HOME}/.config/autostart"
applications_dir="${HOME}/.local/share/applications"
icons_dir="${HOME}/.local/share/icons/hicolor/scalable/apps"
pixmaps_dir="${HOME}/.local/share/pixmaps"
desktop_file="${autostart_dir}/ai-cli-status-widget.desktop"
app_desktop_file="${applications_dir}/ai-cli-status-widget.desktop"
icon_file="${icons_dir}/ai-cli-status-widget.png"
png_icon_file="${pixmaps_dir}/ai-cli-status-widget.png"
notification_sound_file="${data_dir}/notification.mp3"
openai_logo_file="${data_dir}/openai-logo.svg"
anthropic_logo_file="${data_dir}/anthropic-logo.png"

mkdir -p \
  "$bin_dir" \
  "$cache_dir/last_payloads" \
  "$cache_dir/debug_payloads" \
  "$config_dir" \
  "$data_dir" \
  "$autostart_dir" \
  "$applications_dir" \
  "$icons_dir" \
  "$pixmaps_dir"

scripts=(
  ai-agent-status-env
  ai-agent-status-hook
  ai-agent-status-panel
  ai-agent-status-widget
  ai-agent-status-widget-start
  ai-agent-status-widget-stop
  ai-agent-status-doctor
  ai-agent-status-update
)

for script in "${scripts[@]}"; do
  cp "$project_dir/bin/$script" "$bin_dir/$script"
  chmod +x "$bin_dir/$script"
done

rm -rf "$bin_dir/ai_agent_status_lib"
cp -R "$project_dir/bin/ai_agent_status_lib" "$bin_dir/ai_agent_status_lib"

cp "$project_dir/assets/ai-cli-status-widget.png" "$icon_file"
cp "$project_dir/assets/ai-cli-status-widget.png" "$png_icon_file"
cp "$project_dir/assets/notification.mp3" "$notification_sound_file"
cp "$project_dir/assets/openai-logo.svg" "$openai_logo_file"
cp "$project_dir/assets/anthropic-logo.png" "$anthropic_logo_file"

# Record the version and where we installed from, so ai-agent-status-update can
# pull the right clone and the widget can tell when a newer version is published.
cp "$project_dir/VERSION" "$data_dir/VERSION"
printf '%s\n' "$project_dir" >"$data_dir/install_source"

cat >"$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=AI CLI Status Widget
Comment=Floating status widget for Claude Code and Codex CLI
Exec=$bin_dir/ai-agent-status-widget
Icon=$png_icon_file
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

cat >"$app_desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=AI CLI Status Widget
Comment=Open floating status widget for Claude Code and Codex CLI
Exec=$bin_dir/ai-agent-status-widget-start
Icon=$png_icon_file
Terminal=false
Categories=Utility;
StartupNotify=false
EOF

chmod +x "$app_desktop_file" "$desktop_file"

# Remove the retired toggle launcher/script from earlier installs.
rm -f "${applications_dir}/ai-cli-status-widget-toggle.desktop" "${bin_dir}/ai-agent-status-widget-toggle"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

python3 - "$HOME" "$runtime_env" "$source_env" "$config_dir" "$project_dir" <<'PY'
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


home = Path(sys.argv[1])
runtime_env = Path(sys.argv[2])
source_env = Path(sys.argv[3])
config_dir = Path(sys.argv[4])
project_dir = Path(sys.argv[5])
bin_dir = home / ".local" / "bin"
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

sys.path.insert(0, str(bin_dir))
from ai_agent_status_lib.env_config import DEFAULT_VALUES  # noqa: E402
from ai_agent_status_lib.env_config import LEGACY_KEYS  # noqa: E402
from ai_agent_status_lib.env_config import load_settings  # noqa: E402
from ai_agent_status_lib.env_config import parse_dotenv  # noqa: E402
from ai_agent_status_lib.env_config import serialize_env  # noqa: E402


def read_legacy_widget_config() -> dict[str, object]:
    path = config_dir / "widget.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as error:
        print(f"⚠️  Cannot migrate widget config: {path}: {error}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


def install_environment_config() -> None:
    if runtime_env.exists():
        print(f"✅ Environment config preserved: {runtime_env}")
        return

    legacy = read_legacy_widget_config()
    source_values = parse_dotenv(source_env, lambda message: print(f"⚠️  {message}"))
    default_values = parse_dotenv(project_dir / ".env.default")
    explicit_keys = set(os.environ.get("AI_STATUS_INSTALL_EXPLICIT_KEYS", "").split())

    # Values unchanged from the public template are defaults, not intentional
    # overrides, so legacy widget customizations may take precedence on migration.
    for env_key, legacy_key in LEGACY_KEYS.items():
        if env_key in explicit_keys or legacy_key not in legacy:
            continue
        if source_values.get(env_key, DEFAULT_VALUES[env_key]) == default_values.get(env_key, DEFAULT_VALUES[env_key]):
            source_values.pop(env_key, None)

    process_values = {"HOME": str(home)}
    for key in explicit_keys:
        if key in DEFAULT_VALUES and key in os.environ:
            process_values[key] = os.environ[key]

    warnings: list[str] = []
    settings = load_settings(
        environ=process_values,
        env_path=source_env,
        dotenv_values=source_values,
        legacy=legacy,
        diagnostic=warnings.append,
    )
    for message in warnings:
        print(f"⚠️  {message}")
    runtime_env.parent.mkdir(parents=True, exist_ok=True)
    runtime_env.write_text(serialize_env(settings.as_env()), encoding="utf-8")
    runtime_env.chmod(0o600)
    print(f"✅ Environment config installed: {runtime_env}")


def snippet(command: str, events: tuple[str, ...], codex: bool = False) -> str:
    hooks = {}
    for event in events:
        group = {"hooks": [{"type": "command", "command": command}]}
        if codex and event in {"PreToolUse", "PermissionRequest", "PostToolUse", "SubagentStop"}:
            group["matcher"] = "*"
        hooks[event] = [group]
    return json.dumps({"hooks": hooks}, ensure_ascii=False, indent=2)


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, target)
    return target


def load_or_create_json(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        return {}, True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        made = backup(path)
        print(f"⚠️  Cannot merge hooks into invalid JSON: {path}")
        print(f"   Error: {error}")
        if made:
            print(f"   Backup created: {made}")
        raise
    if not isinstance(data, dict):
        made = backup(path)
        print(f"⚠️  Cannot merge hooks because top-level JSON is not an object: {path}")
        if made:
            print(f"   Backup created: {made}")
        raise TypeError("top-level JSON must be object")
    return data, False


def add_hooks(path: Path, command: str, events: tuple[str, ...], codex: bool = False) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data, created = load_or_create_json(path)
    except Exception:
        print("Manual snippet:")
        print(snippet(command, events, codex=codex))
        return False

    if not created:
        made = backup(path)
        if made:
            print(f"Backup created: {made}")

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        print(f"⚠️  Cannot merge hooks because {path} has non-object 'hooks'.")
        print("Manual snippet:")
        print(snippet(command, events, codex=codex))
        return False

    changed = False
    for event in events:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            print(f"⚠️  Cannot merge event {event} because it is not a list in {path}.")
            print("Manual snippet:")
            print(snippet(command, events, codex=codex))
            return False

        exists = False
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if isinstance(handler, dict) and handler.get("type") == "command" and handler.get("command") == command:
                    exists = True
                    break
            if exists:
                break

        if exists:
            continue

        group = {"hooks": [{"type": "command", "command": command}]}
        if codex and event in {"PreToolUse", "PermissionRequest", "PostToolUse", "SubagentStop"}:
            group["matcher"] = "*"
        groups.append(group)
        changed = True

    if changed or created:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ Hooks installed: {path}")
    else:
        print(f"✅ Hooks already installed: {path}")
    return True


claude_command = f"{bin_dir}/ai-agent-status-hook --agent claude"
codex_command = f"{bin_dir}/ai-agent-status-hook --agent codex"

install_environment_config()

add_hooks(
    home / ".claude" / "settings.json",
    claude_command,
    ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification", "Stop", "StopFailure"),
)

codex_config_toml = home / ".codex" / "config.toml"
if codex_config_toml.exists() and "[hooks" in codex_config_toml.read_text(encoding="utf-8", errors="ignore"):
    print("⚠️  ~/.codex/config.toml already contains inline hooks.")
    print("   Codex can load hooks from both config.toml and hooks.json, but may warn when both exist in one layer.")

add_hooks(
    home / ".codex" / "hooks.json",
    codex_command,
    ("UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "SubagentStop", "Stop"),
    codex=True,
)
PY

gtk_ok=0
if python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
PY
then
  gtk_ok=1
fi

wmctrl_ok=0
if command -v wmctrl >/dev/null 2>&1; then
  wmctrl_ok=1
fi

echo
echo "Installed ai-cli-status-monitor $(cat "$project_dir/VERSION")."
echo
echo "Commands:"
echo "  $bin_dir/ai-agent-status-widget"
echo "  $bin_dir/ai-agent-status-doctor"
echo "  $bin_dir/ai-agent-status-panel"
echo "  $bin_dir/ai-agent-status-update"
echo

if [[ "$gtk_ok" -ne 1 || "$wmctrl_ok" -ne 1 ]]; then
  echo "Optional dependencies missing or incomplete."
  echo "Install on Linux Mint with:"
  echo "  sudo apt install python3-gi gir1.2-gtk-3.0 wmctrl"
  echo
fi

echo "Autostart installed:"
echo "  $desktop_file"
echo
echo "Application launcher installed:"
echo "  $app_desktop_file"
echo "Icon installed:"
echo "  $png_icon_file"
echo "Notification sound installed:"
echo "  $notification_sound_file"
echo "Agent logos installed:"
echo "  $openai_logo_file"
echo "  $anthropic_logo_file"
echo "Environment config:"
echo "  $runtime_env"
echo
echo "Run doctor:"
echo "  $bin_dir/ai-agent-status-doctor"
echo

if [[ "$gtk_ok" -eq 1 ]]; then
  if [[ -n "${DISPLAY:-}" ]]; then
    # Restart so a reinstall/update picks up the new code instead of leaving the
    # already-running instance on the old version.
    "$bin_dir/ai-agent-status-widget-stop" >/dev/null 2>&1 || true
    "$bin_dir/ai-agent-status-widget-start" || true
  else
    echo "DISPLAY is not set, widget was not started now. It will start on desktop login."
  fi
else
  echo "GTK is missing, widget was not started."
fi

echo
echo "For Codex CLI, open /hooks and trust the new hook if Codex asks for review."
