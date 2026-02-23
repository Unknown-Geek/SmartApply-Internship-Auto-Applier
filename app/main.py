# =============================================================================
# SmartApply — FastAPI Application Entry Point
# =============================================================================
# Autonomous internship auto-applier powered by Cerebras + Playwright.
#
# Endpoints:
#   GET  /                      — API info
#   GET  /health                — Health check
#   POST /agent/run             — Run a free-form agent task (Cerebras)
#   POST /profile/ingest        — Ingest resume / profile
#   GET  /profile               — View stored profile
#   POST /profile/set           — Manually set a profile field
#   POST /jobs/search           — Search for internships
#   GET  /jobs                  — List discovered jobs
#   POST /jobs/{id}/analyze     — Analyze a job's application page
#   POST /jobs/{id}/apply       — Apply to a specific job
#   POST /pipeline/run          — Full search → analyze → apply pipeline
#   GET  /stats                 — Dashboard statistics
#   POST /memory                — Store a fact
#   GET  /memory                — Recall facts
#   GET  /sessions              — List agent session history
#
# Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
# =============================================================================

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.database import (
    init_db, get_stats, get_jobs, get_all_profile, set_profile,
    get_applications, recall, remember, recall_as_context,
)
from app.agent.cerebras_agent import AgentResult
from app.agent.orchestrator import SmartApplyOrchestrator
from app.telegram_bot import SmartApplyBot, init_bot, get_bot


# =============================================================================
# Request / Response Models
# =============================================================================

class AgentTaskRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=5000,
                      description="The task / prompt for the agent")
    thinking: str = Field(default="medium",
                          description="Reasoning level: off|minimal|low|medium|high")
    timeout: int = Field(default=600, description="Timeout in seconds")


class AgentTaskResponse(BaseModel):
    success: bool
    task: str
    session_id: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None


class ProfileIngestRequest(BaseModel):
    resume_text: str = Field(..., min_length=10,
                             description="Raw text of resume / profile")


class ProfileFieldRequest(BaseModel):
    key: str
    value: str


class JobSearchRequest(BaseModel):
    criteria: str = Field(..., min_length=3,
                          description="Search criteria (role, location, tech, etc.)")


class PipelineRequest(BaseModel):
    criteria: str = Field(..., min_length=3)
    max_applications: int = Field(default=5, ge=1, le=20)
    auto_apply: bool = Field(default=False,
                             description="Auto-submit applications (use with caution)")


class MemoryRequest(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    cerebras_model: str
    api_key_set: bool
    db_initialized: bool
    telegram_connected: bool = False


# =============================================================================
# Lifespan — startup / shutdown
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Validate API key
    api_key = settings.effective_api_key
    if not api_key:
        print("WARNING: No CEREBRAS_API_KEY set — agent calls will fail.")
    else:
        os.environ.setdefault("CEREBRAS_API_KEY", api_key)

    # Initialize SQLite
    init_db(settings.sqlite_db_path)

    print(f"SmartApply starting...")
    print(f"  Environment   : {settings.app_env}")
    print(f"  Server        : http://{settings.host}:{settings.port}")
    print(f"  Cerebras model: {settings.cerebras_model}")
    print(f"  Cerebras key  : {'set' if api_key else 'MISSING'}")
    print(f"  Headless      : {settings.headless}")
    print(f"  SQLite DB     : {settings.sqlite_db_path}")
    print(f"  Telegram      : {'enabled' if settings.telegram_enabled else 'disabled'}")
    print(f"  Docs          : http://{settings.host}:{settings.port}/docs")

    # Start Telegram bot if configured
    bot = None
    if settings.telegram_enabled:
        try:
            bot = init_bot(settings.telegram_bot_token, settings.telegram_chat_id)
            await bot.start()
            print(f"  Telegram bot  : started (chat_id: {settings.telegram_chat_id})")
        except Exception as e:
            print(f"  Telegram bot  : FAILED to start — {e}")
            bot = None
    else:
        print("  Telegram bot  : not configured (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")

    yield

    # Shutdown
    if bot:
        await bot.stop()
    print("SmartApply shutting down.")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="SmartApply — Internship Auto-Applier",
    description=(
        "Autonomous internship application agent powered by Cerebras (gpt-oss-120b) + Playwright. "
        "Search, analyze, and apply to internships via an AI-driven pipeline."
    ),
    version="0.4.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Root / Health
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "SmartApply — Internship Auto-Applier",
        "version": "0.4.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "agent": "/agent/run",
            "profile": "/profile",
            "jobs": "/jobs",
            "pipeline": "/pipeline/run",
            "stats": "/stats",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version="0.4.0",
        environment=settings.app_env,
        cerebras_model=settings.cerebras_model,
        api_key_set=bool(settings.effective_api_key),
        db_initialized=os.path.isfile(settings.sqlite_db_path),
        telegram_connected=get_bot() is not None and get_bot()._running,
    )


# =============================================================================
# Agent — free-form task
# =============================================================================

