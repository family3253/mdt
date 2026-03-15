#!/usr/bin/env bash
set -euo pipefail

# Sync OpenClaw CPA-maintenance skills to GitHub repo: git@github.com:family3253/cpa.git
# NOTE: This script deliberately REDACTS/EXCLUDES secrets.

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
REPO_DIR="/home/chenyechao/tmp/cpa"
REMOTE_URL="git@github.com:family3253/cpa.git"
BRANCH="main"

SRC_SKILLS=(
  "$WORKSPACE_DIR/skills/auto-pool-maintainer"
  "$WORKSPACE_DIR/skills/cpa-pool-maintainer"
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

mkdir -p skills

# Sync skills
for src in "${SRC_SKILLS[@]}"; do
  name="$(basename "$src")"
  if [[ ! -d "$src" ]]; then
    echo "ERROR: missing skill dir: $src" >&2
    exit 1
  fi
  mkdir -p "skills/$name"

  rsync -av \
    --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'runtime/config.json' \
    --exclude 'runtime/logs' \
    --exclude 'scripts/logs' \
    --exclude '*.log' \
    "$src/" "skills/$name/"
done

# Repo hygiene
cat > .gitignore <<'EOF'
# secrets / runtime state
skills/**/runtime/config.json
skills/**/runtime/logs/
skills/**/scripts/logs/

# python
**/__pycache__/
**/*.pyc

# logs
**/*.log
EOF

cat > README.md <<'EOF'
# cpa

This repo publishes OpenClaw maintenance skills related to CPA/CLIProxyAPI.

## Notes
- This repo **does not include secrets** (tokens, API keys) and excludes runtime state.
- Copy `skills/auto-pool-maintainer/references/config.template.json` to a local runtime config and fill in your own values.
EOF

# Redact known secret literals if they accidentally appear in committed docs
python3 - <<'PY'
from pathlib import Path

REDACT = {
  # known local secrets (replace with placeholders)
  "3323092216": "<REDACTED_CPA_MGMT_KEY>",
  "mk_v1WKMQ5nNnBWnIBBFtAv9uFhtl_LIjky": "<REDACTED_EMAIL_API_KEY>",
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
  git commit -m "sync: publish cpa maintenance skills (redacted)" || true
  git push -u origin "$BRANCH"
  echo "OK: pushed to $REMOTE_URL ($BRANCH)"
else
  echo "OK: no changes to push"
fi
