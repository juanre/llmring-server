from fastapi import Request, HTTPException


async def get_project_id(request: Request) -> str:
    """Extract and require the project scope header.

    The core server is key-scoped (no users). All stateful routes must include
    the `X-Project-Key` header. We accept either case for convenience.
    """
    key = request.headers.get("X-Project-Key") or request.headers.get("x-project-key")
    if not key:
        raise HTTPException(status_code=401, detail="X-Project-Key header required")
    return key


