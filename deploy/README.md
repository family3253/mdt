# MDT Hub Deploy

## 已下载依赖
- `vendor/openclaw-agents`
- `vendor/openclaw-office`
- `vendor/OpenClaw-Medical-Skills`
- `vendor/mcp-simple-pubmed`
- `vendor/healthcare-mcp-public`

## 一键初始化（本机）
```bash
cd /home/chenyechao/.openclaw/workspace/mdt-hub
bash deploy/bootstrap.sh
```

## 启动 MDT API
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8788
```

## 跑端到端检查
```bash
cd backend
source .venv/bin/activate
python deploy_check.py
```

## 启动 PubMed MCP（可选）
```bash
cd /home/chenyechao/.openclaw/workspace/mdt-hub/vendor/mcp-simple-pubmed
python -m venv .venv
source .venv/bin/activate
pip install -e .
export PUBMED_EMAIL=your_email@example.com
python -m mcp_simple_pubmed
```

## 启动 Healthcare MCP（可选）
```bash
cd /home/chenyechao/.openclaw/workspace/mdt-hub/vendor/healthcare-mcp-public/server
npm install
npm run server:http
```
