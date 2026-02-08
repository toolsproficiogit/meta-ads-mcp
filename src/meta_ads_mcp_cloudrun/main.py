import contextlib
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from mcp.server.fastmcp import FastMCP

from meta_ads_mcp_cloudrun.config import Settings

# -----------------------------
# Env / config
# -----------------------------

SETTINGS = Settings.from_env()
API_BEARER_TOKEN = SETTINGS.api_bearer_token
MCP_BASE_PATH = "/mcp"
PUBLIC_PATHS = {"/healthz"}


# -----------------------------
# FastAPI app
# -----------------------------
# IMPORTANT: prevents Starlette/FastAPI from issuing 307 redirects for /mcp -> /mcp/
# (including for POST), which breaks MCP clients like n8n.
app = FastAPI(redirect_slashes=False)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    path = request.url.path

    # Public probe endpoint
    if path in PUBLIC_PATHS:
        return await call_next(request)

    # If no bearer token is configured, skip auth (useful for local dev).
    if not API_BEARER_TOKEN:
        return await call_next(request)

    # Protect MCP endpoints (/mcp and anything under it)
    if path == MCP_BASE_PATH or path.startswith(MCP_BASE_PATH + "/"):
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return JSONResponse({"error": "missing_bearer_token"}, status_code=401)
        token = auth.split(" ", 1)[1].strip()
        if token != API_BEARER_TOKEN:
            return JSONResponse({"error": "invalid_bearer_token"}, status_code=401)
        return await call_next(request)

    # Defense-in-depth: require bearer for all other routes too
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


# -----------------------------
# MCP server wiring (official MCP Python SDK)
# -----------------------------
# Use stateless_http=True for cloud deployments unless you need session persistence.
# json_response=True can help clients that don't want SSE-style streaming;
# leave it False unless you know you need JSON-only responses.
mcp = FastMCP(
    name="Meta Ads MCP (Cloud Run, Read-Only)",
    stateless_http=True,
)

# Register tools (keep your repo pattern)
from meta_ads_mcp_cloudrun.tools.register import register_read_tools
register_read_tools(mcp, SETTINGS)

# In the official MCP SDK, Streamable HTTP ASGI app comes from streamable_http_app()
mcp_asgi_app = mcp.streamable_http_app()

# Mount MCP endpoint
app.mount(MCP_BASE_PATH, mcp_asgi_app)
app.mount(MCP_BASE_PATH + "/", mcp_asgi_app)


# -----------------------------
# Lifespan: start session manager if present (safe no-op if not)
# -----------------------------
@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    # Some MCP SDK versions require the session manager to run when mounted.
    # If your version doesn't, this still works.
    sm = getattr(mcp, "session_manager", None)
    if sm is not None and hasattr(sm, "run"):
        async with sm.run():
            yield
    else:
        yield


# Attach lifespan to app (keeps redirect_slashes config intact)
app.router.lifespan_context = lifespan


# -----------------------------
# Local entrypoint
# -----------------------------
def main():
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(
        "meta_ads_mcp_cloudrun.main:app",
        host="0.0.0.0",
        port=port,
        # Cloud Run forwards headers; this prevents scheme/host confusion if any redirects occur.
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
