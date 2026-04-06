"""
backend/app/api/jobs.py
REST endpoints for job application task management.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.schemas import ApplyRequest, TaskResponse, TaskStatus, LogEntry
from app.agent.agent import run_agent

router = APIRouter()

# In-memory task store (use Redis/DB for production)
_tasks: Dict[str, dict] = {}


def _get_task(task_id: str) -> dict:
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return _tasks[task_id]


def _append_log(task_id: str, level: str, message: str, step: int = None):
    """Append a log entry to the task."""
    if task_id in _tasks:
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            step=step,
        )
        _tasks[task_id]["logs"].append(entry)
        _tasks[task_id]["updated_at"] = datetime.utcnow()


def _run_agent_task(task_id: str, job_url: str):
    """Background task: runs the agent and updates task state."""
    _tasks[task_id]["status"] = TaskStatus.RUNNING
    _append_log(task_id, "info", f"🤖 Agent started for: {job_url}")

    step_counter = [0]

    def log_callback(level: str, message: str):
        step_counter[0] += 1
        _append_log(task_id, level, message, step=step_counter[0])

    try:
        result = run_agent(job_url=job_url, log_callback=log_callback)
        _tasks[task_id]["status"] = TaskStatus.COMPLETED
        _tasks[task_id]["result"] = result
        _append_log(task_id, "info", f"✅ Agent completed: {result}")
    except Exception as e:
        _tasks[task_id]["status"] = TaskStatus.FAILED
        _tasks[task_id]["error"] = str(e)
        _append_log(task_id, "error", f"❌ Agent failed: {e}")
    finally:
        _tasks[task_id]["updated_at"] = datetime.utcnow()


@router.post("/apply", response_model=TaskResponse, status_code=202)
async def apply_for_job(request: ApplyRequest, background_tasks: BackgroundTasks):
    """
    Submit a job URL for autonomous application.
    Returns a task_id immediately; monitor via GET /api/jobs/{task_id} or WS.
    """
    task_id = str(uuid.uuid4())
    now = datetime.utcnow()

    _tasks[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "job_url": request.job_url,
        "created_at": now,
        "updated_at": now,
        "logs": [],
        "result": None,
        "error": None,
    }

    # Run agent in background thread (blocking smolagents code)
    background_tasks.add_task(
        asyncio.get_event_loop().run_in_executor,
        None,
        _run_agent_task,
        task_id,
        request.job_url,
    )

    return TaskResponse(**_tasks[task_id])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get the status and logs of an application task."""
    task = _get_task(task_id)
    return TaskResponse(**task)


@router.get("/", response_model=list[TaskResponse])
async def list_tasks():
    """List all application tasks."""
    return [TaskResponse(**t) for t in _tasks.values()]
