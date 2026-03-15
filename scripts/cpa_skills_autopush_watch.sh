#!/usr/bin/env bash
set -euo pipefail

# Watch CPA-related skill dirs for changes and auto-push after debounce.
# Requires: inotify-tools

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
WATCH_DIRS=(
  "$WORKSPACE_DIR/skills/auto-pool-maintainer"
  "$WORKSPACE_DIR/skills/cpa-pool-maintainer"
)
PUSH_SCRIPT="$WORKSPACE_DIR/scripts/push_cpa_skills_to_github.sh"
DEBOUNCE_SECONDS=10

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "ERROR: inotifywait not found. Install: sudo apt-get update && sudo apt-get install -y inotify-tools" >&2
  exit 1
fi

if [[ ! -x "$PUSH_SCRIPT" ]]; then
  echo "ERROR: push script not executable: $PUSH_SCRIPT" >&2
  exit 1
fi

for d in "${WATCH_DIRS[@]}"; do
  [[ -d "$d" ]] || { echo "ERROR: watch dir missing: $d" >&2; exit 1; }
done

echo "[cpa-autopush] watching: ${WATCH_DIRS[*]}"

trigger_push() {
  echo "[cpa-autopush] change detected, waiting ${DEBOUNCE_SECONDS}s..."
  sleep "$DEBOUNCE_SECONDS"
  echo "[cpa-autopush] pushing..."
  "$PUSH_SCRIPT"
  echo "[cpa-autopush] done"
}

inotifywait -m -r "${WATCH_DIRS[@]}" \
  --event close_write,move,create,delete \
  --format '%w%f' \
| while read -r changed; do
    case "$changed" in
      *.swp|*.tmp|*~|*.bak|*/__pycache__/*|*/runtime/config.json|*/runtime/logs/*|*/scripts/logs/*) continue;;
    esac
    trigger_push
  done
