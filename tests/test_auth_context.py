# ABOUTME: Test authentication context handling for browser vs programmatic access.
# ABOUTME: Verifies get_auth_context extracts API key or user+project authentication.

import pytest
import pytest_asyncio
from fastapi import Request

from llmring_server.dependencies import get_auth_context


@pytest_asyncio.fixture
async def setup_api_keys_table(llmring_db):
    """Create llmring_api schema and api_keys table for testing cross-schema authorization."""
    await llmring_db.execute("CREATE SCHEMA IF NOT EXISTS llmring_api")
    await llmring_db.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    await llmring_db.execute(
        """
        CREATE TABLE IF NOT EXISTS llmring_api.api_keys (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL,
            name VARCHAR(255) NOT NULL,
            key_hash VARCHAR(255) NOT NULL
        )
        """
    )
    return llmring_db


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


@pytest.mark.asyncio
async def test_mcp_list_servers_with_user_auth(test_app, setup_api_keys_table):
    """Test listing MCP servers with user authentication filters by project."""
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create API key for project 2
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000002'::uuid, '10000000-0000-0000-0000-000000000002'::uuid, 'Test Key 2', 'hash2')
        """
    )

    # Create server for project 1
    await llmring_db.execute(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Server 1', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        """
    )

    # Create server for project 2
    await llmring_db.execute(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Server 2', 'http://server2', 'http', '00000000-0000-0000-0000-000000000002')
        """
    )

    # User 1 lists servers - should only see project 1's servers
    response = await test_app.get(
        "/api/v1/mcp/servers",
        headers={"X-User-ID": "user-1", "X-Project-ID": "10000000-0000-0000-0000-000000000001"},
    )

    assert response.status_code == 200
    servers = response.json()
    assert len(servers) == 1
    assert servers[0]["name"] == "Server 1"

    # User 2 lists servers - should only see project 2's servers
    response = await test_app.get(
        "/api/v1/mcp/servers",
        headers={"X-User-ID": "user-2", "X-Project-ID": "10000000-0000-0000-0000-000000000002"},
    )

    assert response.status_code == 200
    servers = response.json()
    assert len(servers) == 1
    assert servers[0]["name"] == "Server 2"


@pytest.mark.asyncio
async def test_mcp_get_server_authorization_bypass(test_app, setup_api_keys_table):
    """Test that get_server prevents cross-project access with user auth.

    SECURITY TEST: This test exposes the authorization bypass vulnerability
    where any authenticated user can access any server by ID, regardless of
    project ownership.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create server for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Project 1 Server', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )
    server_id = result["id"]

    # User from project 2 tries to access project 1's server - should get 404
    response = await test_app.get(
        f"/api/v1/mcp/servers/{server_id}",
        headers={"X-User-ID": "user-2", "X-Project-ID": "10000000-0000-0000-0000-000000000002"},
    )

    # SECURITY VIOLATION: This currently returns 200 instead of 404
    assert (
        response.status_code == 404
    ), "Authorization bypass: user can access server from different project"


@pytest.mark.asyncio
async def test_mcp_update_server_authorization_bypass(test_app, setup_api_keys_table):
    """Test that update_server prevents cross-project modification with user auth.

    SECURITY TEST: This test exposes the authorization bypass vulnerability
    where any authenticated user can modify any server by ID.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create server for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Original Name', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )
    server_id = result["id"]

    # User from project 2 tries to modify project 1's server - should get 404
    response = await test_app.patch(
        f"/api/v1/mcp/servers/{server_id}",
        json={"name": "Hacked Name"},
        headers={"X-User-ID": "user-2", "X-Project-ID": "10000000-0000-0000-0000-000000000002"},
    )

    # SECURITY VIOLATION: This currently returns 200 instead of 404
    assert (
        response.status_code == 404
    ), "Authorization bypass: user can modify server from different project"

    # Verify server was not modified
    result = await llmring_db.fetch_one(
        "SELECT name FROM mcp_client.servers WHERE id = $1", server_id
    )
    assert result["name"] == "Original Name", "Server should not have been modified"


@pytest.mark.asyncio
async def test_mcp_delete_server_authorization_bypass(test_app, setup_api_keys_table):
    """Test that delete_server prevents cross-project deletion with user auth.

    SECURITY TEST: This test exposes the authorization bypass vulnerability
    where any authenticated user can delete any server by ID.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create server for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Important Server', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )
    server_id = result["id"]

    # User from project 2 tries to delete project 1's server - should get 404
    response = await test_app.delete(
        f"/api/v1/mcp/servers/{server_id}",
        headers={"X-User-ID": "user-2", "X-Project-ID": "10000000-0000-0000-0000-000000000002"},
    )

    # SECURITY VIOLATION: This currently returns 200 instead of 404
    assert (
        response.status_code == 404
    ), "Authorization bypass: user can delete server from different project"

    # Verify server was not deleted
    result = await llmring_db.fetch_one(
        "SELECT id FROM mcp_client.servers WHERE id = $1", server_id
    )
    assert result is not None, "Server should not have been deleted"


@pytest.mark.asyncio
async def test_mcp_refresh_server_capabilities_authorization_bypass(test_app, setup_api_keys_table):
    """Test that refresh_server_capabilities prevents cross-project access.

    SECURITY TEST: This test exposes the authorization bypass vulnerability
    where any authenticated user can refresh capabilities for any server.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create server for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Server 1', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )
    server_id = result["id"]

    # User from project 2 tries to refresh project 1's server capabilities - should get 404
    response = await test_app.post(
        f"/api/v1/mcp/servers/{server_id}/refresh",
        json={"tools": [], "resources": [], "prompts": []},
        headers={"X-User-ID": "user-2", "X-Project-ID": "10000000-0000-0000-0000-000000000002"},
    )

    # SECURITY VIOLATION: This currently returns 200 instead of 404
    assert (
        response.status_code == 404
    ), "Authorization bypass: user can refresh capabilities for server from different project"
