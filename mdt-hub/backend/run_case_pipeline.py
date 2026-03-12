import requests
from datetime import datetime

API = "http://127.0.0.1:8788"
case_id = f"CASE-RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

requests.post(f"{API}/cases/open", json={
    "case_id": case_id,
    "patient_summary": {
        "chief_complaint": "发热、咳嗽、低血压",
        "suspected_source": "肺部感染",
        "history": ["近期广谱抗菌药暴露"]
    },
    "danger_flag": True
}, timeout=10)

flow = [
    ("mdt-orchestrator", "case_opened", {"stage": "triage"}, 0.95, "mdt"),
    ("mdt-id", "agent_opinion", {"claim": "先覆盖MDR-GNB，24h复评降阶梯"}, 0.81, "infectious_disease"),
    ("mdt-micro", "agent_opinion", {"claim": "当前标本质量中等，需复采确认"}, 0.73, "microbiology"),
    ("mdt-pharm", "agent_opinion", {"claim": "按eGFR分层给药，监测肾毒性/TDM"}, 0.84, "clinical_pharmacy"),
    ("mdt-icu", "agent_opinion", {"claim": "存在休克风险，需4小时内复测乳酸"}, 0.79, "icu"),
    ("mdt-evidence", "agent_opinion", {"claim": "IDSA+本院药敏支持先覆盖后去升级"}, 0.77, "evidence"),
    ("mdt-orchestrator", "conflict_detected", {"topic": "覆盖强度 vs 肾毒性"}, 0.9, "mdt"),
    ("mdt-orchestrator", "consensus_updated", {"status": "majority", "recommendation": "覆盖+肾功能分层+24h复评"}, 0.86, "mdt"),
]

for i, (speaker, etype, payload, conf, specialty) in enumerate(flow, start=1):
    requests.post(f"{API}/events", json={
        "case_id": case_id,
        "round_no": 1 if i < 7 else 2,
        "event_type": etype,
        "speaker": speaker,
        "specialty": specialty,
        "payload": payload,
        "confidence": conf,
    }, timeout=10)

resp = requests.get(f"{API}/cases/{case_id}/events", timeout=10).json()
print("case_id=", case_id)
print("events_count=", resp.get("count"))
print("last=", resp.get("events", [])[-1]["event_type"], resp.get("events", [])[-1]["speaker"])
