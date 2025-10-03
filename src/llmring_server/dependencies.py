from fastapi import HTTPException, Request
from pgdbm import AsyncDatabaseManager

from llmring_server.config import Settings

MAX_PROJECT_KEY_LENGTH = 255


async def get_project_id(request: Request) -> str:
    """Extract and require the API key header.

    The core server is key-scoped (no users). All stateful routes must include
    the `X-API-Key` header which contains the api_key_id. We accept either case for convenience.
    """
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if not key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    key = key.strip()
    if not key:
        raise HTTPException(status_code=401, detail="X-API-Key header cannot be empty")
    if len(key) > MAX_PROJECT_KEY_LENGTH:
        raise HTTPException(status_code=400, detail="X-API-Key too long")
    if any(ch.isspace() for ch in key):
        raise HTTPException(status_code=400, detail="X-API-Key must not contain whitespace")
    return key


async def get_db(request: Request) -> AsyncDatabaseManager:
    """Get database manager from app state.

    This dependency can be overridden when using llmring-server as a library
    to provide a different database manager.
    """
    if not hasattr(request.app.state, "db") or not request.app.state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    """Get settings from app state or create new instance.

    This dependency checks app.state.settings first (for testing),
    then falls back to creating a new Settings() instance (for production).

    This allows tests to inject settings with receipt keys, while
    production code can continue using environment variables.
    """
    if hasattr(request.app.state, "settings") and request.app.state.settings:
        return request.app.state.settings
    return Settings()
