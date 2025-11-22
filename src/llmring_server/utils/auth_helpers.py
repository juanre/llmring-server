"""Helper utilities for handling dual authentication modes (API key and user auth). Provides dispatch and validation functions to reduce code duplication across routers."""

"""Helper utilities for handling dual authentication modes."""

from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import HTTPException, status


async def dispatch_by_auth_type(
    auth_context: Dict[str, Optional[str]],
    api_key_handler: Callable[..., Awaitable[Any]],
    user_handler: Callable[..., Awaitable[Any]],
) -> Any:
    """Dispatch service call based on authentication type.

    Args:
        auth_context: Authentication context from get_auth_context dependency
        api_key_handler: Async function to call for API key auth
        user_handler: Async function to call for user auth

    Returns:
        Result from the appropriate handler

    Example:
        result = await dispatch_by_auth_type(
            auth_context,
            lambda: service.get_server(server_id, api_key_id=auth_context["api_key_id"]),
            lambda: service.get_server(server_id, user_id=auth_context["user_id"], project_id=auth_context["project_id"])
        )
    """
    if auth_context["type"] == "api_key":
        return await api_key_handler()
    else:
        return await user_handler()


async def verify_resource_access(
    resource: Optional[Any],
    resource_type: str = "Resource",
) -> Any:
    """Verify resource exists and user has access, raise 404 if not.

    Args:
        resource: The resource object or None
        resource_type: Type of resource for error message (e.g., "Server", "Conversation")

    Returns:
        The resource if it exists

    Raises:
        HTTPException: 404 if resource is None
    """
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type} not found",
        )
    return resource
