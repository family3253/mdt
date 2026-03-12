from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mdt.db"

app = FastAPI(title="MDT Hub API", version="0.3.0")


class MDTEvent(BaseModel):
    case_id: str
    round_no: int = Field(ge=0)
    event_type: str
    speaker: str
    specialty: Optional[str] = None
    payload: dict[str, Any]
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reply_to_event_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseOpen(BaseModel):
    case_id: str
    patient_summary: dict[str, Any]
    status: str = "active"
    danger_flag: bool = False


class DiscussionInput(BaseModel):
    case_id: str
    round_no: int = Field(default=1, ge=1)
    speaker: str = "human_clinician"
    message: str


class AgentCreate(BaseModel):
    agent_id: str
    role: str
    specialty: str
    prompt: str = ""
    enabled: bool = True


class KnowledgeFeed(BaseModel):
    content: str
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)


class WSManager:
    def __init__(self) -> None:
        self.clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.clients:
            self.clients.remove(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for c in self.clients:
            try:
                await c.send_json(message)
            except Exception:
                dead.append(c)
        for c in dead:
            self.disconnect(c)


ws_manager = WSManager()


DEFAULT_SPECIALIST_PROFILES = [
    ("mdt-id", "infectious_disease", "感染来源+抗菌覆盖策略"),
    ("mdt-micro", "microbiology", "病原/标本质量与耐药解释"),
    ("mdt-pharm", "clinical_pharmacy", "剂量与肾功能分层，药物相互作用"),
    ("mdt-icu", "icu", "重症风险分层与支持治疗窗口"),
    ("mdt-evidence", "evidence", "指南与文献证据分级"),
]


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with conn() as c:
        c.execute(
            """
            create table if not exists cases (
              case_id text primary key,
              status text not null default 'active',
              opened_at text not null,
              closed_at text,
              patient_summary text not null,
              danger_flag integer not null default 0,
              final_conclusion text
            )
            """
        )
        c.execute(
            """
            create table if not exists mdt_events (
              event_id integer primary key autoincrement,
              case_id text not null,
              round_no integer not null,
              event_type text not null,
              speaker text not null,
              specialty text,
              payload text not null,
              confidence real,
              reply_to_event_id integer,
              timestamp text not null
            )
            """
        )
        c.execute(
            """
            create table if not exists mdt_agents (
              agent_id text primary key,
              role text not null,
              specialty text not null,
              prompt text,
              enabled integer not null default 1,
              created_at text not null
            )
            """
        )
        c.execute(
            """
            create table if not exists mdt_knowledge (
              id integer primary key autoincrement,
              agent_id text not null,
              content text not null,
              source text not null,
              tags text,
              created_at text not null
            )
            """
        )


def _ensure_case(case_id: str) -> None:
    with conn() as c:
        exists = c.execute("select case_id from cases where case_id=?", (case_id,)).fetchone()
        if not exists:
            c.execute(
                "insert into cases(case_id,status,opened_at,patient_summary,danger_flag) values (?,?,?,?,0)",
                (case_id, "active", datetime.now(timezone.utc).isoformat(), json.dumps({}, ensure_ascii=False)),
            )


def _persist_event(event: MDTEvent) -> dict[str, Any]:
    _ensure_case(event.case_id)
    with conn() as c:
        cur = c.execute(
            """
            insert into mdt_events(case_id,round_no,event_type,speaker,specialty,payload,confidence,reply_to_event_id,timestamp)
            values (?,?,?,?,?,?,?,?,?)
            """,
            (
                event.case_id,
                event.round_no,
                event.event_type,
                event.speaker,
                event.specialty,
                json.dumps(event.payload, ensure_ascii=False),
                event.confidence,
                event.reply_to_event_id,
                event.timestamp.isoformat(),
            ),
        )
        event_id = cur.lastrowid
    return {"event_id": event_id, **event.model_dump(mode="json")}


def _latest_round(case_id: str) -> int:
    with conn() as c:
        row = c.execute("select max(round_no) as r from mdt_events where case_id=?", (case_id,)).fetchone()
    return int(row["r"] or 0)


def _seed_default_agents() -> None:
    now = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        for agent_id, specialty, lens in DEFAULT_SPECIALIST_PROFILES:
            c.execute(
                "insert or ignore into mdt_agents(agent_id, role, specialty, prompt, enabled, created_at) values (?,?,?,?,1,?)",
                (agent_id, lens, specialty, "", now),
            )


def _load_enabled_agents() -> list[tuple[str, str, str]]:
    with conn() as c:
        rows = c.execute("select agent_id, specialty, role from mdt_agents where enabled=1 order by created_at asc").fetchall()
    if not rows:
        return DEFAULT_SPECIALIST_PROFILES
    return [(r["agent_id"], r["specialty"], r["role"]) for r in rows]


def _knowledge_snippet(agent_id: str, limit: int = 2) -> str:
    with conn() as c:
        rows = c.execute(
            "select content from mdt_knowledge where agent_id=? order by id desc limit ?",
            (agent_id, limit),
        ).fetchall()
    if not rows:
        return ""
    return " | ".join((r["content"][:60] for r in rows))


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _seed_default_agents()


init_db()
_seed_default_agents()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "mdt-hub", "db": str(DB_PATH)}


