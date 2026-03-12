from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mdt.db"

app = FastAPI(title="MDT Hub API", version="0.2.0")


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


@app.on_event("startup")
def on_startup() -> None:
    init_db()

# ensure table bootstrap for TestClient/offline scripts
init_db()

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
    with conn() as c:
        exists = c.execute(
            "select case_id from cases where case_id=?", (event.case_id,)
        ).fetchone()
        if not exists:
            c.execute(
                "insert into cases(case_id,status,opened_at,patient_summary,danger_flag) values (?,?,?,?,0)",
                (
                    event.case_id,
                    "active",
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps({}, ensure_ascii=False),
                ),
            )
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

    body = {"event_id": event_id, **event.model_dump(mode="json")}
    await ws_manager.broadcast({"type": "mdt_event", "data": body})
    return {"accepted": True, "event": body}


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
