"""
backend/app/api/ws.py
WebSocket endpoint for live streaming of agent logs.
"""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.jobs import _tasks

router = APIRouter()


def _serialize_log(log) -> dict:
    return {
        "timestamp": log.timestamp.isoformat(),
        "level": log.level,
        "message": log.message,
        "step": log.step,
    }


@router.websocket("/ws/agent/{task_id}")
async def agent_logs_ws(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint that streams live agent logs to the frontend.
    Sends existing logs immediately, then polls for new ones.
    Closes when task reaches COMPLETED or FAILED state.
    """
    await websocket.accept()

    if task_id not in _tasks:
        await websocket.send_text(json.dumps({
            "error": f"Task {task_id} not found"
        }))
        await websocket.close()
        return

    sent_count = 0

    try:
        while True:
            task = _tasks.get(task_id)
            if not task:
                break

            logs = task.get("logs", [])
            new_logs = logs[sent_count:]

            for log in new_logs:
                await websocket.send_text(json.dumps(_serialize_log(log)))
                sent_count += 1

            # Send status update
            status = task.get("status")
            await websocket.send_text(json.dumps({
                "type": "status",
                "status": status.value if hasattr(status, "value") else str(status),
                "timestamp": datetime.utcnow().isoformat(),
            }))

            if status in ("completed", "failed") or (
                hasattr(status, "value") and status.value in ("completed", "failed")
            ):
                # Final result
                await websocket.send_text(json.dumps({
                    "type": "done",
                    "result": task.get("result"),
                    "error": task.get("error"),
                }))
                break

            await asyncio.sleep(1)  # Poll every second

    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
