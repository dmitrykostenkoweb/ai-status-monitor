#!/usr/bin/env bash
# Linux/macOS entry point. The installer itself is install.py (cross-platform);
# this wrapper only adds the `curl ... | bash` bootstrap and picks python3.
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

python_bin="${AI_STATUS_PYTHON:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3.9+ and try again." >&2
  exit 1
fi

# Bootstrap path: no local checkout (piped install) -> clone into the managed
# source dir and hand off to its installer.
if [[ -z "$project_dir" || ! -f "$project_dir/install.py" ]]; then
  repo_slug="${AI_STATUS_UPDATE_REPO:-dmitrykostenkoweb/ai-status-monitor}"
  repo_branch="${AI_STATUS_UPDATE_BRANCH:-main}"
  data_dir_boot="${AI_STATUS_DATA_DIR:-$HOME/.local/share/ai-cli-status-monitor}"
  data_dir_boot="${data_dir_boot/#\~/$HOME}"
  managed_src="$data_dir_boot/src"
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required to install via curl. Install git and try again." >&2
    exit 1
  fi
  echo "Cloning https://github.com/${repo_slug}.git ..."
  rm -rf "$managed_src"
  mkdir -p "$(dirname "$managed_src")"
  git clone --branch "$repo_branch" --depth 1 "https://github.com/${repo_slug}.git" "$managed_src"
  exec "$python_bin" "$managed_src/install.py" "$@"
fi

exec "$python_bin" "$project_dir/install.py" "$@"
