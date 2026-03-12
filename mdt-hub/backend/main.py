from __future__ import annotations

import io
import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    from PIL import Image
    import pytesseract
except Exception:  # pragma: no cover
    Image = None
    pytesseract = None

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mdt.db"

app = FastAPI(title="MDT Hub API", version="0.3.0")
DEFAULT_AGENT_MODEL = "openai-codex/gpt-5.3-codex"
FALLBACK_MODEL_OPTIONS = [
    "openai-codex/gpt-5.3-codex",
    "openai/gpt-4.1",
    "anthropic/claude-3-7-sonnet",
    "google/gemini-2.5-pro",
]
logger = logging.getLogger("mdt_hub")
OBSERVED_PATH_PATTERNS = [
    re.compile(r"^/models/available$"),
    re.compile(r"^/agents$"),
    re.compile(r"^/agents/[^/]+/model$"),
    re.compile(r"^/cases/[^/]+/events$"),
    re.compile(r"^/discussion/submit$"),
]


def _should_log_path(path: str) -> bool:
    return any(p.match(path) for p in OBSERVED_PATH_PATTERNS)


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


class ConfirmedSectionItem(BaseModel):
    text: str
    confirmed: bool = True


class ConfirmedSections(BaseModel):
    imaging: list[ConfirmedSectionItem] = Field(default_factory=list)
    labs: list[ConfirmedSectionItem] = Field(default_factory=list)
    medications: list[ConfirmedSectionItem] = Field(default_factory=list)


class DiscussionInput(BaseModel):
    case_id: str
    round_no: int = Field(default=1, ge=1)
    speaker: str = "human_clinician"
    message: str
    confirmed_sections: Optional[ConfirmedSections] = None
    enable_docs_context: bool = True


class RoundReviewInput(BaseModel):
    case_id: str
    from_round: int = Field(default=1, ge=1)
    to_round: int = Field(default=2, ge=2)


class KnowledgeFeed(BaseModel):
    content: str
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)


class URLIngest(BaseModel):
    url: str
    source: str = "url"


class AgentCreate(BaseModel):
    agent_id: str
    role: str
    specialty: str
    prompt: str = ""
    enabled: bool = True
    auto_learn_web: bool = True
    model: Optional[str] = None


class AgentModelUpdate(BaseModel):
    model: Optional[str] = None
    enabled: Optional[bool] = None


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

ROLE_PROMPT_TEMPLATES = {
    "感染": "你是感染科专家，聚焦感染来源、耐药风险、覆盖策略与去升级路径，输出需含证据与禁忌。",
    "药": "你是临床药师，聚焦剂量分层、相互作用、肝肾功能调整、毒性监测与TDM建议。",
    "icu": "你是重症专家，聚焦器官功能风险、支持治疗窗口、恶化预警。",
    "影像": "你是影像专家，聚焦CT/MRI关键征象、鉴别诊断、影像随访建议。",
    "检验": "你是检验/检验医学专家，聚焦实验室指标趋势、异常解释与复查建议。",
    "循证": "你是循证秘书，聚焦指南检索、文献摘要、证据分级和引用规范。",
}

ROLE_SKILL_HINTS = {
    "感染": ["OpenClaw-Medical-Skills: antimicrobial stewardship", "mcp-simple-pubmed", "healthcare-mcp-public"],
    "药": ["OpenClaw-Medical-Skills: clinical pharmacy", "healthcare-mcp-public"],
    "影像": ["OpenClaw-Medical-Skills: radiology", "OCR/PDF ingestion"],
    "检验": ["OpenClaw-Medical-Skills: lab interpretation", "healthcare-mcp-public"],
    "循证": ["mcp-simple-pubmed", "OpenClaw-Medical-Skills: evidence synthesis"],
}


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ensure_column(c: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = c.execute(f"pragma table_info({table})").fetchall()
    names = {r[1] for r in cols}
    if column not in names:
        c.execute(f"alter table {table} add column {column} {ddl}")


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
              model text,
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
        c.execute(
            """
            create table if not exists mdt_case_docs (
              id integer primary key autoincrement,
              case_id text not null,
              doc_type text not null,
              source text not null,
              content text not null,
              sections text,
              created_at text not null
            )
            """
        )
        _ensure_column(c, "mdt_agents", "model", "text")

        # 兼容旧库：若历史表缺少 model 列则在线补齐
        cols = [r[1] for r in c.execute("pragma table_info(mdt_agents)").fetchall()]
        if "model" not in cols:
            c.execute("alter table mdt_agents add column model text")


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
                "insert or ignore into mdt_agents(agent_id, role, specialty, prompt, model, enabled, created_at) values (?,?,?,?,?,1,?)",
                (agent_id, lens, specialty, "", None, now),
            )


