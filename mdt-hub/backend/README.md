# backend

## 1) 启动 API
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8788
```

## 2) 打开病例
```bash
curl -X POST http://127.0.0.1:8788/cases/open \
  -H 'content-type: application/json' \
  -d '{
    "case_id":"CASE-2026-0312-001",
    "patient_summary":{"chief_complaint":"发热、低血压","suspected_source":"肺部感染"},
    "danger_flag": true
  }'
```

## 3) 发送事件
```bash
curl -X POST http://127.0.0.1:8788/events \
  -H 'content-type: application/json' \
  -d '{
    "case_id":"CASE-2026-0312-001",
    "round_no":1,
    "event_type":"agent_opinion",
    "speaker":"mdt-id",
    "specialty":"infectious_disease",
    "payload":{"claim":"覆盖MDR-GNB并24h复评"},
    "confidence":0.81
  }'
```

## 4) 查询病例事件
```bash
curl http://127.0.0.1:8788/cases/CASE-2026-0312-001/events
```

## 5) 实时可视化演示
直接打开 `../frontend.html`，它会监听 `ws://<host>:8788/ws/events`。
