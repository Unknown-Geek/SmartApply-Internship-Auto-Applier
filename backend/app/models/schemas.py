"""backend/app/models/schemas.py — Pydantic schemas for API."""
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, HttpUrl


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"   # paused — agent needs human input
    COMPLETED = "completed"
    FAILED = "failed"


class ApplyRequest(BaseModel):
    job_url: str
    notes: Optional[str] = None  # Optional applicant notes / custom instructions


class LogEntry(BaseModel):
    timestamp: datetime
    level: str  # "thought" | "action" | "observation" | "error" | "info"
    message: str
    step: Optional[int] = None


class AnswerRequest(BaseModel):
    answer: str


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    job_url: str
    created_at: datetime
    updated_at: datetime
    logs: List[LogEntry] = []
    result: Optional[str] = None
    error: Optional[str] = None
    question: Optional[str] = None  # set when status == WAITING


class ServiceStatusSchema(BaseModel):
    ok: bool
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    identity_loaded: bool
    ollama: ServiceStatusSchema
    context_mode: ServiceStatusSchema
    pinchtab: ServiceStatusSchema
    version: str = "1.0.0"
