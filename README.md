# LLMRing Server

Self-hostable backend for the LLMRing project. It adds optional capabilities on top of the lockfile-only workflow:

- Project-scoped alias sync (with profiles)
- Usage logging and simple stats
- Receipt issuance and verification (Ed25519 over RFC 8785 JCS-canonicalized JSON)
- Read-only access to the public model registry (proxied from GitHub Pages)

This service is optional. LLMRing works fully in lockfile-only mode; run this server when you want centralized alias sync, receipts, and usage stats.

## Quick start

Requirements:
- Python 3.10+
- PostgreSQL (reachable from the server)

Install and run:

```bash
# from repo root or this directory
uv run llmring-server --reload
# or
uv run python -m llmring_server.cli --reload
```

By default the server listens on http://0.0.0.0:8000 and exposes Swagger UI at `/docs`.

## Configuration

Configuration is provided via environment variables (Pydantic Settings). Key variables:

- LLMRING_DATABASE_URL: PostgreSQL connection string (default: postgresql://localhost/llmring)
- LLMRING_DATABASE_SCHEMA: Schema name (default: llmring)
- LLMRING_DATABASE_POOL_SIZE: Connection pool size (default: 20)
- LLMRING_DATABASE_POOL_OVERFLOW: Pool overflow (default: 10)
- LLMRING_REDIS_URL: Redis URL for caching (default: redis://localhost:6379/0)
- LLMRING_CACHE_TTL: Cache TTL seconds (default: 3600)
- LLMRING_CORS_ORIGINS: Comma-separated origins (default: http://localhost:5173,http://localhost:5174,*)
- LLMRING_REGISTRY_BASE_URL: Base URL for the public registry (default: https://llmring.github.io/registry/)
- LLMRING_RECEIPTS_PRIVATE_KEY_B64: Base64url Ed25519 private key (for receipt issuance)
- LLMRING_RECEIPTS_PUBLIC_KEY_B64: Base64url Ed25519 public key (for verification)
- LLMRING_RECEIPTS_KEY_ID: Identifier for current signing key

Minimal required: set `LLMRING_DATABASE_URL` to a reachable Postgres instance. If you plan to issue receipts, also set the signing key variables.

## Authentication model

- Project-scoped via `X-Project-Key` header
- No user management in this service
- The same project can carry separate alias bindings by profile (e.g., `dev`, `prod`).

## Endpoints

Public:
- GET `/` → service info
- GET `/health` → DB health
- GET `/registry` (and `/registry.json`) → aggregated provider registry (fetched from GitHub Pages)
- GET `/receipts/public-key.pem` → current public key in PEM
- GET `/receipts/public-keys.json` → list of available public keys

Project-scoped (require header `X-Project-Key`):
- Aliases (`/api/v1/aliases/...`)
  - GET `/` → list aliases (optional `?profile=`)
  - POST `/bind` → `{ alias, model, profile?, metadata? }`
  - GET `/resolve?alias=NAME&profile=default` → `{ alias, model }`
  - GET `/{alias}?profile=default`
  - PUT `/{alias}` → `{ model, profile?, metadata? }`
  - DELETE `/{alias}?profile=default`
  - POST `/bulk_upsert?profile=default` → body: `[ { alias, model, metadata? }, ... ]`
- Usage (`/api/v1/log`, `/api/v1/stats`)
  - POST `/api/v1/log` → `{ provider, model, input_tokens, output_tokens, cached_input_tokens?, alias?, profile?, cost? }`
  - GET `/api/v1/stats?start_date=&end_date=&group_by=day`
- Receipts (`/api/v1/receipts/...`)
  - POST `/` store a signed receipt `{ receipt: {...} }` (server verifies signature)
  - GET `/{receipt_id}` fetch stored receipt
  - POST `/issue` issue a signed receipt from an unsigned payload (requires configured signing key)

## Receipts

- Signature: Ed25519 over RFC 8785 JSON Canonicalization Scheme (JCS)
- Signature format: `ed25519:<base64url>`
- Receipt fields (subset):
  - `id`, `timestamp`, `model`, `alias`, `profile`, `lock_digest`, `key_id`
  - `tokens: { input, output, cached_input }`
  - `cost: { amount, calculation }`
  - `signature`
- Public keys are available at `/receipts/public-key.pem` and `/receipts/public-keys.json`.

## Registry

The server proxies the public registry hosted at [`https://llmring.github.io/registry/`](https://llmring.github.io/registry/). Models are returned with provider-prefixed keys (e.g., `openai:gpt-4o-mini`). Responses are cached in Redis when configured.

## Development

Install dev dependencies and run:

```bash
# run tests
uv run pytest -q

# run the server in reload mode
uv run llmring-server --reload
```

The project uses:
- FastAPI for HTTP API
- pgdbm for Postgres migrations and access
- httpx for outbound HTTP
- redis (optional) for caching
- cryptography + pynacl for receipts

## Notes

- This server is optional; the lockfile-only client works without it.
- Profiles let you maintain different alias→model bindings per environment.
- Keep `X-Project-Key` secret; it scopes writes and reads to a project.
