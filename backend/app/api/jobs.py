"""
backend/app/api/jobs.py
REST endpoints for job application task management.
"""
import asyncio
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict

import httpx
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.agent import human_input
from app.agent.agent import run_agent
from app.models.schemas import AnswerRequest, ApplyRequest, LogEntry, TaskResponse, TaskStatus

router = APIRouter()

# Thread pool for blocking agent runs (smolagents is synchronous)
_executor = ThreadPoolExecutor(max_workers=2)

# In-memory task store — keyed by task_id
_tasks: Dict[str, dict] = {}

SESSIONS_DIR = os.getenv("SESSIONS_DIR", "/app/data/sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Optional n8n Application Logger webhook (set N8N_LOG_WEBHOOK_URL in .env)
N8N_LOG_WEBHOOK_URL = os.getenv("N8N_LOG_WEBHOOK_URL", "")
# Webhook n8n calls when the agent needs a human answer (set N8N_QUESTION_WEBHOOK_URL in .env)
N8N_QUESTION_WEBHOOK_URL = os.getenv("N8N_QUESTION_WEBHOOK_URL", "")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _notify_n8n_logger(job_url: str, status: str, result: str = "") -> None:
    """
    Fire-and-forget POST to the n8n Application Logger webhook.

    Sends the payload shape expected by the 'SmartApply - Application Logger'
    n8n workflow:
      { url, status, details, fields_filled, company, title, issues }

    Silently skips if N8N_LOG_WEBHOOK_URL is not configured.
    Runs synchronously inside the agent thread — never blocks a job run because
    it uses a short timeout and all exceptions are swallowed.
    """
    if not N8N_LOG_WEBHOOK_URL:
        return
    try:
        # Best-effort keyword extraction from result string
        fields_filled = 0
        if "filled" in result.lower():
            import re
            m = re.search(r"(\d+)\s*field", result, re.IGNORECASE)
            if m:
                fields_filled = int(m.group(1))

        payload = {
            "url": job_url,
            "status": status,          # "success" | "failed"
            "details": result[:500],   # truncate for Sheets cell limit
            "fields_filled": fields_filled,
            "company": "",             # n8n can enrich this from the queue sheet
            "title": "",
            "issues": [] if status == "success" else [result[:200]],
        }
        httpx.post(N8N_LOG_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"n8n log webhook failed (non-fatal): {exc}")


def _get_task(task_id: str) -> dict:
    if task_id not in _tasks:
        # Try loading from disk
        path = os.path.join(SESSIONS_DIR, f"{task_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                _tasks[task_id] = json.load(f)
        else:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return _tasks[task_id]


def _persist_task(task_id: str):
    """Write task state to disk for durability."""
    task = _tasks.get(task_id)
    if not task:
        return
    path = os.path.join(SESSIONS_DIR, f"{task_id}.json")
    try:
        serializable = {**task, "logs": [
            {**log, "timestamp": log["timestamp"].isoformat() if hasattr(log.get("timestamp"), "isoformat") else log.get("timestamp", "")}
            for log in task.get("logs", [])
        ]}
        with open(path, "w") as f:
            json.dump(serializable, f, default=str)
    except Exception:
        pass


def _append_log(task_id: str, level: str, message: str, step: int = None):
    """Append a log entry to the task and persist."""
    if task_id not in _tasks:
        return
    entry = {
        "timestamp": datetime.utcnow(),
        "level": level,
        "message": message,
        "step": step,
    }
    _tasks[task_id]["logs"].append(entry)
    _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
    _persist_task(task_id)


def _run_agent_task(task_id: str, job_url: str):
    """Blocking function run in thread pool: runs the agent and updates task state."""
    _tasks[task_id]["status"] = TaskStatus.RUNNING.value
    _append_log(task_id, "info", f"🤖 Agent started for: {job_url}")

    step_counter = [0]

    def log_callback(level: str, message: str):
        step_counter[0] += 1
        _append_log(task_id, level, message, step=step_counter[0])

    def user_input_fn(question: str) -> str:
        """Called by the agent when it needs a human answer. Blocks until answered."""
        _tasks[task_id]["status"] = TaskStatus.WAITING.value
        _tasks[task_id]["question"] = question
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _persist_task(task_id)
        _append_log(task_id, "info", f"⏸️  Agent waiting for human input: {question}")

        # Notify n8n → Telegram
        if N8N_QUESTION_WEBHOOK_URL:
            try:
                httpx.post(
                    N8N_QUESTION_WEBHOOK_URL,
                    json={"task_id": task_id, "question": question},
                    timeout=10,
                )
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).warning(f"n8n question webhook failed: {exc}")

        # Block here until the operator answers via /api/jobs/{task_id}/answer
        answer = human_input.request_input(task_id, question)

        # Resume
        _tasks[task_id]["status"] = TaskStatus.RUNNING.value
        _tasks[task_id]["question"] = None
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _persist_task(task_id)
        _append_log(task_id, "info", f"▶️  Resuming — operator answered: {answer[:80]}")
        return answer

    try:
        result = run_agent(job_url=job_url, log_callback=log_callback, user_input_fn=user_input_fn)
        _tasks[task_id]["status"] = TaskStatus.COMPLETED.value
        _tasks[task_id]["result"] = str(result)
        _append_log(task_id, "info", f"✅ Application completed: {result}")
        _notify_n8n_logger(job_url=job_url, status="success", result=str(result))
    except Exception as e:
        _tasks[task_id]["status"] = TaskStatus.FAILED.value
        _tasks[task_id]["error"] = str(e)
        _append_log(task_id, "error", f"❌ Agent failed: {e}")
        _notify_n8n_logger(job_url=job_url, status="failed", result=str(e))
    finally:
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _persist_task(task_id)


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/apply", response_model=TaskResponse, status_code=202)
async def apply_for_job(request: ApplyRequest):
    """
    Submit a job URL for autonomous application.
    Returns a task_id immediately; monitor via GET /api/jobs/{task_id} or WS.
    """
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    _tasks[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "job_url": request.job_url,
        "created_at": now,
        "updated_at": now,
        "logs": [],
        "result": None,
        "error": None,
    }
    _persist_task(task_id)

    # Submit to thread pool — agent is blocking; this keeps FastAPI responsive
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_agent_task, task_id, request.job_url)

    return _task_to_response(_tasks[task_id])


