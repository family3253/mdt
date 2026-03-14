#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/chenyechao/.openclaw/workspace/mdt-hub"
BACKEND="$ROOT/backend"
MCP="$ROOT/vendor/healthcare-mcp-public/server"  # fetched by deploy/bootstrap.sh

# Ports:
# - Frontend static: 8088
# - Backend API: 8788
# - Healthcare MCP HTTP: 3000

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -t -i TCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "[kill] port $port -> $pids"
    kill $pids || true
    sleep 0.5
  fi
}

mkdir -p "$ROOT/.run"

echo "[1/5] stop old processes"
kill_port 8088
kill_port 8788
kill_port 3000

echo "[2/5] start backend (uvicorn)"
cd "$BACKEND"
source "$BACKEND/.venv/bin/activate"
nohup uvicorn main:app --host 0.0.0.0 --port 8788 >"$ROOT/.run/backend.8788.log" 2>&1 &
echo $! >"$ROOT/.run/backend.8788.pid"

echo "[3/5] start frontend static server"
cd "$ROOT"
nohup python3 -m http.server 8088 --bind 0.0.0.0 >"$ROOT/.run/frontend.8088.log" 2>&1 &
echo $! >"$ROOT/.run/frontend.8088.pid"

echo "[4/5] start healthcare-mcp HTTP server"
cd "$MCP"
nohup node http-server.js >"$ROOT/.run/mcp.3000.log" 2>&1 &
echo $! >"$ROOT/.run/mcp.3000.pid"

echo "[5/5] quick health checks"
sleep 1
curl -fsS "http://127.0.0.1:8788/health" | head -c 200 || true
curl -fsS "http://127.0.0.1:3000/health" | head -c 200 || true
curl -fsS "http://127.0.0.1:8088/frontend.html" | head -c 60 || true

echo "OK: MDT restarted"
echo "frontend: http://127.0.0.1:8088/frontend.html"
echo "backend:  http://127.0.0.1:8788"
echo "mcp:      http://127.0.0.1:3000"