def _load_enabled_agents() -> list[tuple[str, str, str, Optional[str]]]:
    with conn() as c:
        rows = c.execute("select agent_id, specialty, role, model from mdt_agents where enabled=1 order by created_at asc").fetchall()
    if not rows:
        return [(a, b, c, None) for (a, b, c) in DEFAULT_SPECIALIST_PROFILES]
    return [(r["agent_id"], r["specialty"], r["role"], r["model"]) for r in rows]


def _knowledge_snippet(agent_id: str, limit: int = 2) -> str:
    with conn() as c:
        rows = c.execute(
            "select content from mdt_knowledge where agent_id=? order by id desc limit ?",
            (agent_id, limit),
        ).fetchall()
    if not rows:
        return ""
    return " | ".join((r["content"][:60] for r in rows))


def _auto_prompt_for_role(role: str, specialty: str) -> str:
    role_l = role.lower()
    for key, prompt in ROLE_PROMPT_TEMPLATES.items():
        if key in role or key in role_l or key in specialty.lower():
            return prompt
    return f"你是{role}专家，按{specialty}视角输出结构化观点，必须给出依据、风险与下一步建议。"


def _skills_for_role(role: str, specialty: str) -> list[str]:
    out = []
    for key, vals in ROLE_SKILL_HINTS.items():
        if key in role or key in role.lower() or key in specialty.lower():
            out.extend(vals)
    return sorted(set(out))


def _extract_text_from_bytes(filename: str, data: bytes, content_type: str | None) -> str:
    name = filename.lower()
    ct = (content_type or "").lower()

    if name.endswith(".txt") or "text/plain" in ct:
        return data.decode("utf-8", errors="ignore")

    if name.endswith(".pdf") or "pdf" in ct:
        if not PdfReader:
            return ""
        reader = PdfReader(io.BytesIO(data))
        return "\n".join([(p.extract_text() or "") for p in reader.pages]).strip()

    if any(name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]) or "image/" in ct:
        if not (Image and pytesseract):
            return ""
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img, lang="eng+chi_sim")

    return data.decode("utf-8", errors="ignore")


def _extract_text_from_url(url: str) -> str:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
    except requests.exceptions.SSLError:
        # fallback for hosts with incomplete cert chain in some server environments
        r = requests.get(url, timeout=20, verify=False)
        r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    if "text/html" in ctype:
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        return " ".join(soup.get_text(" ").split())
    if "application/pdf" in ctype and PdfReader:
        reader = PdfReader(io.BytesIO(r.content))
        return "\n".join([(p.extract_text() or "") for p in reader.pages]).strip()
    return r.text


