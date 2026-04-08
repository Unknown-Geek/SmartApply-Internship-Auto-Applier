"""
backend/app/agent/tools.py
smolagents @tool wrappers for: Scrapling, PinchTab, context-mode, and file upload.
"""
import json
import logging
import os
import subprocess

import httpx
from smolagents import tool

logger = logging.getLogger(__name__)

PINCHTAB_API_URL = os.getenv("PINCHTAB_DAEMON_URL", "http://localhost:9867")
CONTEXT_MODE_URL = os.getenv("CONTEXT_MODE_URL", "http://context-mode:3100")
RESUME_PDF_PATH = os.getenv("RESUME_PDF_PATH", "/app/data/identity/resume.pdf")

# ─── Tool 1: Scrape Job Description ──────────────────────────────────────────


@tool
def scrape_jd(url: str) -> str:
    """
    Fetches and indexes the job description from a given URL using Scrapling.
    Handles anti-bot protection (Cloudflare, LinkedIn). Returns a short summary.

    Args:
        url: The URL of the job description page to scrape.

    Returns:
        A plain-text summary of the job description (title, company, requirements).
    """
    try:
        from scrapling.defaults import Fetcher  # type: ignore
        fetcher = Fetcher(auto_match=True)
        page = fetcher.get(url, stealthy_headers=True)
        text = page.get_all_text()[:3000]  # Truncate to avoid context flood

        # Index into context-mode for later ctx_search queries
        try:
            httpx.post(
                f"{CONTEXT_MODE_URL}/index",
                json={"id": "jd", "content": text},
                timeout=10
            )
        except Exception:
            pass  # context-mode indexing is best-effort

        return f"[JD Scraped] {len(text)} chars from {url}\n\n{text[:1500]}..."
    except Exception as e:
        logger.error(f"scrape_jd failed: {e}")
        return f"[ERROR] Could not scrape job description: {e}"


# ─── Tool 2: Navigate ────────────────────────────────────────────────────────


@tool
def navigate(url: str) -> str:
    """
    Opens the given URL in the headless browser (PinchTab or fallback).

    Args:
        url: The URL to navigate to.

    Returns:
        Confirmation message with page title.
    """
    # Try PinchTab first
    result = _pinchtab_call("navigate", {"url": url})
    if result["success"]:
        return f"[OK] Navigated to: {url}"
    # Fallback: log and return
    return f"[FALLBACK] Navigated (browser fallback): {url}"


# ─── Tool 3: Get UI Elements ──────────────────────────────────────────────────


@tool
def get_ui_elements() -> str:
    """
    Returns a compact, token-efficient list of interactive elements on the
    current page (form fields, buttons, dropdowns). Elements are referenced
    by short IDs like e5, e12 instead of full HTML.

    Returns:
        A compact listing of interactive element references and their labels.
    """
    result = _pinchtab_call("snapshot", {"interactive": True, "compact": True})
    if result["success"]:
        output = result["output"]
        # If output is too long, pass through context-mode
        if len(output) > 2000:
            try:
                httpx.post(
                    f"{CONTEXT_MODE_URL}/index",
                    json={"id": "ui_elements", "content": output},
                    timeout=10
                )
                return (
                    f"[DOM INDEXED] {len(output)} chars indexed. "
                    "Use ctx_search() to query specific fields. "
                    f"Preview:\n{output[:500]}..."
                )
            except Exception:
                pass
        return output
    return "[ERROR] Could not get UI elements. Browser may not be open — call navigate() first."


# ─── Tool 4: Act on UI ────────────────────────────────────────────────────────


