#!/usr/bin/env bash
set -euo pipefail

# Polling-based watcher: no inotify dependency.
# It checks for any mtime changes under skills/wenxian and triggers a push after debounce.

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
WATCH_DIR="$WORKSPACE_DIR/skills/wenxian"
PUSH_SCRIPT="$WORKSPACE_DIR/scripts/push_wenxian_to_github.sh"

INTERVAL_SECONDS=30
DEBOUNCE_SECONDS=15

if [[ ! -x "$PUSH_SCRIPT" ]]; then
  echo "ERROR: push script not executable: $PUSH_SCRIPT" >&2
  exit 1
fi

cd "$WORKSPACE_DIR"

echo "[wenxian-autopush] polling watch: $WATCH_DIR (interval=${INTERVAL_SECONDS}s)"

# Get a stable signature: latest mtime + file count.
sig() {
  # Exclude noisy dirs
  find "$WATCH_DIR" -type f \
    -not -path '*/__pycache__/*' \
    -not -name '*.swp' -not -name '*~' -not -name '*.tmp' -not -name '*.bak' \
    -printf '%T@\n' 2>/dev/null \
  | sort -n \
  | tail -n 1
}

last="$(sig || true)"

while true; do
  sleep "$INTERVAL_SECONDS"
  cur="$(sig || true)"
  if [[ "$cur" != "$last" ]]; then
    echo "[wenxian-autopush] change detected, debounce ${DEBOUNCE_SECONDS}s..."
    sleep "$DEBOUNCE_SECONDS"
    # re-check to avoid pushing mid-edit
    cur2="$(sig || true)"
    if [[ "$cur2" != "$cur" ]]; then
      # more changes happened; skip this cycle, next loop will catch
      last="$cur2"
      continue
    fi
    echo "[wenxian-autopush] pushing..."
    "$PUSH_SCRIPT" || true
    last="$cur2"
  fi
done