def _extract_clinical_sections(text: str) -> dict[str, list[str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    imaging_kw = ("CT", "MRI", "影像", "胸片", "超声", "X线")
    lab_kw = ("WBC", "CRP", "PCT", "肌酐", "ALT", "AST", "eGFR", "乳酸", "血小板")
    meds_kw = ("抗", "药", "剂量", "mg", "q12h", "q8h")

    imaging = [ln for ln in lines if any(k.lower() in ln.lower() for k in imaging_kw)][:30]
    labs = [ln for ln in lines if any(k.lower() in ln.lower() for k in lab_kw)][:50]
    meds = [ln for ln in lines if any(k.lower() in ln.lower() for k in meds_kw)][:50]

    return {"imaging": imaging, "labs": labs, "medications": meds}


def _store_case_doc(case_id: str, source: str, content: str, doc_type: str = "record") -> dict[str, Any]:
    sections = _extract_clinical_sections(content)
    now = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        cur = c.execute(
            "insert into mdt_case_docs(case_id, doc_type, source, content, sections, created_at) values (?,?,?,?,?,?)",
            (case_id, doc_type, source, content, json.dumps(sections, ensure_ascii=False), now),
        )
        doc_id = cur.lastrowid
    return {"doc_id": doc_id, "case_id": case_id, "sections": sections}


def _is_image_source(source: str) -> bool:
    src = (source or "").lower()
    return any(src.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"))


def _build_case_docs_context(case_id: str, limit: int = 3) -> dict[str, Any]:
    with conn() as c:
        rows = c.execute(
            "select id, doc_type, source, content, sections, created_at from mdt_case_docs where case_id=? order by id desc limit ?",
            (case_id, limit),
        ).fetchall()

    docs: list[dict[str, Any]] = []
    merged_sections = {"imaging": [], "labs": [], "medications": []}
    has_image_doc = False
    for r in rows:
        sections = json.loads(r["sections"] or "{}")
        for k in ("imaging", "labs", "medications"):
            merged_sections[k].extend(sections.get(k) or [])
        is_img = _is_image_source(r["source"])
        has_image_doc = has_image_doc or is_img
        docs.append(
            {
                "doc_id": r["id"],
                "doc_type": r["doc_type"],
                "source": r["source"],
                "created_at": r["created_at"],
                "is_image_source": is_img,
                "text_excerpt": (r["content"] or "")[:400],
                "sections": sections,
            }
        )

    # 简单去重截断，保证 payload 可读可追溯
    for k in merged_sections:
        seen = set()
        uniq = []
        for item in merged_sections[k]:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            uniq.append(text)
            if len(uniq) >= 15:
                break
        merged_sections[k] = uniq

    return {
        "case_id": case_id,
        "doc_count": len(docs),
        "has_image_doc": has_image_doc,
        "latest_docs": docs,
        "merged_sections": merged_sections,
    }


def _candidate_openclaw_config_paths() -> list[Path]:
    home = Path.home()
    return [
        home / ".openclaw" / "openclaw.json",
        home / ".config" / "openclaw" / "openclaw.json",
        home / ".config" / "openclaw" / "config.json",
    ]


def _load_models_from_openclaw_config() -> tuple[list[str], Optional[str], Optional[str], str]:
    """Return (models, default_model, source_path, note)."""
    last_err = ""
    for cfg in _candidate_openclaw_config_paths():
        if not cfg.exists() or not cfg.is_file():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            values: set[str] = set()

            defaults = (data.get("agents") or {}).get("defaults") or {}
            default_model = ((defaults.get("model") or {}).get("primary") or "").strip() or None

            for m in ((defaults.get("model") or {}).get("fallbacks") or []):
                mm = str(m).strip()
                if mm:
                    values.add(mm)

            for m in ((defaults.get("models") or {}).keys()):
                mm = str(m).strip()
                if mm:
                    values.add(mm)

            providers = ((data.get("models") or {}).get("providers") or {})
            for provider_name, provider_cfg in providers.items():
                for item in (provider_cfg or {}).get("models") or []:
                    if isinstance(item, dict):
                        mid = str(item.get("id") or item.get("name") or "").strip()
                    else:
                        mid = str(item).strip()
                    if mid:
                        values.add(mid if "/" in mid else f"{provider_name}/{mid}")

            models = sorted(values)
            if not models:
                return [], default_model, str(cfg), "config_loaded_but_no_models"
            return models, default_model, str(cfg), "config_loaded"
        except Exception as exc:  # pragma: no cover
            last_err = f"{type(exc).__name__}: {exc}"
            logger.warning("Failed parsing OpenClaw config %s: %s", cfg, last_err)

    return [], None, None, (last_err or "config_not_found")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _seed_default_agents()


init_db()
_seed_default_agents()


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if _should_log_path(request.url.path):
            logger.exception("access path=%s method=%s status=500 elapsed_ms=%s", request.url.path, request.method, elapsed_ms)
        raise

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if _should_log_path(request.url.path):
        logger.info(
            "access path=%s method=%s status=%s elapsed_ms=%s",
            request.url.path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "message": detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    detail = "request validation failed"
    return JSONResponse(
        status_code=422,
        content={"detail": detail, "message": detail, "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error path=%s", request.url.path)
    detail = f"internal server error: {type(exc).__name__}"
    return JSONResponse(status_code=500, content={"detail": detail, "message": detail})


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "mdt-hub", "db": str(DB_PATH)}


@app.get("/frontend.html")
def frontend_page() -> FileResponse:
    frontend = BASE_DIR.parent / "frontend.html"
    if not frontend.exists():
        raise HTTPException(status_code=404, detail="frontend.html not found")
    return FileResponse(frontend)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "mdt-hub",
        "db": str(DB_PATH),
        "time": datetime.now(timezone.utc).isoformat(),
        "version": app.version,
    }


@app.get("/models/available")
def list_available_models() -> dict[str, Any]:
    models, default_model, source_path, note = _load_models_from_openclaw_config()
    if models:
        out_default = default_model or DEFAULT_AGENT_MODEL
        logger.info("Loaded %d available models from %s", len(models), source_path)
        return {
            "models": models,
            "default_model": out_default,
            "source": source_path,
            "fallback": False,
            "note": note,
        }

    logger.warning("Model list fallback enabled: note=%s", note)
    return {
        "models": FALLBACK_MODEL_OPTIONS,
        "default_model": default_model or DEFAULT_AGENT_MODEL,
        "source": source_path or "builtin-fallback",
        "fallback": True,
        "note": f"fallback_used:{note}",
    }


@app.post("/cases/open")
def open_case(payload: CaseOpen) -> dict[str, Any]:
    opened_at = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        existed = c.execute("select opened_at from cases where case_id=?", (payload.case_id,)).fetchone()
        if existed:
            return {
                "ok": True,
                "case_id": payload.case_id,
                "opened_at": existed["opened_at"],
                "already_exists": True,
            }

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
    return {"ok": True, "case_id": payload.case_id, "opened_at": opened_at, "already_exists": False}


@app.post("/events")
async def ingest_event(event: MDTEvent) -> dict[str, Any]:
    body = _persist_event(event)
    await ws_manager.broadcast({"type": "mdt_event", "data": body})
    return {"accepted": True, "event": body}


@app.get("/agents")
def list_agents() -> dict[str, Any]:
    with conn() as c:
        rows = c.execute("select agent_id, role, specialty, prompt, model, enabled, created_at from mdt_agents order by created_at asc").fetchall()
    return {"count": len(rows), "agents": [dict(r) for r in rows]}


@app.post("/agents")
def create_agent(payload: AgentCreate) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    auto_prompt = _auto_prompt_for_role(payload.role, payload.specialty)
    final_prompt = (auto_prompt + "\n" + payload.prompt).strip() if payload.prompt else auto_prompt
    skill_suggestions = _skills_for_role(payload.role, payload.specialty)
    model = (payload.model or "").strip() or None

    with conn() as c:
        try:
            c.execute(
                "insert into mdt_agents(agent_id, role, specialty, prompt, model, enabled, created_at) values (?,?,?,?,?,?,?)",
                (payload.agent_id, payload.role, payload.specialty, final_prompt, model, 1 if payload.enabled else 0, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="agent_id already exists")
    return {
        "ok": True,
        "agent_id": payload.agent_id,
        "generated_prompt": auto_prompt,
        "final_prompt": final_prompt,
        "model": model,
        "skill_suggestions": skill_suggestions,
        "web_learning": "enabled" if payload.auto_learn_web else "disabled",
    }


@app.post("/agents/{agent_id}/model")
def update_agent_model(agent_id: str, payload: AgentModelUpdate) -> dict[str, Any]:
    updates: list[str] = []
    values: list[Any] = []

    if payload.model is not None:
        model = payload.model.strip() or None
        updates.append("model=?")
        values.append(model)
    else:
        model = None

    if payload.enabled is not None:
        updates.append("enabled=?")
        values.append(1 if payload.enabled else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    with conn() as c:
        values.append(agent_id)
        cur = c.execute(f"update mdt_agents set {', '.join(updates)} where agent_id=?", tuple(values))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="agent not found")

        row = c.execute("select model, enabled from mdt_agents where agent_id=?", (agent_id,)).fetchone()

    return {
        "ok": True,
        "agent_id": agent_id,
        "model": row["model"] if row else model,
        "enabled": bool(row["enabled"]) if row else payload.enabled,
    }


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


@app.post("/agents/{agent_id}/knowledge/url")
def feed_knowledge_url(agent_id: str, payload: URLIngest) -> dict[str, Any]:
    text = _extract_text_from_url(payload.url)
    if not text:
        raise HTTPException(status_code=400, detail="unable to extract text from url")
    content = text[:12000]
    return feed_knowledge(agent_id, KnowledgeFeed(content=content, source=payload.url, tags=["url"]))


@app.post("/agents/{agent_id}/knowledge/upload")
async def feed_knowledge_upload(agent_id: str, file: UploadFile = File(...), tags: str = Form(default="")) -> dict[str, Any]:
    data = await file.read()
    text = _extract_text_from_bytes(file.filename or "upload.bin", data, file.content_type)
    if not text:
        raise HTTPException(status_code=400, detail="unable to extract text from file")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return feed_knowledge(agent_id, KnowledgeFeed(content=text[:12000], source=file.filename or "upload", tags=tag_list or ["file"]))


@app.post("/cases/{case_id}/documents/url")
def ingest_case_doc_url(case_id: str, payload: URLIngest) -> dict[str, Any]:
    _ensure_case(case_id)
    text = _extract_text_from_url(payload.url)
    if not text:
        raise HTTPException(status_code=400, detail="unable to extract text from url")
    stored = _store_case_doc(case_id, payload.url, text[:30000], doc_type="url")
    return {"ok": True, **stored}


@app.post("/cases/{case_id}/documents/upload")
async def ingest_case_doc_upload(case_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    _ensure_case(case_id)
    data = await file.read()
    text = _extract_text_from_bytes(file.filename or "upload.bin", data, file.content_type)
    if not text:
        raise HTTPException(status_code=400, detail="unable to extract text from file")
    stored = _store_case_doc(case_id, file.filename or "upload", text[:30000], doc_type="file")
    return {"ok": True, **stored}


@app.post("/discussion/submit")
async def discussion_submit(payload: DiscussionInput) -> dict[str, Any]:
    """模拟现实 MDT：先录入临床医生发言，再按角色生成一轮专家回应。"""
    round_no = payload.round_no or max(1, _latest_round(payload.case_id))

    confirmed_sections = payload.confirmed_sections.model_dump(mode="json") if payload.confirmed_sections else None
    docs_context = _build_case_docs_context(payload.case_id) if payload.enable_docs_context else {
        "case_id": payload.case_id,
        "doc_count": 0,
        "has_image_doc": False,
        "latest_docs": [],
        "merged_sections": {"imaging": [], "labs": [], "medications": []},
    }
    adopted_lines: list[str] = []
    if payload.confirmed_sections:
        for k in ("imaging", "labs", "medications"):
            for item in getattr(payload.confirmed_sections, k):
                if item.confirmed and item.text.strip():
                    adopted_lines.append(f"[{k}] {item.text.strip()}")

    human_payload: dict[str, Any] = {"text": payload.message, "docs_context": docs_context}
    if confirmed_sections:
        human_payload["confirmed_sections"] = confirmed_sections

    human_event = MDTEvent(
        case_id=payload.case_id,
        round_no=round_no,
        event_type="discussion_message",
        speaker=payload.speaker,
        specialty="human",
        payload=human_payload,
        confidence=None,
    )
    human_body = _persist_event(human_event)
    await ws_manager.broadcast({"type": "mdt_event", "data": human_body})

    generated: list[dict[str, Any]] = []
    for agent_id, specialty, lens, agent_model in _load_enabled_agents():
        learned = _knowledge_snippet(agent_id)
        model_used = agent_model or DEFAULT_AGENT_MODEL
        discussion_text = f"针对输入“{payload.message}”，从{lens}角度建议补充评估并形成可执行方案。"
        if adopted_lines:
            discussion_text += " 已采纳病历要点：" + "；".join(adopted_lines[:3])
        if docs_context.get("doc_count"):
            discussion_text += f" 参考了{docs_context.get('doc_count')}份病历文档。"

        ev = MDTEvent(
            case_id=payload.case_id,
            round_no=round_no,
            event_type="agent_opinion",
            speaker=agent_id,
            specialty=specialty,
            payload={
                "discussion": discussion_text,
                "learned_context": learned,
                "source": "simulated_role_response",
                "model_used": model_used,
                "confirmed_sections": confirmed_sections,
                "docs_context": docs_context,
                "case_context": {
                    "message": payload.message,
                    "adopted_confirmed_lines": adopted_lines[:10],
                    "doc_refs": [d.get("doc_id") for d in docs_context.get("latest_docs", [])],
                },
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
        "confirmed_sections_received": bool(confirmed_sections),
        "confirmed_adopted_count": len(adopted_lines),
        "docs_context_enabled": payload.enable_docs_context,
        "docs_context_doc_count": docs_context.get("doc_count", 0),
        "docs_context_has_image_doc": docs_context.get("has_image_doc", False),
    }


@app.post("/discussion/review")
async def discussion_review(payload: RoundReviewInput) -> dict[str, Any]:
    with conn() as c:
        base_rows = c.execute(
            "select event_id, speaker, payload from mdt_events where case_id=? and round_no=? and event_type='agent_opinion' order by event_id asc",
            (payload.case_id, payload.from_round),
        ).fetchall()

    if not base_rows:
        raise HTTPException(status_code=404, detail="no agent opinions found for source round")

    opinions = [
        {
            "event_id": r["event_id"],
            "speaker": r["speaker"],
            "payload": json.loads(r["payload"]),
        }
        for r in base_rows
    ]

    generated = 0
    docs_context = _build_case_docs_context(payload.case_id)
    agents = _load_enabled_agents()
    for idx, (agent_id, specialty, lens, agent_model) in enumerate(agents):
        target = opinions[(idx + 1) % len(opinions)]
        stance = "oppose" if idx % 2 == 0 else "support"
        ev = MDTEvent(
            case_id=payload.case_id,
            round_no=payload.to_round,
            event_type="agent_review",
            speaker=agent_id,
            specialty=specialty,
            payload={
                "stance": stance,
                "target_event_id": target["event_id"],
                "target_speaker": target["speaker"],
                "model_used": agent_model or DEFAULT_AGENT_MODEL,
                "review": f"{agent_id} 对 {target['speaker']} 的观点给出{('反驳' if stance=='oppose' else '支持')}：从{lens}角度补充证据与边界。",
                "docs_context": docs_context,
                "case_context": {
                    "source_round": payload.from_round,
                    "doc_refs": [d.get("doc_id") for d in docs_context.get("latest_docs", [])],
                },
            },
            confidence=0.74,
            reply_to_event_id=target["event_id"],
        )
        body = _persist_event(ev)
        generated += 1
        await ws_manager.broadcast({"type": "mdt_event", "data": body})

    orchestrator = MDTEvent(
        case_id=payload.case_id,
        round_no=payload.to_round,
        event_type="conflict_detected",
        speaker="mdt-orchestrator",
        specialty="mdt",
        payload={
            "summary": "二轮互评完成，已形成支持/反驳关系图。",
            "next_step": "resolve_conflicts_and_finalize",
        },
        confidence=0.83,
    )
    body = _persist_event(orchestrator)
    await ws_manager.broadcast({"type": "mdt_event", "data": body})

    return {"accepted": True, "case_id": payload.case_id, "generated_count": generated + 1}


@app.get("/cases/{case_id}/documents")
def list_case_docs(case_id: str) -> dict[str, Any]:
    with conn() as c:
        rows = c.execute(
            "select id, doc_type, source, sections, created_at from mdt_case_docs where case_id=? order by id desc",
            (case_id,),
        ).fetchall()
    docs = []
    for r in rows:
        docs.append({
            "id": r["id"],
            "doc_type": r["doc_type"],
            "source": r["source"],
            "sections": json.loads(r["sections"] or "{}"),
            "created_at": r["created_at"],
        })
    return {"case_id": case_id, "count": len(docs), "documents": docs}


@app.get("/cases/{case_id}/conflicts")
def case_conflicts(case_id: str) -> dict[str, Any]:
    with conn() as c:
        rows = c.execute(
            "select event_id, speaker, specialty, payload, reply_to_event_id from mdt_events where case_id=? and event_type in ('agent_review','conflict_detected') order by event_id asc",
            (case_id,),
        ).fetchall()

    edges = []
    nodes = {}
    for r in rows:
        sp = r["speaker"]
        nodes[sp] = {"id": sp, "specialty": r["specialty"]}
        if r["reply_to_event_id"]:
            payload = json.loads(r["payload"])
            target = payload.get("target_speaker", "unknown")
            nodes[target] = {"id": target, "specialty": "unknown"}
            edges.append(
                {
                    "from": sp,
                    "to": target,
                    "stance": payload.get("stance", "neutral"),
                    "event_id": r["event_id"],
                }
            )

    return {"case_id": case_id, "nodes": list(nodes.values()), "edges": edges, "count": len(edges)}


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