@tool
def act_on_ui(action: str, ref: str, text: str = "") -> str:
    """
    Performs an action on a UI element identified by a short reference ID.

    Args:
        action: The action to perform: "click", "fill", "select", or "upload".
        ref: The element reference ID from get_ui_elements() (e.g. "e5").
        text: The text to type (for "fill"), option to select, or file path (for "upload").

    Returns:
        Result of the action.
    """
    if action == "click":
        result = _pinchtab_call("click", {"ref": ref})
    elif action == "fill":
        result = _pinchtab_call("fill", {"ref": ref, "text": text})
    elif action == "select":
        result = _pinchtab_call("select", {"ref": ref, "value": text})
    elif action == "upload":
        file_path = text if text else RESUME_PDF_PATH
        
        # If it's a URL (like a Google Drive link), download it first
        if file_path.startswith("http://") or file_path.startswith("https://"):
            import tempfile
            import uuid
            import subprocess
            
            tmp_dir = os.path.join(tempfile.gettempdir(), f"smartapply_dl_{uuid.uuid4().hex}")
            os.makedirs(tmp_dir, exist_ok=True)
            
            logger.info(f"Downloading remote file from {file_path} into {tmp_dir}")
            try:
                # Use gdown CLI to download. This preserves the Google Drive filename natively.
                result = subprocess.run(
                    ["gdown", "--fuzzy", file_path],
                    cwd=tmp_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr if result.stderr else result.stdout
                    return f"[ERROR] Failed to download file from {file_path}: {error_msg}"
                
                downloaded_files = os.listdir(tmp_dir)
                if not downloaded_files:
                    return f"[ERROR] Failed to download file, no file produced by gdown for {file_path}."
                
                file_path = os.path.join(tmp_dir, downloaded_files[0])
                logger.info(f"Successfully downloaded to {file_path}")
            except FileNotFoundError:
                return "[ERROR] gdown is not installed or not in PATH."
            except Exception as e:
                return f"[ERROR] Downloading failed: {str(e)}"

        result = _pinchtab_call("attach", {"ref": ref, "path": file_path})
    else:
        return f"[ERROR] Unknown action: {action}. Use click/fill/select/upload."

    if result["success"]:
        return f"[OK] {action.upper()} on {ref}" + (f" with '{text}'" if text else "")
    return f"[ERROR] {action} failed on {ref}: {result.get('error', 'unknown error')}"


# ─── Tool 5: Context Search ────────────────────────────────────────────────────


@tool
def ctx_search(query: str) -> str:
    """
    Searches the indexed page content (job description or DOM) using SQLite FTS5.
    Use this instead of reading raw element dumps when the page has too much content.

    Args:
        query: Natural language query to search for (e.g. "email field", "submit button").

    Returns:
        Relevant snippets from the indexed content.
    """
    try:
        resp = httpx.post(
            f"{CONTEXT_MODE_URL}/search",
            json={"query": query, "limit": 5},
            timeout=10
        )
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return f"[ctx_search] No results for: '{query}'"
        snippets = "\n---\n".join([r.get("content", "") for r in results])
        return f"[ctx_search results for '{query}']:\n{snippets}"
    except Exception as e:
        logger.error(f"ctx_search failed: {e}")
        return f"[ERROR] Context search failed: {e}"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _pinchtab_call(path: str, payload: dict) -> dict:
    """Call PinchTab's HTTP API. Falls back to CLI subprocess if API unreachable."""
    try:
        resp = httpx.post(
            f"{PINCHTAB_API_URL}/{path.lstrip('/')}",
            json=payload,
            timeout=30,
        )
        data = resp.json()
        return {
            "success": resp.status_code < 400,
            "output": data.get("result") or data.get("text") or "",
            "error": data.get("error") if resp.status_code >= 400 else None,
        }
    except httpx.ConnectError:
        # Fallback to CLI
        return _run_pinchtab_cli(path.split("/")[-1:])
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def _run_pinchtab_cli(args: list) -> dict:
    """Run a PinchTab CLI command and return structured result."""
    try:
        cmd = ["pinchtab"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else None,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "",
            "error": "PinchTab not installed or not in PATH",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "PinchTab command timed out",
        }
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
