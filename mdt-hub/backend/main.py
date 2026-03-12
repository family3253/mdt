from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime, timezone

app = FastAPI(title="MDT Hub API", version="0.1.0")


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


@app.get("/health")
def health():
    return {"ok": True, "service": "mdt-hub"}


@app.post("/events")
def ingest_event(event: MDTEvent):
    # TODO: persist to Postgres + broadcast via WebSocket
    return {"accepted": True, "event": event.model_dump()}
