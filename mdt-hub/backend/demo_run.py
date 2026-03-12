from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from main import app

client = TestClient(app)

case_id = "CASE-2026-0312-001"
base = datetime.now(timezone.utc)

events = [
    {
        "case_id": case_id,
        "round_no": 0,
        "event_type": "case_opened",
        "speaker": "orchestrator",
        "specialty": "mdt",
        "payload": {
            "chief_complaint": "发热、低血压",
            "suspected_source": "肺部感染",
            "danger_flag": True,
            "note": "进入快速会诊流程"
        },
        "confidence": 0.95,
        "timestamp": (base).isoformat()
    },
    {
        "case_id": case_id,
        "round_no": 1,
        "event_type": "agent_opinion",
        "speaker": "id_specialist",
        "specialty": "infectious_disease",
        "payload": {
            "claim": "优先覆盖 MDR-GNB，待药敏后去升级",
            "evidence_refs": ["IDSA guidance 2024", "local antibiogram"],
            "contraindications": ["严重肾功能不全需调整"]
        },
        "confidence": 0.78,
        "timestamp": (base + timedelta(seconds=5)).isoformat()
    },
    {
        "case_id": case_id,
        "round_no": 1,
        "event_type": "agent_opinion",
        "speaker": "pharm_specialist",
        "specialty": "clinical_pharmacy",
        "payload": {
            "claim": "建议先行剂量优化并监测 TDM",
            "dose_note": "根据 eGFR 调整",
            "interaction_risks": ["肾毒性叠加风险"]
        },
        "confidence": 0.82,
        "timestamp": (base + timedelta(seconds=8)).isoformat()
    },
    {
        "case_id": case_id,
        "round_no": 1,
        "event_type": "conflict_detected",
        "speaker": "orchestrator",
        "specialty": "mdt",
        "payload": {
            "topic": "初始方案强度 vs 肾毒性风险",
            "open_issue": "是否立即联合方案"
        },
        "confidence": 0.9,
        "timestamp": (base + timedelta(seconds=12)).isoformat()
    },
    {
        "case_id": case_id,
        "round_no": 2,
        "event_type": "consensus_updated",
        "speaker": "orchestrator",
        "specialty": "mdt",
        "payload": {
            "status": "majority",
            "recommendation": "先覆盖 MDR-GNB + 肾功能分层给药 + 24h 复评",
            "unresolved": []
        },
        "confidence": 0.84,
        "timestamp": (base + timedelta(seconds=18)).isoformat()
    }
]

print("=== MDT Demo Run ===")
print("health:", client.get("/health").json())

for i, ev in enumerate(events, start=1):
    r = client.post("/events", json=ev)
    body = r.json()
    accepted = body.get("accepted")
    event_type = body.get("event", {}).get("event_type")
    speaker = body.get("event", {}).get("speaker")
    print(f"[{i}] accepted={accepted} event={event_type} speaker={speaker}")

print("=== Done ===")
