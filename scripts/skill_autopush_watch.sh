#!/usr/bin/env bash
set -euo pipefail

# Watch academic skill dirs for changes and auto-push to git@github.com:family3253/skill.git
# Requires: inotify-tools

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
WATCH_DIRS=(
  # Watch the whole skill directories so new academic skills auto-sync without editing this script.
  "$WORKSPACE_DIR/skills"
  "/home/chenyechao/.openclaw/skills"
)

PUSH_SCRIPT="$WORKSPACE_DIR/scripts/push_academic_skills_to_github.sh"
DEBOUNCE_SECONDS=10

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "ERROR: inotifywait not found" >&2
  exit 1
fi

if [[ ! -x "$PUSH_SCRIPT" ]]; then
  echo "ERROR: push script not executable: $PUSH_SCRIPT" >&2
  exit 1
fi

for d in "${WATCH_DIRS[@]}"; do
  [[ -d "$d" ]] || { echo "ERROR: watch dir missing: $d" >&2; exit 1; }
done

echo "[skill-autopush] watching: ${WATCH_DIRS[*]}"

trigger_push() {
  echo "[skill-autopush] change detected, waiting ${DEBOUNCE_SECONDS}s..."
  sleep "$DEBOUNCE_SECONDS"
  echo "[skill-autopush] pushing..."
  "$PUSH_SCRIPT"
  echo "[skill-autopush] done"
}

inotifywait -m -r "${WATCH_DIRS[@]}" \
  --event close_write,move,create,delete \
  --format '%w%f' \
| while read -r changed; do
    case "$changed" in
      *.swp|*.tmp|*~|*.bak|*/__pycache__/*|*.pyc|*/runtime/config.json|*/runtime/logs/*|*/scripts/logs/*|*.log) continue;;
    esac
    trigger_push
  done
