"""backend/app/models/schemas.py — Pydantic schemas for API."""
from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, HttpUrl
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
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


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    job_url: str
    created_at: datetime
    updated_at: datetime
    logs: List[LogEntry] = []
    result: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    ollama: bool
    model: str
    identity_loaded: bool
    version: str = "1.0.0"
