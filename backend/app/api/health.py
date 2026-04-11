"""backend/app/api/health.py — Detailed health check endpoint."""
import os
from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.data import identity

router = APIRouter()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")
CONTEXT_MODE_URL = os.getenv("CONTEXT_MODE_URL", "http://context-mode:3100")


class ServiceStatus(BaseModel):
    ok: bool
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str              # "ok" | "degraded" | "error"
    version: str = "1.0.0"
    model: str
    identity_loaded: bool
    ollama: ServiceStatus
    context_mode: ServiceStatus
    pinchtab: ServiceStatus


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Deep health check — tests connectivity to Ollama, context-mode, and PinchTab.
    Returns 200 even when degraded, so the UI can show partial status.
    """
    import subprocess

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_ok = False
    ollama_detail = None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            tags = r.json().get("models", [])
            names = [m.get("name", "") for m in tags]
            model_ready = any(LLM_MODEL.split(":")[0] in n for n in names)
            ollama_ok = r.status_code == 200
            ollama_detail = f"model {'ready' if model_ready else 'pulling/missing'}"
    except Exception as e:
        ollama_detail = str(e)[:80]

    # ── context-mode ──────────────────────────────────────────────────────────
    ctx_ok = False
    ctx_detail = None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{CONTEXT_MODE_URL}/health", timeout=3)
            ctx_ok = r.status_code == 200
            ctx_detail = r.json().get("db", "")
    except Exception as e:
        ctx_detail = str(e)[:80]

    # ── PinchTab (check if process running) ───────────────────────────────────
    pinch_ok = False
    pinch_detail = None
    try:
        result = subprocess.run(["pinchtab", "--version"], capture_output=True, text=True, timeout=3)
        pinch_ok = result.returncode == 0
        pinch_detail = result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        pinch_detail = "not installed"
    except Exception as e:
        pinch_detail = str(e)[:80]

    # ── Overall status ────────────────────────────────────────────────────────
    all_ok = ollama_ok and ctx_ok
    status = "ok" if all_ok else ("degraded" if ollama_ok else "error")

    return HealthResponse(
        status=status,
        model=LLM_MODEL,
        identity_loaded=identity._identity is not None,
        ollama=ServiceStatus(ok=ollama_ok, detail=ollama_detail),
        context_mode=ServiceStatus(ok=ctx_ok, detail=ctx_detail),
        pinchtab=ServiceStatus(ok=pinch_ok, detail=pinch_detail),
    )
