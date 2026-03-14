#!/usr/bin/env bash
set -euo pipefail

# Push mdt-hub to a PRIVATE GitHub repo.
# Usage:
#   scripts/push_mdt_to_private_github.sh git@github.com:<owner>/<repo>.git

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <git-ssh-remote-url>" >&2
  echo "Example: $0 git@github.com:family3253/mdt-hub-private.git" >&2
  exit 1
fi

REMOTE_URL="$1"
ROOT="/home/chenyechao/.openclaw/workspace/mdt-hub"
BRANCH="main"

cd "$ROOT"

# Ensure we're on main
cur_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$cur_branch" != "$BRANCH" ]]; then
  git branch -M "$BRANCH"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

# Commit any pending changes
if [[ -n "$(git status --porcelain=v1)" ]]; then
  git add -A
  git commit -m "sync: mdt-hub update" || true
fi

git push -u origin "$BRANCH"

echo "OK: pushed mdt-hub to $REMOTE_URL ($BRANCH)"
