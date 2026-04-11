"""
backend/app/main.py
FastAPI application entrypoint with lifespan, CORS, and router registration.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.agent import warmup_agent
from app.api import health, identity, jobs, ws
from app.data.identity import load_identity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("🚀 Smart Apply backend starting up...")
    # Load applicant identity CSV into memory
    try:
        load_identity()
        logger.info("✅ Identity data loaded.")
    except FileNotFoundError as e:
        logger.warning(f"⚠️  Identity CSV not found: {e} — upload it via /api/identity")

    # Optionally warm up the LLM connection (non-blocking)
    try:
        await warmup_agent()
        logger.info("✅ Ollama connection verified.")
    except Exception as e:
        logger.warning(f"⚠️  Ollama warmup failed: {e} — will retry on first job")

    yield

    logger.info("🛑 Smart Apply backend shutting down.")


app = FastAPI(
    title="Smart Apply API",
    description="Autonomous job application agent powered by qwen3:8b",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(identity.router, prefix="/api", tags=["Identity"])
app.include_router(ws.router, tags=["WebSocket"])
