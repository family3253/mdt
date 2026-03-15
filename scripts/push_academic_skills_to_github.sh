#!/usr/bin/env bash
set -euo pipefail

# Publish academic-focused skills to GitHub repo: git@github.com:family3253/skill.git
# IMPORTANT: this script excludes secrets + runtime state by default.

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
REPO_DIR="/home/chenyechao/tmp/skill"
REMOTE_URL="git@github.com:family3253/skill.git"
BRANCH="main"

# skill dirs to publish (academic writing + research)
SRC_SKILLS=(
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

  # PPT
  "/home/chenyechao/.openclaw/skills/elite-powerpoint-designer"
  "/home/chenyechao/.openclaw/skills/powerpoint-automation"
)

# Extra repo-only wrappers/scripts we want to include
EXTRA_FILES=(
  "$WORKSPACE_DIR/scripts/push_wenxian_to_github.sh"
  "$WORKSPACE_DIR/scripts/push_cpa_skills_to_github.sh"
  "$WORKSPACE_DIR/scripts/push_aether_skills_to_github.sh"
  "$WORKSPACE_DIR/scripts/cpa_skills_autopush_watch.sh"
  "$WORKSPACE_DIR/scripts/aether_skills_autopush_watch.sh"
)

mkdir -p "$(dirname "$REPO_DIR")"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  rm -rf "$REPO_DIR"
  git clone "$REMOTE_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

git remote set-url origin "$REMOTE_URL" || true

# Empty repo bootstrap
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  git checkout -B "$BRANCH"
else
  git fetch origin "$BRANCH" >/dev/null 2>&1 || true
  if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
    git checkout "$BRANCH" >/dev/null 2>&1 || git checkout -b "$BRANCH"
    git pull --rebase origin "$BRANCH" || true
  else
    git checkout -B "$BRANCH"
  fi
fi

mkdir -p skills scripts

# Sync skills
for src in "${SRC_SKILLS[@]}"; do
  name="$(basename "$src")"
  if [[ ! -d "$src" ]]; then
    echo "WARN: missing skill dir, skip: $src" >&2
    continue
  fi
  mkdir -p "skills/$name"

  rsync -av \
    --delete \
    --exclude '.git' \
    --exclude '.clawhub' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'runtime/config.json' \
    --exclude 'runtime/logs' \
    --exclude 'scripts/logs' \
    --exclude '*.log' \
    "$src/" "skills/$name/"
done

# Copy extra scripts (best-effort)
for f in "${EXTRA_FILES[@]}"; do
  if [[ -f "$f" ]]; then
    cp -f "$f" "scripts/$(basename "$f")"
  fi
done

cat > .gitignore <<'EOF'
# secrets / runtime state
**/runtime/config.json
**/runtime/logs/
**/scripts/logs/

# node/python
**/node_modules/
**/__pycache__/
**/*.pyc

# logs
**/*.log
EOF

cat > README.md <<'EOF'
# skill

Academic-focused skill bundle for OpenClaw/OpenCode migration.

## Structure
- `skills/<skill-name>/` : skill package directories
- `scripts/` : helper sync scripts (no secrets)

## Safety
- This repo excludes secrets (tokens, API keys) and runtime state by default.
- Fill credentials locally when running.
EOF

# Redact known local secret literals in committed text (best-effort)
python3 - <<'PY'
from pathlib import Path

REDACT = {
  "3323092216": "<REDACTED>",
  "1145569340@qq.com": "<REDACTED>",
  "mk_v1WKMQ5nNnBWnIBBFtAv9uFhtl_LIjky": "<REDACTED>",
}

for p in Path('.').rglob('*'):
  if p.is_dir():
    continue
  if p.suffix.lower() not in {'.md','.txt','.json','.yml','.yaml','.sh','.py','.js','.mjs'}:
    continue
  try:
    s = p.read_text(encoding='utf-8', errors='ignore')
  except Exception:
    continue
  orig=s
  for k,v in REDACT.items():
    s=s.replace(k,v)
  if s!=orig:
    p.write_text(s,encoding='utf-8')
PY

if [[ -n "$(git status --porcelain=v1)" ]]; then
  git add -A
  git commit -m "sync: publish academic skills bundle (redacted)" || true
  git push -u origin "$BRANCH"
  echo "OK: pushed to $REMOTE_URL ($BRANCH)"
else
  echo "OK: no changes to push"
fi
