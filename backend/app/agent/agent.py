"""
backend/app/agent/agent.py
smolagents CodeAgent initialization with qwen2.5-coder:7b via Ollama.
"""
import os
import asyncio
import logging
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


def _make_model() -> LiteLLMModel:
    """Create a LiteLLM model pointing to local Ollama."""
    return LiteLLMModel(
        model_id=f"ollama/{LLM_MODEL}",
        api_base=OLLAMA_HOST,
        num_ctx=LLM_CONTEXT_SIZE,
        temperature=LLM_TEMPERATURE,
    )


async def warmup_agent() -> bool:
    """
    Quick connectivity check to verify Ollama is reachable.
    Called at startup; non-blocking.
    """
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
            tags = r.json().get("models", [])
            names = [m.get("name", "") for m in tags]
            if not any(LLM_MODEL in n for n in names):
                logger.warning(
                    f"⚠️  Model '{LLM_MODEL}' not yet pulled. "
                    "It will be pulled by the Ollama entrypoint script."
                )
            return True
    except Exception as e:
        raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}")


def run_agent(
    job_url: str,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> str:
    """
    Run the CodeAgent to apply to a job.

    Args:
        job_url: The job application URL.
        log_callback: Optional callback(level, message) for live streaming.

    Returns:
        Final result string ("SUCCESS", "BLOCKED", or error message).
    """
    model = _make_model()

    try:
        identity_text = get_identity_text()
    except Exception as e:
        identity_text = "No identity data loaded."
        logger.warning(f"Could not load identity: {e}")

    system_prompt = build_prompt(identity_text=identity_text, max_steps=AGENT_MAX_STEPS)

    # Custom logger that forwards to log_callback
    class CallbackLogger:
        def log(self, message: str):
            if log_callback:
                log_callback("info", message)

    agent = CodeAgent(
        tools=[scrape_jd, navigate, get_ui_elements, act_on_ui, ctx_search],
        model=model,
        max_steps=AGENT_MAX_STEPS,
        additional_authorized_imports=["json", "re", "time", "os"],
        system_prompt=system_prompt,
        verbosity_level=2,
    )

    task = (
        f"Apply for the job at: {job_url}\n\n"
        f"Use the scrape_jd tool first, then navigate to the application URL and complete the form.\n"
        f"Stop when you see a submission confirmation or after {AGENT_MAX_STEPS} steps."
    )

    try:
        result = agent.run(task)
        return str(result)
    except Exception as e:
        logger.error(f"Agent run failed: {e}")
        raise
