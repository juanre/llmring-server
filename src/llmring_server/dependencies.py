# ABOUTME: FastAPI dependencies for API key validation and database access.
# ABOUTME: Provides get_project_id for authentication and get_db for database injection.

from typing import Dict, Optional

from fastapi import HTTPException, Request
from pgdbm import AsyncDatabaseManager

from llmring_server.config import Settings

MAX_PROJECT_KEY_LENGTH = 255


async def get_auth_context(request: Request) -> Dict[str, Optional[str]]:
    """Extract authentication context from request headers.

    Supports two authentication modes:
    1. API Key (programmatic): X-API-Key header contains api_key_id
    2. User/Browser (JWT): X-User-ID + X-Project-ID headers

    Returns dict with:
    - type: "api_key" or "user"
    - api_key_id: str (if type="api_key")
    - user_id: str (if type="user")
    - project_id: str (if type="user")
    """
    # Check for API key authentication (programmatic access)
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if api_key:
        api_key = api_key.strip()
        if not api_key:
            raise HTTPException(status_code=401, detail="X-API-Key header cannot be empty")
        if len(api_key) > MAX_PROJECT_KEY_LENGTH:
            raise HTTPException(status_code=400, detail="X-API-Key too long")
        if any(ch.isspace() for ch in api_key):
            raise HTTPException(status_code=400, detail="X-API-Key must not contain whitespace")

        return {
            "type": "api_key",
            "api_key_id": api_key,
            "user_id": None,
            "project_id": None,
        }

    # Check for user authentication (browser/JWT access)
    user_id = request.headers.get("X-User-ID") or request.headers.get("x-user-id")
    project_id = request.headers.get("X-Project-ID") or request.headers.get("x-project-id")

    if user_id and project_id:
        user_id = user_id.strip()
        project_id = project_id.strip()

        if not user_id or not project_id:
            raise HTTPException(
                status_code=401, detail="X-User-ID and X-Project-ID cannot be empty"
            )

        return {
            "type": "user",
            "api_key_id": None,
            "user_id": user_id,
            "project_id": project_id,
        }

    # No valid authentication found
    raise HTTPException(
        status_code=401,
        detail="Authentication required: provide X-API-Key or (X-User-ID + X-Project-ID)",
    )


async def get_project_id(request: Request) -> str:
    """Extract and require the API key header (legacy compatibility).

    This function is maintained for backward compatibility with existing routes.
    New routes should use get_auth_context() for full context.

    Returns the api_key_id for API key auth, or api_key_id for user auth
    (user auth will be handled by looking up project's first active API key).
    """
    context = await get_auth_context(request)

    if context["type"] == "api_key":
        return context["api_key_id"]
    else:
        # For user auth, routes will need to handle user_id + project_id
        # This is a transitional approach - routes should migrate to get_auth_context
        raise HTTPException(
            status_code=500,
            detail="Route not yet updated for user authentication - use get_auth_context",
        )


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

    This allows tests to inject custom settings, while
    production code can continue using environment variables.
    """
    if hasattr(request.app.state, "settings") and request.app.state.settings:
        return request.app.state.settings
    return Settings()
