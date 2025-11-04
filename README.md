# LLMRing Server

Self-hostable backend for the LLMRing project. It provides optional persistence and advanced features on top of the lockfile-only workflow.

## Key Features

- **Usage Tracking**: Log LLM usage with costs and statistics
- **Registry Proxy**: Cached access to the public model registry (from GitHub Pages)
- **Conversations**: Store and retrieve conversation history
- **MCP Integration**: Persist MCP servers, tools, resources, and prompts
- **Templates**: Reusable conversation templates

This service is optional. LLMRing works fully in lockfile-only mode; run this server when you need persistence, usage tracking, or MCP integration.

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

### Docker Compose (local stack)

```bash
docker compose -f docker-compose.dev.yml up --build
```

Services:
- `db`: PostgreSQL 15 with persistent volume
- `redis`: Redis 7 for caching/rate limiting (optional but bundled)
- `server`: llmring-server with `uvicorn --reload`

### Bare-metal development helper

```bash
# Ensure you have a local Postgres running (defaults: postgres/postgres)
./scripts/dev-server.sh
```

The script:
1. Creates the development database if needed (`uv run llmring-server db create --env dev`)
2. Runs migrations (`uv run llmring-server db migrate --env dev`)
3. Starts the FastAPI server with auto-reload

### Bootstrap client configuration

After the server is running, generate a local env file from your application repo:

```bash
llmring server init --env-file .env.llmring
source .env.llmring
```

CLI helpers:
- `llmring server status` — verify health checks and API key acceptance
- `llmring server key rotate` — create a fresh API key and update `.env.llmring`
- `llmring server key list` — inspect current values from env and env file
- `llmring server stats` — aggregated usage for the active API key
- `llmring server logs --output csv` — export raw usage events
- `llmring server conversations` — inspect stored conversation history

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

Minimal required: set `LLMRING_DATABASE_URL` to a reachable Postgres instance.

## Authentication model

- Project-scoped via `X-API-Key` header
- No user management in this service
- Aliases are local to each codebase in its lockfile; the server only logs the alias label used

Security notes:
- The `X-API-Key` must be treated as a secret. Do not expose it publicly
- The server validates the header is present, non-empty, below 256 chars, and without whitespace
- In production, set narrow `LLMRING_CORS_ORIGINS` (avoid `*`) and deploy behind TLS

## Endpoints

### Public Endpoints

- GET `/` → service info
- GET `/health` → DB health
- GET `/registry` (and `/registry.json`) → aggregated provider registry (fetched from GitHub Pages)

### Project-Scoped Endpoints (require header `X-API-Key`)

#### Usage Tracking (`/api/v1`)
- POST `/api/v1/log` → Log LLM usage
  ```json
  { "provider": "openai", "model": "gpt-4", "input_tokens": 100,
    "output_tokens": 50, "cached_input_tokens": 0,
    "alias": "summarizer", "profile": "prod", "cost": 0.0025 }
  ```
- GET `/api/v1/stats?start_date=&end_date=&group_by=day` → Usage statistics

#### Conversations (`/conversations`)
- POST `/` → Create new conversation
  ```json
  { "title": "Chat Title", "system_prompt": "You are helpful",
    "model_alias": "claude-3", "project_id": "uuid" }
  ```
- GET `/` → List conversations
- GET `/{conversation_id}` → Get conversation with messages
- PATCH `/{conversation_id}` → Update conversation metadata
- GET `/{conversation_id}/messages` → Get conversation messages
- POST `/{conversation_id}/messages/batch` → Add multiple messages
- DELETE `/old-messages` → Clean up old messages

#### Conversation Templates (`/api/v1/templates`)
- POST `/` → Create template
- GET `/` → List all templates
- GET `/stats` → Template usage statistics
- GET `/{template_id}` → Get specific template
- PUT `/{template_id}` → Update template
- DELETE `/{template_id}` → Delete template
- POST `/{template_id}/use` → Record template usage

#### MCP Integration (`/api/v1/mcp`)

##### MCP Servers
- POST `/servers` → Register MCP server
  ```json
  { "name": "my-server", "url": "http://localhost:8080",
    "transport_type": "http", "auth_config": {...},
    "capabilities": {...}, "project_id": "uuid" }
  ```
- GET `/servers` → List MCP servers
- GET `/servers/{server_id}` → Get server details
- PUT `/servers/{server_id}` → Update server
- DELETE `/servers/{server_id}` → Remove server
- POST `/servers/{server_id}/refresh` → Refresh server capabilities

##### MCP Tools
- GET `/tools` → List all tools (with server info)
- GET `/tools/{tool_id}` → Get tool details
- POST `/tools/{tool_id}/execute` → Execute tool
  ```json
  { "input": {...}, "conversation_id": "uuid" }
  ```
- GET `/tools/{tool_id}/history` → Get execution history

##### MCP Resources
- GET `/resources` → List all resources
- GET `/resources/{resource_id}` → Get resource details
- GET `/resources/{resource_id}/content` → Get resource content

##### MCP Prompts
- GET `/prompts` → List all prompts
- GET `/prompts/{prompt_id}` → Get prompt details
- POST `/prompts/{prompt_id}/render` → Render prompt with arguments

Security notes:
- Stats and logs are key-scoped; ensure you send the right API key to avoid data leakage across projects

## Registry

The server proxies the public registry hosted at [`https://llmring.github.io/registry/`](https://llmring.github.io/registry/). Models are returned with provider-prefixed keys (e.g., `openai:gpt-4o-mini`). Responses are cached in Redis when configured.

## Database Schema

The server uses PostgreSQL with two schemas:

### `llmring` schema (core data)
- **usage_logs**: LLM usage tracking
- **conversations**: Conversation metadata
- **messages**: Conversation messages
- **conversation_templates**: Reusable templates

### `mcp_client` schema (MCP data)
- **servers**: MCP server registrations
- **tools**: Available tools from MCP servers
- **resources**: Available resources
- **prompts**: Available prompts
- **tool_executions**: Tool execution history

Migrations are managed via pgdbm and applied automatically on startup.

## Development

Install dev dependencies and run:

```bash
# run tests
uv run pytest -q

# run the server in reload mode
uv run llmring-server --reload

# run migrations manually
uv run llmring-db migrate
```

The project uses:
- FastAPI for HTTP API
- pgdbm for Postgres migrations and access
- httpx for outbound HTTP
- redis (optional) for caching
- Pydantic for data validation

# Security Checklist

- [ ] Set `LLMRING_CORS_ORIGINS` to explicit origins (not `*`) in production
- [ ] Serve behind TLS (reverse proxy like nginx or cloud load balancer)
- [ ] Store and rotate `X-API-Key` values securely; consider per-env keys
- [ ] Restrict egress if running in sensitive environments; registry fetches use outbound HTTP
- [ ] Enable Redis with authentication (set `LLMRING_REDIS_URL`) if caching is needed
