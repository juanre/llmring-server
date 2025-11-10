# ABOUTME: Test authentication context handling for browser vs programmatic access.
# ABOUTME: Verifies get_auth_context extracts API key or user+project authentication.

import pytest
from fastapi import Request

from llmring_server.dependencies import get_auth_context


@pytest.mark.asyncio
async def test_api_key_auth_context():
    """Test API key authentication returns api_key_id context."""

    # Mock request with X-API-Key header
    class MockRequest:
        headers = {"x-api-key": "test-api-key-id"}

    request = MockRequest()
    context = await get_auth_context(request)

    assert context["type"] == "api_key"
    assert context["api_key_id"] == "test-api-key-id"
    assert context.get("user_id") is None


@pytest.mark.asyncio
async def test_user_auth_context():
    """Test user authentication returns user_id + project_id context."""

    # Mock request with X-User-ID and X-Project-ID headers
    class MockRequest:
        headers = {"x-user-id": "user-123", "x-project-id": "project-456"}

    request = MockRequest()
    context = await get_auth_context(request)

    assert context["type"] == "user"
    assert context["user_id"] == "user-123"
    assert context["project_id"] == "project-456"
    assert context.get("api_key_id") is None


@pytest.mark.asyncio
async def test_no_auth_context_raises_401():
    """Test missing authentication raises 401."""

    # Mock request with no auth headers
    class MockRequest:
        headers = {}

    request = MockRequest()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_auth_context(request)

    assert exc_info.value.status_code == 401
