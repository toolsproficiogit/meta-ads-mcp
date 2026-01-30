# Meta Ads MCP (Cloud Run, Read-Only)

This repo is a **read-only** Model Context Protocol (MCP) server for the **Meta Marketing API (Meta Ads)**, designed to run on **Google Cloud Run** and be used as **n8n AI Agent tools** via **Streamable HTTP transport** with **Bearer authentication**.

It is based on the public behavior/tooling of Pipeboard’s Meta Ads MCP, but modified per your requirements:

- ✅ **Only “read/get” tools** in the initial deployment (no create/update/upload).
- ✅ Meta API auth via **Business App + System User + server-side long-lived token** (no user OAuth flow).
- ✅ Ability to **limit accessible ad accounts** via env var allowlist (system user can still have access to all accounts).
- ✅ Ability to **enable/disable tools** via env vars (defense-in-depth).

## What you get

- `/mcp` — MCP Streamable HTTP endpoint (for n8n, Claude, Cursor, etc.)
- `/healthz` — simple health check

## Tool list (read-only)

All tool names are prefixed with `mcp_meta_ads_`:

- `mcp_meta_ads_list_accounts`
- `mcp_meta_ads_get_account`
- `mcp_meta_ads_get_campaigns`
- `mcp_meta_ads_get_campaign_details`
- `mcp_meta_ads_get_adsets`
- `mcp_meta_ads_get_ads`
- `mcp_meta_ads_get_ad_details`
- `mcp_meta_ads_get_insights`

> Adding future tools: create a new module in `src/meta_ads_mcp_cloudrun/tools/` and register them in `main.py` (see `register_read_tools()` pattern).

---

# 1) Meta prerequisites (Business App + System User token)

You will create a **Meta Business App**, then a **System User**, assign it assets (ad accounts), and generate a token.

## 1.1 Create (or choose) a Business App

1. Go to Meta for Developers → **My Apps** → **Create App**
2. Choose **Business** type (recommended for Marketing API integrations).
3. Add the **Marketing API** product if prompted.

## 1.2 Create a System User and assign assets

1. Open **Meta Business Settings**
2. Go to **Users → System Users**
3. Click **Add** → create an **Admin** system user
4. Select the system user → **Add Assets**:
   - assign the relevant **Ad Accounts** with appropriate permissions (e.g., “Manage campaigns”, “View performance”)

Meta docs:
- System users overview: citeturn7search3

## 1.3 Generate a System User access token

1. In Business Settings → System Users
2. Select your system user
3. Click **Generate new token**
4. Choose your app
5. Select permissions:
   - `ads_read` (minimum for insights and listing)
   - `ads_management` (often needed even for some reads; depends on your setup)
   - `business_management` (helps for listing assets in some org setups)

Official Meta guide for generating a system user token (UI steps): citeturn7search1

> Token lifetime: Meta documents long-lived tokens and (in some cases) “no expiry” behavior for long-lived tokens depending on app status/permissions. Verify your token expiry in the Access Token Debugger. citeturn7search0turn7search17

---

# 2) Google Cloud Run deployment (copy/paste)

## 2.1 Prereqs

- A Google Cloud project
- Billing enabled
- `gcloud` available (Cloud Shell is easiest)

## 2.2 One-time setup (Cloud Shell)

```bash
# ---- set your values ----
export PROJECT_ID="YOUR_GCP_PROJECT_ID"
export REGION="us-central1"
export SERVICE_NAME="meta-ads-mcp"

# Create/choose project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

## 2.3 Build and deploy

### Option A (Recommended): store secrets in Secret Manager

```bash
# Create secrets (you will paste values when prompted)
echo -n "PASTE_META_SYSTEM_USER_TOKEN_HERE" | gcloud secrets create META_ACCESS_TOKEN --data-file=-
echo -n "CHOOSE_A_LONG_RANDOM_BEARER_TOKEN" | gcloud secrets create API_BEARER_TOKEN --data-file=-

# Grant Cloud Run access to secrets at runtime
gcloud secrets add-iam-policy-binding META_ACCESS_TOKEN \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding API_BEARER_TOKEN \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Build container
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

# Deploy to Cloud Run
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars META_API_VERSION="v20.0",REQUEST_TIMEOUT_SECONDS="30" \
  --set-secrets META_ACCESS_TOKEN=META_ACCESS_TOKEN:latest,API_BEARER_TOKEN=API_BEARER_TOKEN:latest
```

### Option B: env vars directly (simpler, less secure)

```bash
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars \
    META_ACCESS_TOKEN="PASTE_TOKEN_HERE",\
    API_BEARER_TOKEN="CHOOSE_A_LONG_RANDOM_BEARER_TOKEN",\
    META_API_VERSION="v20.0",\
    REQUEST_TIMEOUT_SECONDS="30"
```

After deploy, Cloud Run prints the service URL. Your MCP endpoint is:

- `https://YOUR_CLOUD_RUN_URL/mcp`

Health check:

- `https://YOUR_CLOUD_RUN_URL/healthz`

---

# 3) Configure n8n (AI Agent tools)

In n8n, when adding an MCP (Streamable HTTP) tool/server:

- **URL**: `https://YOUR_CLOUD_RUN_URL/mcp`
- **Auth**: Bearer
- **Token**: the value of `API_BEARER_TOKEN`

---

# 4) Server configuration (env vars)

## Required

- `META_ACCESS_TOKEN` — System User access token (server-side).
- `API_BEARER_TOKEN` — token clients must send as `Authorization: Bearer ...`

## Optional

- `META_API_VERSION` (default: `v20.0`)
- `REQUEST_TIMEOUT_SECONDS` (default: `30`)

## Account allowlist (security)

Limit which ad accounts can be queried by *any* tool that accepts `account_id`:

- `ALLOWED_AD_ACCOUNTS` — comma-separated list, e.g. `act_123,act_456`

If unset/empty, all accounts are allowed.

## Enable/disable tools (security)

- `DISABLED_TOOLS` — comma-separated tool names (supports prefix wildcard `*`)
  - Example: `DISABLED_TOOLS="mcp_meta_ads_get_insights,mcp_meta_ads_get_ads"`
  - Example wildcard: `DISABLED_TOOLS="mcp_meta_ads_get_*"`
- `ENABLED_TOOLS` — if set, **only** these tools are enabled (also supports `*`)

Precedence:
1. `DISABLED_TOOLS`
2. `ENABLED_TOOLS` (if non-empty)

---

# 5) Local development

```bash
export META_ACCESS_TOKEN="..."
export API_BEARER_TOKEN="devtoken"
uvicorn src.meta_ads_mcp_cloudrun.main:app --host 0.0.0.0 --port 8080
```

Test:

```bash
curl -N -H "Authorization: Bearer devtoken" http://localhost:8080/mcp
curl http://localhost:8080/healthz
```

---

# Notes & best practices

- Prefer **Secret Manager** for `META_ACCESS_TOKEN` and `API_BEARER_TOKEN`.
- For rotation, generate a new System User token in Business Settings and update the secret.
- To add write tools later:
  - add a `write_tools.py` module
  - gate them behind `ENABLED_TOOLS` / `DISABLED_TOOLS`
  - consider an additional “confirmation” pattern at tool level before any state-changing call

---

# Disclaimer

This is an unofficial third-party integration with Meta’s APIs. You are responsible for complying with Meta platform policies and terms.
