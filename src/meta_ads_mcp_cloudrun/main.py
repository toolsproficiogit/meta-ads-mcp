from __future__ import annotations

import os

from fastapi import FastAPI
from mcp.server import FastMCP

from .auth import BearerAuthMiddleware
from .config import Settings
from .tools.read_tools import register_read_tools


settings = Settings.from_env()

mcp = FastMCP(
    "Meta Ads MCP (read-only)",
)

# Register tools
register_read_tools(mcp, settings)

# Create the Streamable HTTP app for MCP.
# The MCP SDK mounts the endpoint under /mcp (as per spec defaults).
mcp_app = mcp.streamable_http_app()

# Wrap to add auth middleware and a basic health endpoint.
app = FastAPI(title="Meta Ads MCP (Cloud Run)")

# Health endpoint (not part of MCP)
@app.get("/healthz")
def healthz():
    return {"ok": True}

# Mount the MCP app under /mcp (same path n8n expects for streamable-http servers).
app.mount("/mcp", mcp_app)

# Bearer auth for everything (including /mcp)
app.add_middleware(BearerAuthMiddleware, expected_token=settings.api_bearer_token)

# Cloud Run sets PORT
PORT = int(os.getenv("PORT", "8080"))
