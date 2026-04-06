"""backend/app/api/health.py — Health check endpoint."""
import os
import httpx
from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.data.identity import _identity

router = APIRouter()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check connectivity to Ollama and identity status."""
    ollama_ok = False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return HealthResponse(
        status="ok" if ollama_ok else "degraded",
        ollama=ollama_ok,
        model=LLM_MODEL,
        identity_loaded=_identity is not None,
    )
