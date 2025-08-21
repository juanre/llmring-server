from fastapi import HTTPException, Request
from pgdbm import AsyncDatabaseManager

MAX_PROJECT_KEY_LENGTH = 255


async def get_project_id(request: Request) -> str:
    """Extract and require the project scope header.

    The core server is key-scoped (no users). All stateful routes must include
    the `X-Project-Key` header. We accept either case for convenience.
    """
    key = request.headers.get("X-Project-Key") or request.headers.get("x-project-key")
    if not key:
        raise HTTPException(status_code=401, detail="X-Project-Key header required")
    key = key.strip()
    if not key:
        raise HTTPException(status_code=401, detail="X-Project-Key header cannot be empty")
    if len(key) > MAX_PROJECT_KEY_LENGTH:
        raise HTTPException(status_code=400, detail="X-Project-Key too long")
    if any(ch.isspace() for ch in key):
        raise HTTPException(status_code=400, detail="X-Project-Key must not contain whitespace")
    return key


async def get_db(request: Request) -> AsyncDatabaseManager:
    """Get database manager from app state.
    
    This dependency can be overridden when using llmring-server as a library
    to provide a different database manager.
    """
    if not hasattr(request.app.state, 'db') or not request.app.state.db:
        raise HTTPException(
            status_code=500,
            detail="Database not initialized"
        )
    return request.app.state.db
