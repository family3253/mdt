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

echo "[3/4] prepare healthcare-mcp node deps"
if [ -d "$ROOT/vendor/healthcare-mcp-public/server" ]; then
  cd "$ROOT/vendor/healthcare-mcp-public/server"
  npm install --silent || npm install
fi

echo "[4/4] bootstrap done"
echo "next: cd $ROOT/backend && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8788"
