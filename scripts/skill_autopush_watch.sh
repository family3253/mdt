#!/usr/bin/env bash
set -euo pipefail

# Watch academic skill dirs for changes and auto-push to git@github.com:family3253/skill.git
# Requires: inotify-tools

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
WATCH_DIRS=(
  "$WORKSPACE_DIR/skills/wenxian"
  "$WORKSPACE_DIR/skills/mdrgnb-daily-push"
  "$WORKSPACE_DIR/skills/pubmed-database"
  "$WORKSPACE_DIR/skills/summarize"
  "$WORKSPACE_DIR/skills/brave-search"
  "$WORKSPACE_DIR/skills/tavily-search"
  "$WORKSPACE_DIR/skills/multi-search-engine"
  "$WORKSPACE_DIR/skills/playwright-scraper-skill"
  "$WORKSPACE_DIR/skills/agent-browser"
  "$WORKSPACE_DIR/skills/notion"
  "$WORKSPACE_DIR/skills/gog"
  "$WORKSPACE_DIR/skills/daily-digest"
  "$WORKSPACE_DIR/skills/weekly-report-generator"
  "$WORKSPACE_DIR/skills/find-skills"
  "$WORKSPACE_DIR/skills/context-master"
  "$WORKSPACE_DIR/skills/task-status"
  "$WORKSPACE_DIR/skills/quadrants"
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
