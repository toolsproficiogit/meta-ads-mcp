from __future__ import annotations

from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Simple Bearer auth for MCP clients (n8n, etc).

    - If API_BEARER_TOKEN is not set, auth is disabled (useful for local dev).
    - Checks Authorization: Bearer <token>
    """

    def __init__(self, app, expected_token: Optional[str]) -> None:
        super().__init__(app)
        self.expected_token = expected_token

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if not self.expected_token:
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        prefix = "bearer "
        if not auth.lower().startswith(prefix):
            return JSONResponse({"error": "missing_bearer_token"}, status_code=401)

        token = auth[len(prefix):].strip()
        if token != self.expected_token:
            return JSONResponse({"error": "invalid_bearer_token"}, status_code=401)

        return await call_next(request)