@app.post("/agent/run", response_model=AgentTaskResponse, tags=["Agent"])
async def run_agent_task(request: AgentTaskRequest):
    """
    Execute a free-form task using the Cerebras agent with browser tools.

    The agent has access to a headless browser (Playwright) and can
    navigate to websites, fill forms, click buttons, and more.
    """
    settings = get_settings()
    if not settings.effective_api_key:
        raise HTTPException(500, "No Cerebras API key configured.")

    orchestrator = SmartApplyOrchestrator(
        thinking=request.thinking,
        timeout=request.timeout,
    )
    result = await orchestrator.run_task(request.task)

    return AgentTaskResponse(
        success=result.success,
        task=request.task,
        session_id=result.session_id,
        result=result.text if result.success else None,
        error=result.error if not result.success else None,
        model=result.model,
    )


# =============================================================================
# Profile
# =============================================================================

@app.post("/profile/ingest", tags=["Profile"])
async def ingest_profile(request: ProfileIngestRequest):
    """Parse a resume / profile and store structured data."""
    orchestrator = SmartApplyOrchestrator()
    data = await orchestrator.ingest_profile(request.resume_text)
    return {"success": "error" not in data, "data": data}


@app.post("/profile/ingest/direct", tags=["Profile"])
async def ingest_profile_direct(body: dict):
    """
    Directly ingest structured profile key-value pairs.
    Accepts any flat JSON object like {"Full Name": "...", "Email": "..."}.
    Each key-value pair is stored directly into the user_profile table.
    """
    count = 0
    for key, value in body.items():
        if isinstance(value, (dict, list)):
            import json as _json
            value = _json.dumps(value)
        set_profile(str(key), str(value))
        count += 1
    return {"success": True, "fields_stored": count}


@app.get("/profile", tags=["Profile"])
async def get_profile():
    """Return all stored profile fields."""
    return get_all_profile()


@app.post("/profile/set", tags=["Profile"])
async def set_profile_field(request: ProfileFieldRequest):
    """Manually set a profile field."""
    set_profile(request.key, request.value)
    return {"success": True, "key": request.key}


# =============================================================================
# Jobs
# =============================================================================

@app.post("/jobs/search", tags=["Jobs"])
async def search_jobs(request: JobSearchRequest):
    """Search for internship listings matching criteria."""
    orchestrator = SmartApplyOrchestrator()
    jobs = await orchestrator.search_jobs(request.criteria)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/jobs", tags=["Jobs"])
async def list_jobs(status: Optional[str] = None, limit: int = 50):
    """List discovered jobs, optionally filtered by status."""
    return get_jobs(status=status, limit=limit)


@app.post("/jobs/{job_id}/analyze", tags=["Jobs"])
async def analyze_job(job_id: int):
    """Analyze a job's application page to understand form requirements."""
    orchestrator = SmartApplyOrchestrator()
    analysis = await orchestrator.analyze_job(job_id)
    return {"success": "error" not in analysis, "analysis": analysis}


@app.post("/jobs/{job_id}/apply", tags=["Jobs"])
async def apply_to_job(job_id: int):
    """Attempt to apply to a specific job."""
    orchestrator = SmartApplyOrchestrator()
    result = await orchestrator.apply_to_job(job_id)
    return result


# =============================================================================
# Pipeline — full automation
# =============================================================================

@app.post("/pipeline/run", tags=["Pipeline"])
async def run_pipeline(request: PipelineRequest):
    """
    Run the full autonomous pipeline: search → analyze → apply.

    Set `auto_apply=true` to automatically submit applications (use carefully).
    """
    orchestrator = SmartApplyOrchestrator()
    summary = await orchestrator.run_pipeline(
        criteria=request.criteria,
        max_applications=request.max_applications,
        auto_apply=request.auto_apply,
    )
    return summary


# =============================================================================
# Memory
# =============================================================================

@app.post("/memory", tags=["Memory"])
async def store_memory(request: MemoryRequest):
    """Store a fact in agent memory."""
    remember(request.category, request.key, request.value, request.confidence)
    return {"success": True}


@app.get("/memory", tags=["Memory"])
async def get_memory(category: Optional[str] = None):
    """Recall facts from agent memory."""
    return recall(category=category)


@app.get("/memory/context", tags=["Memory"])
async def get_memory_context():
    """Get all memory formatted as context text (for debugging)."""
    return {"context": recall_as_context()}


# =============================================================================
# Sessions & Stats
# =============================================================================

@app.get("/sessions", tags=["Sessions"])
async def list_sessions(limit: int = 50):
    """List recent agent sessions."""
    from app.db.database import get_connection
    settings = get_settings()
    conn = get_connection(settings.sqlite_db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM agent_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/applications", tags=["Applications"])
async def list_applications(status: Optional[str] = None, limit: int = 50):
    """List application attempts with job info."""
    return get_applications(status=status, limit=limit)


@app.get("/stats", tags=["Dashboard"])
async def dashboard_stats():
    """Get summary statistics for jobs, applications, sessions, and memory."""
    return get_stats()


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level="info",
    )
