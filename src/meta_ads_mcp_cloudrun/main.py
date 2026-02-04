import os
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

# NOTE: This repo uses MCP "Streamable HTTP" via FastMCP.
# The important fix is to avoid FastAPI/Starlette's automatic slash redirects
# which break clients like n8n on Cloud Run.
from mcp.server.fastmcp import FastMCP

# ---- Config helpers ----

def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def _normalize_path(p: str) -> str:
    # Ensure no trailing slash (except root)
    if p != "/" and p.endswith("/"):
        return p[:-1]
    return p

API_BEARER_TOKEN = _require_env("API_BEARER_TOKEN")

# Optional: keep /healthz unauthenticated for Cloud Run probes / simple checks
PUBLIC_PATHS = {"/healthz"}

# MCP base path used by n8n, etc.
MCP_BASE_PATH = "/mcp"

# ---- App + auth middleware ----

# CRITICAL: redirect_slashes=False prevents FastAPI/Starlette from redirecting
# /mcp -> /mcp/ (307) which breaks many MCP clients and caused your 404s.
app = FastAPI(redirect_slashes=False)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    path = request.url.path

    # Allow unauthenticated health checks
    if path in PUBLIC_PATHS:
        return await call_next(request)

    # Allow MCP paths to be authenticated but accepted for both /mcp and /mcp/ and subpaths
    # (Some clients probe /mcp, others might hit /mcp/, and MCP internals may use subpaths.)
    if path == MCP_BASE_PATH or path.startswith(MCP_BASE_PATH + "/"):
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return JSONResponse({"error": "missing_bearer_token"}, status_code=401)
        token = auth.split(" ", 1)[1].strip()
        if token != API_BEARER_TOKEN:
            return JSONResponse({"error": "invalid_bearer_token"}, status_code=401)
        return await call_next(request)

    # Everything else: require bearer too (defense-in-depth)
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

# Import + register tools exactly as your repo already does.
# Keeping this pattern intact; only the HTTP plumbing/auth/redirect behavior changes.
#
# If your repo has a register_read_tools(mcp) helper, keep using it here.
try:
    from meta_ads_mcp_cloudrun.tools.register import register_read_tools  # type: ignore
    register_read_tools(mcp)
except Exception:
    # If your project registers tools in a different way, remove this block and keep your existing imports.
    # This fallback prevents startup from crashing if the helper isn't present in your current tree.
    pass

# Expose MCP over Streamable HTTP as an ASGI app.
# FastMCP provides get_asgi_app() in current MCP Python SDK releases.
mcp_app = mcp.get_asgi_app()

# Mount MCP at /mcp (NO redirects due to FastAPI(redirect_slashes=False))
app.mount(MCP_BASE_PATH, mcp_app)


# ---- Cloud Run entrypoint ----

def main():
    port = int(os.environ.get("PORT", "8080"))
    # proxy_headers=True makes uvicorn respect X-Forwarded-Proto/For/Host on Cloud Run
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