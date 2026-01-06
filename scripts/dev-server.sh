#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

DEFAULT_DB_URL="postgresql://localhost/llmring_dev"
export LLMRING_DATABASE_URL="${LLMRING_DATABASE_URL:-$DEFAULT_DB_URL}"
export LLMRING_DATABASE_SCHEMA="${LLMRING_DATABASE_SCHEMA:-llmring}"
export LLMRING_PORT="${LLMRING_PORT:-9101}"

echo "Using database URL: ${LLMRING_DATABASE_URL}"
echo "Ensuring database exists..."

uv run llmring-server db create --env dev || true
uv run llmring-server db migrate --env dev

echo "Starting llmring-server (auto-reload enabled)..."
exec uv run llmring-server serve --env dev --reload --port "${LLMRING_PORT}"
