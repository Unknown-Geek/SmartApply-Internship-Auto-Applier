"""backend/app/api/health.py — Detailed health check endpoint."""
import os
from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.data import identity

router = APIRouter()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
CONTEXT_MODE_URL = os.getenv("CONTEXT_MODE_URL", "http://context-mode:3100")


class ServiceStatus(BaseModel):
    ok: bool
    detail: Optional[str] = None


class OllamaModelInfo(BaseModel):
    name: str
    size_gb: Optional[float] = None
    param_count: Optional[str] = None
    quantization: Optional[str] = None
    format: Optional[str] = None


class HealthResponse(BaseModel):
    status: str              # "ok" | "degraded" | "error"
    version: str = "1.0.0"
    model: str
    identity_loaded: bool
    ollama: ServiceStatus
    context_mode: ServiceStatus
    pinchtab: ServiceStatus
    model_info: Optional[OllamaModelInfo] = None


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
    model_info = None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            tags = r.json().get("models", [])
            names = [m.get("name", "") for m in tags]
            model_ready = any(LLM_MODEL.split(":")[0] in n for n in names)
            ollama_ok = r.status_code == 200
            ollama_detail = f"model {'ready' if model_ready else 'pulling/missing'}"

            # Get detailed model info (size, params, quantization)
            if model_ready:
                try:
                    show_r = await client.post(
                        f"{OLLAMA_HOST}/api/show",
                        json={"name": LLM_MODEL},
                        timeout=5,
                    )
                    if show_r.status_code == 200:
                        show_data = show_r.json()
                        details = show_data.get("details", {})
                        model_info = OllamaModelInfo(
                            name=LLM_MODEL,
                            size_gb=round(show_data.get("size", 0) / 1e9, 1) if show_data.get("size") else None,
                            param_count=details.get("parameter_size"),
                            quantization=details.get("quantization_level"),
                            format=details.get("format"),
                        )
                except Exception:
                    pass
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
        model_info=model_info,
    )


@router.get("/ollama/stats")
async def ollama_stats():
    """Live Ollama server stats — loaded models, VRAM, and generation metrics."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            tags = r.json().get("models", [])

            # Get running models (loaded in VRAM) from /api/ps
            ps_r = await client.get(f"{OLLAMA_HOST}/api/ps", timeout=3)
            running = []
            if ps_r.status_code == 200:
                for m in ps_r.json().get("models", []):
                    running.append({
                        "name": m.get("name"),
                        "size_gb": round(m.get("size", 0) / 1e9, 1) if m.get("size") else None,
                        "vram_gb": round(m.get("size_vram", 0) / 1e9, 1) if m.get("size_vram") else None,
                        "expires_at": m.get("expires_at"),
                    })

            return {
                "model": LLM_MODEL,
                "models_available": [m.get("name") for m in tags],
                "running": running,
                "server": "online",
            }
    except Exception as e:
        return {"server": "offline", "error": str(e)[:100]}
