FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.cfg /app/
COPY src /app/src

RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir .

# Cloud Run sets PORT
ENV PORT=8080

# IMPORTANT: proxy headers for Cloud Run + explicit module path
CMD ["bash", "-lc", "uvicorn meta_ads_mcp_cloudrun.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
