FROM python:3.11-slim

# Prevents Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional, but helps TLS/certs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml

# Install deps
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

COPY src /app/src

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "src.meta_ads_mcp_cloudrun.main:app", "--host", "0.0.0.0", "--port", "8080"]
