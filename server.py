"""
server.py — DIRESO Agent Board FastAPI Server
Start: uvicorn server:app --host 0.0.0.0 --port 8501
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from memory.store import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="DIRESO Agent Board", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AGENT_META = {
    "ceo":              {"label": "CEO",       "desc": "Co-CEO & Strategie",          "tools": ["workspace", "web"],                    "tier": "executive"},
    "cfo":              {"label": "CFO",       "desc": "Finanzen & Fördergelder",      "tools": ["workspace", "web"],                    "tier": "c-suite"},
    "coo":              {"label": "COO",       "desc": "Prozesse & Effizienz",         "tools": ["workspace", "web"],                    "tier": "c-suite"},
    "cmo":              {"label": "CMO",       "desc": "Marketing & Social Media",     "tools": ["workspace", "web", "email", "social"], "tier": "c-suite"},
    "cso":              {"label": "CSO",       "desc": "Sales & CRM",                  "tools": ["workspace", "web", "email"],           "tier": "c-suite"},
    "cdo":              {"label": "CDO",       "desc": "Website & Digital",            "tools": ["workspace", "web", "file", "browser"], "tier": "c-suite"},
    "cto":              {"label": "CTO",       "desc": "Technologie & Code",           "tools": ["workspace", "web", "file"],            "tier": "c-suite"},
    "legal":            {"label": "Legal",     "desc": "DSGVO & Compliance",           "tools": ["workspace", "web"],                    "tier": "specialist"},
    "hr":               {"label": "HR",        "desc": "Personal & Recruiting",        "tools": ["workspace", "web", "email"],           "tier": "specialist"},
    "ir":               {"label": "IR",        "desc": "Investor Relations",           "tools": ["workspace", "web", "email"],           "tier": "specialist"},
    "customer_success": {"label": "CS",        "desc": "Customer Success",             "tools": ["workspace", "web", "email"],           "tier": "specialist"},
    "portfolio_assistant": {"label": "Portfolio", "desc": "Portfolio-Assistent",       "tools": ["workspace", "web"],                    "tier": "external"},
    "report_generator":    {"label": "Reports",   "desc": "Report-Generator",          "tools": ["workspace", "web"],                    "tier": "external"},
}

PROMPTS_DIR = Path(__file__).parent / "prompts"

class TaskCreate(BaseModel):
    task_text: str
    session_id: str
    agent_name: str = ""

class SessionCreate(BaseModel):
    label: str = "Neue Session"

class PromptSave(BaseModel):
    content: str

class ContextUpdate(BaseModel):
    data: dict

class BriefingAction(BaseModel):
    session_id: str
    agent_name: str
    task_text: str

class BriefingCreate(BaseModel):
    session_id: str

@app.get("/api/agents")
def get_agents():
    return AGENT_META

@app.get("/api/sessions/latest")
def get_latest_session():
    conn = store._connect()
    row = conn.execute("SELECT session_id FROM tasks ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    if row and row["session_id"]:
        return {"session_id": row["session_id"]}
    session_id = store.create_session(label="Neue Session")
    return {"session_id": session_id}

@app.post("/api/sessions")
def create_session(body: SessionCreate):
    session_id = store.create_session(label=body.label)
    return {"session_id": session_id}

@app.get("/api/tasks")
def get_tasks(session_id: str, limit: int = 30):
    return store.get_recent_tasks(session_id, limit=limit)

@app.post("/api/tasks")
def create_task(body: TaskCreate):
    task_id = store.enqueue_task(body.task_text, body.session_id, body.agent_name)
    return {"id": task_id}

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/api/workspace")
def list_workspace():
    files = []
    for f in sorted(settings.workspace_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({"filename": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime})
    return files

@app.get("/api/workspace/{filename:path}")
def read_workspace_file(filename: str):
    fp = settings.workspace_dir / filename
    if not fp.exists():
        matches = sorted(settings.workspace_dir.glob(f"*{filename}"), key=lambda p: p.stat().st_mtime, reverse=True)
        fp = matches[0] if matches else fp
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return PlainTextResponse(fp.read_text(encoding="utf-8"))

@app.delete("/api/workspace/{filename:path}")
def delete_workspace_file(filename: str):
    fp = settings.workspace_dir / filename
    if not fp.exists():
        matches = sorted(settings.workspace_dir.glob(f"*{filename}"), key=lambda p: p.stat().st_mtime, reverse=True)
        fp = matches[0] if matches else fp
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File not found")
    store.delete_artifact(fp.name)
    fp.unlink()
    return {"ok": True}

@app.post("/api/workspace/cleanup")
def cleanup_workspace():
    deleted = 0
    for f in settings.workspace_dir.glob("*"):
        if f.is_file() and f.stat().st_size == 0:
            store.delete_artifact(f.name)
            f.unlink()
            deleted += 1
    for a in store.get_recent_artifacts(limit=200):
        fp = settings.workspace_dir / a["filename"]
        if not fp.exists() and not list(settings.workspace_dir.glob(f"*{a['filename']}")):
            store.delete_artifact(a["filename"])
            deleted += 1
    return {"deleted": deleted}

@app.get("/api/artifacts")
def get_artifacts(limit: int = 50):
    return store.get_recent_artifacts(limit=limit)

@app.get("/api/briefings")
def get_briefings(limit: int = 5):
    return store.get_briefings(limit=limit)

@app.delete("/api/briefings/{briefing_id}")
def delete_briefing(briefing_id: str):
    found = store.delete_briefing(briefing_id)
    if not found:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return {"ok": True}

@app.post("/api/briefings/action")
def dispatch_briefing_action(body: BriefingAction):
    task_id = store.enqueue_task(body.task_text, body.session_id, body.agent_name)
    return {"id": task_id}

@app.post("/api/briefings/create")
def create_briefing(body: BriefingCreate):
    tasks = store.get_recent_tasks(body.session_id, limit=1)
    if not tasks:
        raise HTTPException(status_code=400, detail="Keine Tasks in dieser Session")
    last_result = tasks[0].get("result_text", "")
    if not last_result:
        raise HTTPException(status_code=400, detail="Letzter Task hat kein Ergebnis")
    from orchestrator.orchestrator import orchestrator
    b = orchestrator.create_board_briefing(last_result, session_id=body.session_id)
    return b

@app.get("/api/prompts/{agent_name}")
def get_prompt(agent_name: str):
    if agent_name == "orchestrator":
        path = PROMPTS_DIR / "orchestrator_system.txt"
    elif agent_name in ("portfolio_assistant", "report_generator"):
        path = PROMPTS_DIR / "external" / f"{agent_name}_system.txt"
    else:
        path = PROMPTS_DIR / "internal" / f"{agent_name}_system.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"))

@app.put("/api/prompts/{agent_name}")
def save_prompt(agent_name: str, body: PromptSave):
    if agent_name == "orchestrator":
        path = PROMPTS_DIR / "orchestrator_system.txt"
    elif agent_name in ("portfolio_assistant", "report_generator"):
        path = PROMPTS_DIR / "external" / f"{agent_name}_system.txt"
    else:
        path = PROMPTS_DIR / "internal" / f"{agent_name}_system.txt"
    path.write_text(body.content, encoding="utf-8")
    return {"ok": True}

@app.get("/api/context")
def get_context():
    ctx_path = Path(__file__).parent / "company_context.json"
    if not ctx_path.exists():
        return {}
    return json.loads(ctx_path.read_text(encoding="utf-8"))

@app.put("/api/context")
def save_context(body: ContextUpdate):
    ctx_path = Path(__file__).parent / "company_context.json"
    ctx_path.write_text(json.dumps(body.data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}

@app.get("/api/status")
def get_status():
    pid_file = Path(__file__).parent / "worker.pid"
    worker_alive = False
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            worker_alive = True
        except (OSError, ValueError):
            pass
    return {
        "worker_alive": worker_alive,
        "search_configured": settings.is_search_configured(),
        "email_configured": settings.is_email_configured(),
        "social_configured": settings.is_social_configured(),
        "model": settings.anthropic_model,
    }

# Static files — MUST BE LAST
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