@router.get("/waiting", response_model=list[dict])
async def get_waiting_tasks():
    """Return all tasks currently paused waiting for human input."""
    return human_input.list_waiting()


@router.post("/{task_id}/answer")
async def answer_task(task_id: str, body: AnswerRequest):
    """
    Provide a human answer to an agent that is waiting for input.
    The agent thread unblocks immediately and resumes with the supplied answer.
    """
    task = _get_task(task_id)  # raises 404 if not found
    if task.get("status") != TaskStatus.WAITING.value:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} is not in WAITING state (current: {task.get('status')})",
        )
    unblocked = human_input.provide_answer(task_id, body.answer)
    if not unblocked:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} is not waiting for input right now.",
        )
    return {"ok": True, "task_id": task_id, "message": "Answer delivered — agent resuming."}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get the status and logs of an application task."""
    task = _get_task(task_id)
    return _task_to_response(task)


@router.get("/", response_model=list[TaskResponse])
async def list_tasks():
    """List all application tasks (in-memory + on-disk sessions)."""
    # Also load any persisted sessions not in memory
    try:
        for fname in os.listdir(SESSIONS_DIR):
            if fname.endswith(".json"):
                tid = fname[:-5]
                if tid not in _tasks:
                    path = os.path.join(SESSIONS_DIR, fname)
                    with open(path) as f:
                        _tasks[tid] = json.load(f)
    except Exception:
        pass
    return [_task_to_response(t) for t in sorted(
        _tasks.values(), key=lambda x: x.get("created_at", ""), reverse=True
    )]


def _task_to_response(task: dict) -> TaskResponse:
    """Convert raw task dict to TaskResponse, handling ISO string timestamps."""
    logs = []
    for log in task.get("logs", []):
        ts = log.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif not isinstance(ts, datetime):
            ts = datetime.utcnow()
        logs.append(LogEntry(
            timestamp=ts,
            level=log.get("level", "info"),
            message=log.get("message", ""),
            step=log.get("step"),
        ))

    created = task.get("created_at")
    updated = task.get("updated_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)

    return TaskResponse(
        task_id=task["task_id"],
        status=TaskStatus(task.get("status", "pending")),
        job_url=task["job_url"],
        created_at=created or datetime.utcnow(),
        updated_at=updated or datetime.utcnow(),
        logs=logs,
        result=task.get("result"),
        error=task.get("error"),
    )
