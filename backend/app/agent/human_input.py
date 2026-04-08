"""
backend/app/agent/human_input.py

Thread-safe pause-and-resume for mid-run human input.

The agent thread calls request_input(task_id, question) which blocks until:
  - provide_answer(task_id, answer) is called from the API (happy path), or
  - the timeout elapses (returns a TIMEOUT marker string).

All state lives in a single in-process dict — no Redis required.
"""
import threading
from typing import Optional

# task_id -> {"question": str, "event": threading.Event, "answer": str | None}
_pending: dict[str, dict] = {}
_lock = threading.Lock()

# How long (seconds) to wait for a human reply before giving up
DEFAULT_TIMEOUT = int(300)  # 5 minutes


def request_input(task_id: str, question: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Block the calling (agent) thread and wait for a human answer.

    Args:
        task_id:  The task that is pausing.
        question: The question to present to the human.
        timeout:  Max seconds to wait (default 5 min).

    Returns:
        The human's answer string, or a timeout/error marker.
    """
    event = threading.Event()
    with _lock:
        _pending[task_id] = {"question": question, "event": event, "answer": None}

    fired = event.wait(timeout=timeout)

    with _lock:
        slot = _pending.pop(task_id, None)

    if not fired or slot is None or slot["answer"] is None:
        return f"[TIMEOUT] No answer received for '{question}' within {timeout}s. Skipping."

    return slot["answer"]


def provide_answer(task_id: str, answer: str) -> bool:
    """
    Unblock a waiting agent thread by supplying the human's answer.

    Args:
        task_id: The task to resume.
        answer:  The human's reply.

    Returns:
        True if the task was found and unblocked, False if not waiting.
    """
    with _lock:
        slot = _pending.get(task_id)
        if slot is None:
            return False
        slot["answer"] = answer
        slot["event"].set()
    return True


def get_pending_question(task_id: str) -> Optional[str]:
    """Return the pending question for a task, or None if not waiting."""
    with _lock:
        slot = _pending.get(task_id)
        return slot["question"] if slot else None


def list_waiting() -> list[dict]:
    """Return all tasks currently waiting for human input."""
    with _lock:
        return [
            {"task_id": tid, "question": s["question"]}
            for tid, s in _pending.items()
        ]
