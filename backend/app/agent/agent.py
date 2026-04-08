import asyncio
import logging
import os
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Callable, Optional

import httpx
from browser_use import Agent, Browser, Controller, ChatOllama

from app.data.identity import get_identity_text

logger = logging.getLogger(__name__)

# Thread-local storage so the module-level controller can call the
# per-task user_input_fn without any shared mutable global state.
_run_ctx = threading.local()

controller = Controller()


@controller.action(
    'Ask the human operator for information that is missing or unknown. '
    'Use this when you encounter a login form, a field you cannot fill from '
    'identity data, an OTP prompt, or any security challenge. '
    'Blocks until the human replies via Telegram.'
)
def ask_user(question: str) -> str:
    """
    Pause the agent and ask the human operator for input.

    Args:
        question: The exact question to ask (e.g. "What is your LinkedIn password?").

    Returns:
        The human\'s answer as a plain string.
    """
    fn: Optional[Callable[[str], str]] = getattr(_run_ctx, 'user_input_fn', None)
    if fn is None:
        return "[SKIPPED] No user-input handler configured for this run."
    return fn(question)

@controller.action('Download a file from a Google Drive URL to the local disk. Returns the absolute file path which you can then use for file inputs.')
def download_file_from_drive(gdrive_url: str) -> str:
    tmp_dir = os.path.join(tempfile.gettempdir(), f"smartapply_dl_{uuid.uuid4().hex}")
    os.makedirs(tmp_dir, exist_ok=True)
    logger.info(f"Downloading remote file from {gdrive_url} into {tmp_dir}")
    try:
        result = subprocess.run(["gdown", "--fuzzy", gdrive_url], cwd=tmp_dir, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return f"Failed to download: {result.stderr}"
        downloaded_files = os.listdir(tmp_dir)
        if not downloaded_files:
            return "Failed to download: no file produced."
        return os.path.join(tmp_dir, downloaded_files[0])
    except Exception as e:
        return f"Download failed: {str(e)}"


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")
LLM_CONTEXT_SIZE = int(os.getenv("LLM_CONTEXT_SIZE", "8192"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "20"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))

# Max times to retry the full agent run on transient failures
MAX_RUN_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5


def _make_model() -> ChatOllama:
    """Create a LangChain ChatOllama model pointing to local Ollama."""
    return ChatOllama(
        model=LLM_MODEL,
        host=OLLAMA_HOST,
        ollama_options={
            "temperature": LLM_TEMPERATURE,
            "num_ctx": LLM_CONTEXT_SIZE
        }
    )


async def warmup_agent() -> bool:
    """
    Quick connectivity check to verify Ollama is reachable and model is available.
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
    user_input_fn: Optional[Callable[[str], str]] = None,
) -> str:
    """
    Run the browser-use Agent to apply to a job.

    Args:
        job_url:        The job application URL.
        log_callback:   Optional callback(level, message) for live streaming.
        user_input_fn:  Optional callback(question) -> answer for human-in-the-loop.
                        When provided, the agent may call ask_user() and block
                        until the operator supplies an answer.

    Returns:
        Final result string.
    """
    def _log(level: str, msg: str):
        logger.info(f"[{level.upper()}] {msg}")
        if log_callback:
            log_callback(level, msg)

    # Inject per-run user_input_fn into thread-local so ask_user() can reach it
    _run_ctx.user_input_fn = user_input_fn

    model = _make_model()

    try:
        identity_text = get_identity_text()
        _log("info", f"📋 Identity loaded — {len(identity_text.splitlines())} fields")
    except Exception as e:
        identity_text = "No identity data available. Proceed with empty fields."
        _log("error", f"⚠️  Identity load failed: {e} — proceeding without identity")

    task = (
        f"Apply for the job at: {job_url}\n\n"
        "Here is your applicant identity data. Use this strictly when filling out forms on the application page:\n"
        f"{identity_text}\n\n"
        "Steps:\n"
        "1. Open the job application URL.\n"
        "2. Parse requirements and match available identity data to HTML forms iteratively.\n"
        "3. Use standard input/click interactions natively to fill details.\n"
        "4. Stop when you see the final submission confirmation screen and have successfully applied."
    )

    if "myworkdayjobs.com" in job_url.lower():
        _log("info", "🚀 Routing complex Workday URL to Agent-E native handler.")
        # NOTE: Agent-E integration stub
        # We import Agent-E logic dynamically here to handle the workday flow
        try:
            # from agent_e.agent import WebAgent
            # agent_e = WebAgent(...)
            return "[AGENT-E STUB] Workday URL handled by EmergentAGI."
        except Exception as e:
            _log("error", f"Agent-E failed to initialize: {e}")
            # Fallback to browser-use below

    last_error = None
    for attempt in range(1, MAX_RUN_RETRIES + 1):
        if attempt > 1:
            delay = RETRY_BACKOFF_SECONDS * attempt
            _log("info", f"🔄 Retry {attempt}/{MAX_RUN_RETRIES} in {delay}s…")
            time.sleep(delay)

        try:
            _log("info", f"🤖 Browser-use Agent run starting (attempt {attempt}/{MAX_RUN_RETRIES})")

            # Setup headless browser natively for the agent inside Docker
            browser = Browser(headless=True)
            agent = Agent(
                task=task,
                llm=model,
                browser=browser,
                controller=controller
            )

            # Run event loop to wrap the async browser-use api
            result = asyncio.run(agent.run(max_steps=AGENT_MAX_STEPS))
            result_str = str(result)

            _log("info", f"✅ Agent finished: {result_str[:200]}")

            # Ensure cleanup
            if hasattr(browser, "stop"):
                asyncio.run(browser.stop())
            elif hasattr(browser, "close"):
                asyncio.run(browser.close())

            return result_str

        except Exception as e:
            last_error = e
            err_str = str(e)

            is_permanent = any(kw in err_str.lower() for kw in [
                "invalid url", "404", "403", "not found"
            ])

            if is_permanent:
                _log("error", f"❌ Permanent error (no retry): {e}")
                raise

            _log("error", f"⚠️  Transient error (attempt {attempt}): {e}")

            if attempt == MAX_RUN_RETRIES:
                _log("warning", "🚨 Browser-use exhausted. Offloading to Skyvern Fallback Engine.")
                try:
                    # Invoke Skyvern as a last resort via its API
                    skyvern_payload = {
                        "url": job_url,
                        "task": task,
                    }
                    resp = httpx.post("http://skyvern:8080/api/v1/workflow", json=skyvern_payload, timeout=20)
                    resp.raise_for_status()
                    return f"[SKYVERN FALLBACK] Task delegated to Skyvern: {resp.json()}"
                except Exception as sky_e:
                    _log("error", f"Skyvern fallback also failed: {sky_e}")
                break

    raise RuntimeError(
        f"Agent failed after {MAX_RUN_RETRIES} attempts. Last error: {last_error}"
    )