@app.post("/cases/open")
def open_case(payload: CaseOpen) -> dict[str, Any]:
    opened_at = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        try:
            c.execute(
                "insert into cases(case_id,status,opened_at,patient_summary,danger_flag) values (?,?,?,?,?)",
                (
                    payload.case_id,
                    payload.status,
                    opened_at,
                    json.dumps(payload.patient_summary, ensure_ascii=False),
                    1 if payload.danger_flag else 0,
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="case_id already exists")
    return {"ok": True, "case_id": payload.case_id, "opened_at": opened_at}


@app.post("/events")
async def ingest_event(event: MDTEvent) -> dict[str, Any]:
    body = _persist_event(event)
    await ws_manager.broadcast({"type": "mdt_event", "data": body})
    return {"accepted": True, "event": body}


@app.get("/agents")
def list_agents() -> dict[str, Any]:
    with conn() as c:
        rows = c.execute("select agent_id, role, specialty, prompt, enabled, created_at from mdt_agents order by created_at asc").fetchall()
    return {"count": len(rows), "agents": [dict(r) for r in rows]}


@app.post("/agents")
def create_agent(payload: AgentCreate) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        try:
            c.execute(
                "insert into mdt_agents(agent_id, role, specialty, prompt, enabled, created_at) values (?,?,?,?,?,?)",
                (payload.agent_id, payload.role, payload.specialty, payload.prompt, 1 if payload.enabled else 0, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="agent_id already exists")
    return {"ok": True, "agent_id": payload.agent_id}


@app.post("/agents/{agent_id}/knowledge")
def feed_knowledge(agent_id: str, payload: KnowledgeFeed) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    tags = json.dumps(payload.tags, ensure_ascii=False)
    with conn() as c:
        exists = c.execute("select agent_id from mdt_agents where agent_id=?", (agent_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="agent not found")
        c.execute(
            "insert into mdt_knowledge(agent_id, content, source, tags, created_at) values (?,?,?,?,?)",
            (agent_id, payload.content, payload.source, tags, now),
        )
    return {"ok": True, "agent_id": agent_id}


@app.post("/discussion/submit")
async def discussion_submit(payload: DiscussionInput) -> dict[str, Any]:
    """模拟现实 MDT：先录入临床医生发言，再按角色生成一轮专家回应。"""
    round_no = payload.round_no or max(1, _latest_round(payload.case_id))

    human_event = MDTEvent(
        case_id=payload.case_id,
        round_no=round_no,
        event_type="discussion_message",
        speaker=payload.speaker,
        specialty="human",
        payload={"text": payload.message},
        confidence=None,
    )
    human_body = _persist_event(human_event)
    await ws_manager.broadcast({"type": "mdt_event", "data": human_body})

    generated: list[dict[str, Any]] = []
    for agent_id, specialty, lens in _load_enabled_agents():
        learned = _knowledge_snippet(agent_id)
        ev = MDTEvent(
            case_id=payload.case_id,
            round_no=round_no,
            event_type="agent_opinion",
            speaker=agent_id,
            specialty=specialty,
            payload={
                "discussion": f"针对输入“{payload.message}”，从{lens}角度建议补充评估并形成可执行方案。",
                "learned_context": learned,
                "source": "simulated_role_response",
            },
            confidence=0.75,
        )
        body = _persist_event(ev)
        generated.append(body)
        await ws_manager.broadcast({"type": "mdt_event", "data": body})

    orchestrator = MDTEvent(
        case_id=payload.case_id,
        round_no=round_no,
        event_type="consensus_updated",
        speaker="mdt-orchestrator",
        specialty="mdt",
        payload={
            "status": "majority",
            "summary": "已收集多学科观点，建议进入下一轮定向追问或定稿。",
            "next_step": "targeted_round_or_finalize",
        },
        confidence=0.82,
    )
    orchestrator_body = _persist_event(orchestrator)
    await ws_manager.broadcast({"type": "mdt_event", "data": orchestrator_body})

    return {
        "accepted": True,
        "case_id": payload.case_id,
        "round_no": round_no,
        "generated_count": len(generated) + 1,
    }


@app.get("/cases/{case_id}/events")
def list_case_events(case_id: str) -> dict[str, Any]:
    with conn() as c:
        rows = c.execute(
            "select * from mdt_events where case_id=? order by event_id asc", (case_id,)
        ).fetchall()
    events = []
    for r in rows:
        events.append(
            {
                "event_id": r["event_id"],
                "case_id": r["case_id"],
                "round_no": r["round_no"],
                "event_type": r["event_type"],
                "speaker": r["speaker"],
                "specialty": r["specialty"],
                "payload": json.loads(r["payload"]),
                "confidence": r["confidence"],
                "reply_to_event_id": r["reply_to_event_id"],
                "timestamp": r["timestamp"],
            }
        )
    return {"case_id": case_id, "count": len(events), "events": events}


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
