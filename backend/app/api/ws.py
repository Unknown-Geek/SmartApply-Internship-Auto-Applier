"""
backend/app/api/ws.py
WebSocket endpoint for live streaming of agent logs.
"""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.jobs import _tasks, _get_task

router = APIRouter()


def _serialize_log(log: dict) -> dict:
    ts = log.get("timestamp")
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    return {
        "type": "log",
        "timestamp": ts or datetime.utcnow().isoformat(),
        "level": log.get("level", "info"),
        "message": log.get("message", ""),
        "step": log.get("step"),
    }


@router.websocket("/ws/agent/{task_id}")
async def agent_logs_ws(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint that streams live agent logs to the frontend.
    Sends existing logs immediately, then polls every second for new ones.
    Closes automatically when task reaches COMPLETED or FAILED.
    """
    await websocket.accept()

    # Validate task exists (loads from disk if needed)
    try:
        _get_task(task_id)
    except Exception:
        await websocket.send_text(json.dumps({"type": "error", "error": f"Task {task_id} not found"}))
        await websocket.close()
        return

    sent_count = 0
    TERMINAL_STATES = {"completed", "failed"}

    try:
        while True:
            task = _tasks.get(task_id, {})
            logs = task.get("logs", [])
            status = task.get("status", "pending")

            # Send any new log entries
            new_logs = logs[sent_count:]
            for log in new_logs:
                await websocket.send_text(json.dumps(_serialize_log(log)))
                sent_count += 1

            # Always send a status heartbeat
            await websocket.send_text(json.dumps({
                "type": "status",
                "status": status,
                "step": sent_count,
                "timestamp": datetime.utcnow().isoformat(),
            }))

            # If terminal state, send final summary and close
            if status in TERMINAL_STATES:
                await websocket.send_text(json.dumps({
                    "type": "done",
                    "status": status,
                    "result": task.get("result"),
                    "error": task.get("error"),
                }))
                break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
