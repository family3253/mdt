#!/usr/bin/env bash
set -euo pipefail

# Watch Aether-related skill/script for changes and auto-push after debounce.
# Requires: inotify-tools

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
WATCH_DIRS=(
  "$WORKSPACE_DIR/skills/aether-pool-maintainer"
  "$WORKSPACE_DIR/scripts"
)
PUSH_SCRIPT="$WORKSPACE_DIR/scripts/push_aether_skills_to_github.sh"
DEBOUNCE_SECONDS=10

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "ERROR: inotifywait not found. Install: sudo apt-get update && sudo apt-get install -y inotify-tools" >&2
  exit 1
fi

if [[ ! -x "$PUSH_SCRIPT" ]]; then
  echo "ERROR: push script not executable: $PUSH_SCRIPT" >&2
  exit 1
fi

echo "[aether-autopush] watching: ${WATCH_DIRS[*]}"

trigger_push() {
  echo "[aether-autopush] change detected, waiting ${DEBOUNCE_SECONDS}s..."
  sleep "$DEBOUNCE_SECONDS"
  echo "[aether-autopush] pushing..."
  "$PUSH_SCRIPT"
  echo "[aether-autopush] done"
}

inotifywait -m -r "${WATCH_DIRS[@]}" \
  --event close_write,move,create,delete \
  --format '%w%f' \
| while read -r changed; do
    case "$changed" in
      *.swp|*.tmp|*~|*.bak|*/__pycache__/*|*.pyc|*/scripts/logs/*|*/runtime/logs/*) continue;;
    esac
    # only react to the relevant script within scripts/
    if [[ "$changed" == *"scripts/aether_gpt_pool_maintain.py"* ]] || [[ "$changed" == *"skills/aether-pool-maintainer"* ]]; then
      trigger_push
    fi
  done
