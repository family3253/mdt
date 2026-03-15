#!/usr/bin/env bash
set -euo pipefail

# Sync OpenClaw Aether-maintenance skill + helper scripts to GitHub repo: git@github.com:family3253/aether.git
# NOTE: This script deliberately REDACTS/EXCLUDES secrets.

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
REPO_DIR="/home/chenyechao/tmp/aether"
REMOTE_URL="git@github.com:family3253/aether.git"
BRANCH="main"

SKILL_DIR="$WORKSPACE_DIR/skills/aether-pool-maintainer"
SCRIPT_FILE="$WORKSPACE_DIR/scripts/aether_gpt_pool_maintain.py"

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

mkdir -p skills/aether-pool-maintainer scripts

if [[ ! -d "$SKILL_DIR" ]]; then
  echo "ERROR: missing skill dir: $SKILL_DIR" >&2
  exit 1
fi
if [[ ! -f "$SCRIPT_FILE" ]]; then
  echo "ERROR: missing script file: $SCRIPT_FILE" >&2
  exit 1
fi

rsync -av \
  --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$SKILL_DIR/" "skills/aether-pool-maintainer/"

cp -f "$SCRIPT_FILE" "scripts/aether_gpt_pool_maintain.py"

cat > .gitignore <<'EOF'
# python
**/__pycache__/
**/*.pyc

# logs
**/*.log
EOF

cat > README.md <<'EOF'
# aether

This repo publishes OpenClaw maintenance skill(s) and helper scripts for Aether.

## Notes
- This repo **does not include secrets**. Configure credentials locally.
EOF

# Redact known secret literals in docs
python3 - <<'PY'
from pathlib import Path

REDACT = {
  "3323092216": "<REDACTED_PASSWORD_OR_KEY>",
  "1145569340@qq.com": "<REDACTED_ADMIN_EMAIL>",
}

for p in Path("skills").rglob("*.md"):
  s = p.read_text(encoding="utf-8", errors="ignore")
  orig = s
  for k,v in REDACT.items():
    s = s.replace(k, v)
  if s != orig:
    p.write_text(s, encoding="utf-8")
PY

if [[ -n "$(git status --porcelain=v1)" ]]; then
  git add -A
  git commit -m "sync: publish aether maintenance skill (redacted)" || true
  git push -u origin "$BRANCH"
  echo "OK: pushed to $REMOTE_URL ($BRANCH)"
else
  echo "OK: no changes to push"
fi
