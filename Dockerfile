# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src

RUN uv sync --frozen --no-dev --no-editable


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN useradd --system --uid 10001 --create-home appuser

COPY --from=builder --chown=10001:0 /app/.venv /app/.venv

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=2s --start-period=20s --retries=5 \
    CMD python -c "import json,sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=1); d=json.load(r); sys.exit(0 if d.get('status')=='healthy' else 1)"

USER appuser

CMD ["uvicorn", "llmring_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
