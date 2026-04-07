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

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.agent.agent import run_agent
from app.models.schemas import ApplyRequest, LogEntry, TaskResponse, TaskStatus

router = APIRouter()

# Thread pool for blocking agent runs (smolagents is synchronous)
_executor = ThreadPoolExecutor(max_workers=2)

# In-memory task store — keyed by task_id
_tasks: Dict[str, dict] = {}

SESSIONS_DIR = os.getenv("SESSIONS_DIR", "/app/data/sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

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

    try:
        result = run_agent(job_url=job_url, log_callback=log_callback)
        _tasks[task_id]["status"] = TaskStatus.COMPLETED.value
        _tasks[task_id]["result"] = str(result)
        _append_log(task_id, "info", f"✅ Application completed: {result}")
    except Exception as e:
        _tasks[task_id]["status"] = TaskStatus.FAILED.value
        _tasks[task_id]["error"] = str(e)
        _append_log(task_id, "error", f"❌ Agent failed: {e}")
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
