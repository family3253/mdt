#!/usr/bin/env bash
set -euo pipefail

# Push workspace skills/wenxian updates to GitHub repo: git@github.com:family3253/Literature_push.git
# Assumes SSH keys are configured for GitHub.

WORKSPACE_DIR="/home/chenyechao/.openclaw/workspace"
SKILL_DIR="$WORKSPACE_DIR/skills/wenxian"
REPO_DIR="/home/chenyechao/tmp/Literature"

REMOTE_URL="git@github.com:family3253/Literature_push.git"
BRANCH="main"

if [[ ! -d "$SKILL_DIR" ]]; then
  echo "ERROR: skill dir not found: $SKILL_DIR" >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "Repo missing at $REPO_DIR, cloning..." >&2
  rm -rf "$REPO_DIR"
  git clone "$REMOTE_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

git remote set-url origin "$REMOTE_URL" || true

git fetch origin "$BRANCH" >/dev/null 2>&1 || true
# Keep local in sync
if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  git checkout "$BRANCH" >/dev/null 2>&1 || git checkout -b "$BRANCH"
  git pull --rebase origin "$BRANCH"
else
  git checkout -B "$BRANCH"
fi

# Sync files from workspace skill to repo, but keep repo-specific files like README/.gitignore
rsync -av \
  --exclude '.git' \
  --exclude 'README.md' \
  --exclude '.gitignore' \
  "$SKILL_DIR/" "$REPO_DIR/"

if [[ -n "$(git status --porcelain=v1)" ]]; then
  git add -A
  git commit -m "sync: update wenxian skill" || true
  git push origin "$BRANCH"
  echo "OK: pushed changes to $REMOTE_URL ($BRANCH)"
else
  echo "OK: no changes to push"
fi
