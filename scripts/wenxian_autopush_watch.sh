#!/usr/bin/env bash
set -euo pipefail

# Watch skills/wenxian for changes and auto-push to GitHub after a short debounce.
# Requires: inotify-tools

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
WATCH_DIR="$WORKSPACE_DIR/skills/wenxian"
PUSH_SCRIPT="$WORKSPACE_DIR/scripts/push_wenxian_to_github.sh"

DEBOUNCE_SECONDS=10

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "ERROR: inotifywait not found. Install: sudo apt-get update && sudo apt-get install -y inotify-tools" >&2
  exit 1
fi

if [[ ! -x "$PUSH_SCRIPT" ]]; then
  echo "ERROR: push script not executable: $PUSH_SCRIPT" >&2
  exit 1
fi

cd "$WORKSPACE_DIR"

pending=0
last_ts=0

trigger_push() {
  echo "[wenxian-autopush] change detected, waiting ${DEBOUNCE_SECONDS}s..."
  sleep "$DEBOUNCE_SECONDS"
  echo "[wenxian-autopush] pushing..."
  "$PUSH_SCRIPT"
  echo "[wenxian-autopush] done"
}

echo "[wenxian-autopush] watching: $WATCH_DIR"

# Monitor close_write/move/create/delete, ignore temporary editor files.
inotifywait -m -r "$WATCH_DIR" \
  --event close_write,move,create,delete \
  --format '%w%f' \
| while read -r changed; do
    case "$changed" in
      *.swp|*.tmp|*~|*.bak|*/__pycache__/*) continue;;
    esac
    trigger_push
  done
