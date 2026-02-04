import os
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from mcp.server.fastmcp import FastMCP


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


API_BEARER_TOKEN = _require_env("API_BEARER_TOKEN")
MCP_BASE_PATH = "/mcp"
PUBLIC_PATHS = {"/healthz"}


# CRITICAL: prevents 307 /mcp -> /mcp/ redirects (including POST)
app = FastAPI(redirect_slashes=False)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    path = request.url.path

    # Unauthed health checks
    if path in PUBLIC_PATHS:
        return await call_next(request)

    # MCP paths: accept both /mcp and /mcp/... (including /mcp/)
    if path == MCP_BASE_PATH or path.startswith(MCP_BASE_PATH + "/"):
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return JSONResponse({"error": "missing_bearer_token"}, status_code=401)
        token = auth.split(" ", 1)[1].strip()
        if token != API_BEARER_TOKEN:
            return JSONResponse({"error": "invalid_bearer_token"}, status_code=401)
        return await call_next(request)

    # Everything else protected too (defense-in-depth)
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return JSONResponse({"error": "missing_bearer_token"}, status_code=401)
    token = auth.split(" ", 1)[1].strip()
    if token != API_BEARER_TOKEN:
        return JSONResponse({"error": "invalid_bearer_token"}, status_code=401)
    return await call_next(request)


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---- MCP server wiring ----
mcp = FastMCP(name="Meta Ads MCP (Cloud Run, Read-Only)")

# Keep your existing tool registration approach.
# (Adjust this import to match your repo if needed.)
try:
    from meta_ads_mcp_cloudrun.tools.register import register_read_tools  # type: ignore
    register_read_tools(mcp)
except Exception:
    # If your repo registers tools elsewhere, keep your existing imports/registration.
    pass


def _get_mcp_asgi_app(mcp_obj: Any):
    """
    Compatibility shim for different MCP Python SDK versions.

    Known variants across releases:
      - FastMCP.get_asgi_app()
      - FastMCP.asgi_app()
      - FastMCP.app   (property)
    """
    if hasattr(mcp_obj, "get_asgi_app") and callable(getattr(mcp_obj, "get_asgi_app")):
        return mcp_obj.get_asgi_app()

    if hasattr(mcp_obj, "asgi_app") and callable(getattr(mcp_obj, "asgi_app")):
        return mcp_obj.asgi_app()

    if hasattr(mcp_obj, "app"):
        return getattr(mcp_obj, "app")

    raise RuntimeError(
        "Unable to expose MCP as ASGI app. "
        "Your installed mcp.server.fastmcp.FastMCP does not provide get_asgi_app/asgi_app/app. "
        "Pin/upgrade the MCP Python SDK or update wiring accordingly."
    )


mcp_app = _get_mcp_asgi_app(mcp)

# Mount at /mcp (and no redirect due to redirect_slashes=False)
app.mount(MCP_BASE_PATH, mcp_app)


def main():
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(
        "meta_ads_mcp_cloudrun.main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()