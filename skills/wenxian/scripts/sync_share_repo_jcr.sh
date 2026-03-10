#!/usr/bin/env bash
set -euo pipefail

# Sync upstream JCR files from GitHub repo to local references/upstream_raw
# Usage: bash scripts/sync_share_repo_jcr.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM_DIR="$ROOT_DIR/references/upstream_raw"
TMP_DIR="/tmp/share_repo_jcr_sync"
REPO_URL="https://github.com/yongqianxiao/share_repo.git"

mkdir -p "$UPSTREAM_DIR"
rm -rf "$TMP_DIR"

git clone --depth 1 "$REPO_URL" "$TMP_DIR"

if [[ ! -d "$TMP_DIR/JCR" ]]; then
  echo "[ERROR] upstream repo has no JCR directory"
  exit 1
fi

rsync -av --delete "$TMP_DIR/JCR/" "$UPSTREAM_DIR/"
find "$UPSTREAM_DIR" -maxdepth 1 -type f -printf "%f\n" | sort > "$ROOT_DIR/references/upstream/share_repo_JCR_manifest.txt"

echo "[OK] synced to $UPSTREAM_DIR"
