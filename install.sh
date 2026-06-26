#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="${HOME}/.local/bin"
cache_dir="${HOME}/.cache/ai-cli-status-monitor"
config_dir="${HOME}/.config/ai-cli-status-monitor"
data_dir="${HOME}/.local/share/ai-cli-status-monitor"
autostart_dir="${HOME}/.config/autostart"
applications_dir="${HOME}/.local/share/applications"
icons_dir="${HOME}/.local/share/icons/hicolor/scalable/apps"
pixmaps_dir="${HOME}/.local/share/pixmaps"
desktop_file="${autostart_dir}/ai-cli-status-widget.desktop"
app_desktop_file="${applications_dir}/ai-cli-status-widget.desktop"
toggle_desktop_file="${applications_dir}/ai-cli-status-widget-toggle.desktop"
icon_file="${icons_dir}/ai-cli-status-widget.svg"
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
  ai-agent-status-hook
  ai-agent-status-panel
  ai-agent-status-widget
  ai-agent-status-widget-start
  ai-agent-status-widget-stop
  ai-agent-status-widget-toggle
  ai-agent-status-doctor
)

for script in "${scripts[@]}"; do
  cp "$project_dir/bin/$script" "$bin_dir/$script"
  chmod +x "$bin_dir/$script"
done

rm -rf "$bin_dir/ai_agent_status_lib"
cp -R "$project_dir/bin/ai_agent_status_lib" "$bin_dir/ai_agent_status_lib"

cp "$project_dir/assets/ai-cli-status-widget.svg" "$icon_file"
cp "$project_dir/assets/ai-cli-status-widget.png" "$png_icon_file"
cp "$project_dir/assets/notification.mp3" "$notification_sound_file"
cp "$project_dir/assets/openai-logo.svg" "$openai_logo_file"
cp "$project_dir/assets/anthropic-logo.png" "$anthropic_logo_file"

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

cat >"$toggle_desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=AI CLI Status Widget Toggle
Comment=Show or hide the AI CLI status widget
Exec=$bin_dir/ai-agent-status-widget-toggle
Icon=$png_icon_file
Terminal=false
Categories=Utility;
StartupNotify=false
EOF

chmod +x "$app_desktop_file" "$toggle_desktop_file" "$desktop_file"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

python3 - "$HOME" <<'PY'
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


home = Path(sys.argv[1])
bin_dir = home / ".local" / "bin"
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
widget_config_defaults = {
    "sound_enabled": True,
    "stale_after_seconds": 180,
    "hide_done_after_seconds": 180,
    "idle_after_seconds": 600,
    "hide_stale_after_seconds": 900,
    "theme": "dark",
}


def merge_widget_config() -> None:
    path = home / ".config" / "ai-cli-status-monitor" / "widget.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError as error:
            made = backup(path)
            print(f"⚠️  Cannot merge widget config because JSON is invalid: {path}")
            print(f"   Error: {error}")
            if made:
                print(f"   Backup created: {made}")
            data = {}
    changed = False
    for key, value in widget_config_defaults.items():
        if key not in data:
            data[key] = value
            changed = True
    if data.get("hide_done_after_seconds") == 60:
        data["hide_done_after_seconds"] = 180
        changed = True
    if changed or not path.exists():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ Widget config installed: {path}")


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

merge_widget_config()

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
echo "Installed ai-cli-status-monitor."
echo
echo "Commands:"
echo "  $bin_dir/ai-agent-status-widget"
echo "  $bin_dir/ai-agent-status-widget-toggle"
echo "  $bin_dir/ai-agent-status-doctor"
echo "  $bin_dir/ai-agent-status-panel"
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
echo "Application launchers installed:"
echo "  $app_desktop_file"
echo "  $toggle_desktop_file"
echo "Icon installed:"
echo "  $png_icon_file"
echo "Notification sound installed:"
echo "  $notification_sound_file"
echo "Agent logos installed:"
echo "  $openai_logo_file"
echo "  $anthropic_logo_file"
echo
echo "Run doctor:"
echo "  $bin_dir/ai-agent-status-doctor"
echo

if [[ "$gtk_ok" -eq 1 ]]; then
  if [[ -n "${DISPLAY:-}" ]]; then
    "$bin_dir/ai-agent-status-widget-start" || true
  else
    echo "DISPLAY is not set, widget was not started now. It will start on desktop login."
  fi
else
  echo "GTK is missing, widget was not started."
fi

echo
echo "For Codex CLI, open /hooks and trust the new hook if Codex asks for review."
