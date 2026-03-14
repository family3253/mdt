#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/chenyechao/.openclaw/workspace/mdt-hub"

echo "[1/4] setup backend python env"
python -m venv "$ROOT/backend/.venv"
source "$ROOT/backend/.venv/bin/activate"
pip install -r "$ROOT/backend/requirements.txt"


echo "[2/4] init sqlite schema via deploy_check"
python "$ROOT/backend/deploy_check.py" >/tmp/mdt_deploy_check.log
cat /tmp/mdt_deploy_check.log

echo "[3/4] fetch & prepare healthcare-mcp (vendor)"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR"

# Vendor sources are intentionally NOT committed into the private repo.
# This bootstrap step re-fetches required vendor repos.
if [ ! -d "$VENDOR/healthcare-mcp-public/.git" ]; then
  if [ -d "$VENDOR/healthcare-mcp-public" ]; then
    echo "vendor/healthcare-mcp-public exists but is not a git repo; please clean it first." >&2
    exit 1
  fi
  git clone --depth 1 https://github.com/Cicatriiz/healthcare-mcp-public.git "$VENDOR/healthcare-mcp-public"
fi

if [ -d "$VENDOR/healthcare-mcp-public/server" ]; then
  cd "$VENDOR/healthcare-mcp-public/server"
  npm install --silent || npm install
fi

echo "[4/4] bootstrap done"
echo "next: cd $ROOT/backend && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8788"
