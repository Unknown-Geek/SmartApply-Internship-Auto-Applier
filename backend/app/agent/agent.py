"""
backend/app/agent/agent.py
smolagents CodeAgent initialization with qwen2.5-coder:7b via Ollama.
Includes retry logic and structured error recovery.
"""
import os
import asyncio
import logging
import time
from typing import Callable, Optional
import httpx
from smolagents import CodeAgent, LiteLLMModel

from app.agent.tools import scrape_jd, navigate, get_ui_elements, act_on_ui, ctx_search
from app.agent.prompt import build_prompt
from app.data.identity import get_identity_text

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")
LLM_CONTEXT_SIZE = int(os.getenv("LLM_CONTEXT_SIZE", "8192"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "20"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))

# Max times to retry the full agent run on transient failures
MAX_RUN_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5


def _make_model() -> LiteLLMModel:
    """Create a LiteLLM model pointing to local Ollama."""
    return LiteLLMModel(
        model_id=f"ollama/{LLM_MODEL}",
        api_base=OLLAMA_HOST,
        num_ctx=LLM_CONTEXT_SIZE,
        temperature=LLM_TEMPERATURE,
        # Structured output for reliable tool calling
        response_format=None,
    )


async def warmup_agent() -> bool:
    """
    Quick connectivity check to verify Ollama is reachable and model is available.
    Called at startup; non-blocking.
    """
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
            r.raise_for_status()
            tags = r.json().get("models", [])
            names = [m.get("name", "") for m in tags]
            if not any(LLM_MODEL.split(":")[0] in n for n in names):
                logger.warning(
                    f"⚠️  Model '{LLM_MODEL}' not yet pulled. "
                    "Ollama entrypoint should pull it automatically."
                )
            else:
                logger.info(f"✅ Model '{LLM_MODEL}' confirmed available.")
            return True
    except Exception as e:
        raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}")


def run_agent(
    job_url: str,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> str:
    """
    Run the CodeAgent to apply to a job.

    Retries up to MAX_RUN_RETRIES times on transient errors (network, timeout).
    Raises on permanent errors (bad URL, identity missing, etc.).

    Args:
        job_url: The job application URL.
        log_callback: Optional callback(level, message) for live streaming.

    Returns:
        Final result string ("SUCCESS", "BLOCKED", or last agent output).
    """
    def _log(level: str, msg: str):
        logger.info(f"[{level.upper()}] {msg}")
        if log_callback:
            log_callback(level, msg)

    model = _make_model()

    try:
        identity_text = get_identity_text()
        _log("info", f"📋 Identity loaded — {len(identity_text.splitlines())} fields")
    except Exception as e:
        identity_text = "No identity data available. Proceed with empty fields."
        _log("error", f"⚠️  Identity load failed: {e} — proceeding without identity")

    system_prompt = build_prompt(identity_text=identity_text, max_steps=AGENT_MAX_STEPS)

    task = (
        f"Apply for the job at: {job_url}\n\n"
        "Steps:\n"
        "1. Call scrape_jd() to understand the role.\n"
        "2. Call navigate() to open the application URL.\n"
        "3. Loop: get_ui_elements() → match fields to Identity Data → act_on_ui().\n"
        "4. If DOM is large, use ctx_search() instead of reading raw output.\n"
        f"5. Stop when you see a submission confirmation or after {AGENT_MAX_STEPS} steps.\n"
        "Report SUCCESS or BLOCKED at the end."
    )

    last_error = None
    for attempt in range(1, MAX_RUN_RETRIES + 1):
        if attempt > 1:
            delay = RETRY_BACKOFF_SECONDS * attempt
            _log("info", f"🔄 Retry {attempt}/{MAX_RUN_RETRIES} in {delay}s…")
            time.sleep(delay)

        try:
            _log("info", f"🤖 Agent run starting (attempt {attempt}/{MAX_RUN_RETRIES})")

            agent = CodeAgent(
                tools=[scrape_jd, navigate, get_ui_elements, act_on_ui, ctx_search],
                model=model,
                max_steps=AGENT_MAX_STEPS,
                additional_authorized_imports=["json", "re", "time", "os"],
                system_prompt=system_prompt,
                verbosity_level=1,
            )

            result = agent.run(task)
            result_str = str(result)

            _log("info", f"✅ Agent finished: {result_str[:200]}")
            return result_str

        except Exception as e:
            last_error = e
            err_str = str(e)

            # Classify error for smarter retry decisions
            is_transient = any(kw in err_str.lower() for kw in [
                "timeout", "connection", "refused", "network", "temporarily"
            ])
            is_permanent = any(kw in err_str.lower() for kw in [
                "invalid url", "404", "403", "not found"
            ])

            if is_permanent:
                _log("error", f"❌ Permanent error (no retry): {e}")
                raise

            _log("error", f"⚠️  Transient error (attempt {attempt}): {e}")

            if attempt == MAX_RUN_RETRIES:
                break

    raise RuntimeError(
        f"Agent failed after {MAX_RUN_RETRIES} attempts. Last error: {last_error}"
    )
