"""
backend/app/core/auth.py
Simple API key authentication middleware.

Set API_KEYS env var to a comma-separated list of keys.
If API_KEYS is empty or not set, auth is disabled (all requests allowed).
Keys can be passed via:
  - Query param: ?api_key=KEY
  - Header: X-API-Key: KEY
  - Header: Authorization: Bearer KEY
"""
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

# Parse comma-separated keys at import time
_VALID_KEYS: set[str] = set()
_raw = settings.api_keys or os.getenv("API_KEYS", "")
if _raw:
    _VALID_KEYS = {k.strip() for k in _raw.split(",") if k.strip()}

# Paths that never require auth
_PUBLIC_PREFIXES = ("/api/health",)


def _extract_key(request: Request) -> str | None:
    """Extract API key from query param or headers."""
    # Query param
    key = request.query_params.get("api_key")
    if key:
        return key

    # X-API-Key header
    key = request.headers.get("x-api-key")
    if key:
        return key

    # Authorization: Bearer <key>
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return None


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid API key (when API_KEYS is configured)."""

    async def dispatch(self, request: Request, call_next):
        # Auth disabled — no keys configured
        if not _VALID_KEYS:
            return await call_next(request)

        # Public paths
        path = request.url.path
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # WebSocket upgrade — skip (auth handled in ws route if needed)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Check key
        key = _extract_key(request)
        if key is None or key not in _VALID_KEYS:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Pass via api_key query param, X-API-Key header, or Authorization: Bearer <key>"},
            )

        return await call_next(request)
