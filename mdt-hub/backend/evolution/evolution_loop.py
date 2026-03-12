import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB = BASE / "mdt.db"
OUT_JSON = BASE / "evolution" / "evolution-backlog.json"
OUT_MD = BASE / "evolution" / "evolution-report.md"


def load_events():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("select * from mdt_events order by event_id asc").fetchall()
    conn.close()
    events = []
    for r in rows:
        payload = {}
        try:
            payload = json.loads(r["payload"])
        except Exception:
            pass
        events.append({
            "event_id": r["event_id"],
            "case_id": r["case_id"],
            "round_no": r["round_no"],
            "event_type": r["event_type"],
            "speaker": r["speaker"],
            "specialty": r["specialty"],
            "payload": payload,
            "confidence": r["confidence"],
            "reply_to_event_id": r["reply_to_event_id"],
            "timestamp": r["timestamp"],
        })
    return events


def analyze(events):
    by_case = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)

    speaker_count = Counter(e["speaker"] for e in events if e["speaker"]) 
    event_type_count = Counter(e["event_type"] for e in events)

    convergence_steps = []
    conflict_edges = 0
    oppose_edges = 0

    for case_id, arr in by_case.items():
        first_discuss = next((x for x in arr if x["event_type"] in ("discussion_message", "agent_opinion")), None)
        first_consensus = next((x for x in arr if x["event_type"] == "consensus_updated"), None)
        if first_discuss and first_consensus:
            convergence_steps.append(first_consensus["event_id"] - first_discuss["event_id"])

        for x in arr:
            if x["event_type"] == "agent_review":
                conflict_edges += 1
                if x["payload"].get("stance") == "oppose":
                    oppose_edges += 1

    avg_conv = round(sum(convergence_steps) / len(convergence_steps), 2) if convergence_steps else None
    oppose_ratio = round(oppose_edges / conflict_edges, 2) if conflict_edges else 0

    backlog = []

    if avg_conv and avg_conv > 8:
        backlog.append({
            "id": "EVO-001",
            "title": "收敛步数偏高，增加主持人中间收敛节点",
            "priority": "high",
            "impact": "high",
            "effort": "medium",
            "status": "todo"
        })

    if conflict_edges > 0 and oppose_ratio > 0.6:
        backlog.append({
            "id": "EVO-002",
            "title": "反驳比例偏高，引入证据仲裁规则",
            "priority": "high",
            "impact": "high",
            "effort": "medium",
            "status": "todo"
        })

    rare_speakers = [s for s, c in speaker_count.items() if s.startswith("mdt-") and c <= 2]
    if rare_speakers:
        backlog.append({
            "id": "EVO-003",
            "title": f"专家参与不均衡，低参与角色: {', '.join(rare_speakers[:5])}",
            "priority": "medium",
            "impact": "medium",
            "effort": "low",
            "status": "todo"
        })

    if event_type_count.get("agent_review", 0) == 0:
        backlog.append({
            "id": "EVO-004",
            "title": "未启用二轮互评，建议开启 review round",
            "priority": "medium",
            "impact": "medium",
            "effort": "low",
            "status": "todo"
        })

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(by_case),
        "events": len(events),
        "avg_convergence_steps": avg_conv,
        "conflict_edges": conflict_edges,
        "oppose_ratio": oppose_ratio,
        "event_type_count": dict(event_type_count),
        "speaker_count": dict(speaker_count),
        "backlog": backlog[:3],
    }
    return summary


def write_outputs(summary):
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    lines = [
        "# MDT Evolution Report",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Cases: {summary['cases']}",
        f"- Events: {summary['events']}",
        f"- Avg convergence steps: {summary['avg_convergence_steps']}",
        f"- Conflict edges: {summary['conflict_edges']}",
        f"- Oppose ratio: {summary['oppose_ratio']}",
        "",
        "## Top Backlog",
    ]
    if not summary["backlog"]:
        lines.append("- 暂无高优先改进项")
    else:
        for b in summary["backlog"]:
            lines.append(f"- [{b['id']}] {b['title']} (priority={b['priority']}, effort={b['effort']})")

    OUT_MD.write_text("\n".join(lines) + "\n")


def main():
    events = load_events()
    summary = analyze(events)
    write_outputs(summary)
    print("done", OUT_JSON)


if __name__ == "__main__":
    main()
