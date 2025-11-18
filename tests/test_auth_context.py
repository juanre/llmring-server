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
    # Create conversations table for conversation tests
    await llmring_db.execute(
        """
        CREATE TABLE IF NOT EXISTS {{tables.conversations}} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            api_key_id VARCHAR(255) NOT NULL,
            title VARCHAR(255),
            system_prompt TEXT,
            model_alias VARCHAR(255),
            temperature FLOAT,
            max_tokens INT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
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
        headers = {
            "x-user-id": "00000000-0000-0000-0000-000000000001",
            "x-project-id": "10000000-0000-0000-0000-000000000001",
        }

    request = MockRequest()
    context = await get_auth_context(request)

    assert context["type"] == "user"
    assert context["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert context["project_id"] == "10000000-0000-0000-0000-000000000001"
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
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000001",
            "X-Project-ID": "10000000-0000-0000-0000-000000000001",
        },
    )

    assert response.status_code == 200
    servers = response.json()
    assert len(servers) == 1
    assert servers[0]["name"] == "Server 1"

    # User 2 lists servers - should only see project 2's servers
    response = await test_app.get(
        "/api/v1/mcp/servers",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
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
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
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
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
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
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
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
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    # SECURITY VIOLATION: This currently returns 200 instead of 404
    assert (
        response.status_code == 404
    ), "Authorization bypass: user can refresh capabilities for server from different project"


@pytest.mark.asyncio
async def test_conversation_list_with_user_auth(test_app, setup_api_keys_table):
    """Test listing conversations with user authentication filters by project."""
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

    # Create conversation for project 1
    await llmring_db.execute(
        """
        INSERT INTO {{tables.conversations}} (api_key_id, title, model_alias)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Project 1 Conversation', 'default')
        """
    )

    # Create conversation for project 2
    await llmring_db.execute(
        """
        INSERT INTO {{tables.conversations}} (api_key_id, title, model_alias)
        VALUES ('00000000-0000-0000-0000-000000000002', 'Project 2 Conversation', 'default')
        """
    )

    # User 1 lists conversations - should only see project 1's conversations
    response = await test_app.get(
        "/api/v1/conversations/",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000001",
            "X-Project-ID": "10000000-0000-0000-0000-000000000001",
        },
    )

    assert response.status_code == 200
    conversations = response.json()
    assert len(conversations) == 1
    assert conversations[0]["title"] == "Project 1 Conversation"

    # User 2 lists conversations - should only see project 2's conversations
    response = await test_app.get(
        "/api/v1/conversations/",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert response.status_code == 200
    conversations = response.json()
    assert len(conversations) == 1
    assert conversations[0]["title"] == "Project 2 Conversation"


@pytest.mark.asyncio
async def test_conversation_get_authorization_bypass(test_app, setup_api_keys_table):
    """Test that get_conversation prevents cross-project access with user auth.

    SECURITY TEST: This test ensures users cannot access conversations
    from projects they don't own.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create conversation for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO {{tables.conversations}} (api_key_id, title, model_alias)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Private Conversation', 'default')
        RETURNING id
        """
    )
    conversation_id = result["id"]

    # User from project 2 tries to access project 1's conversation - should get 404
    response = await test_app.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert (
        response.status_code == 404
    ), "Authorization bypass: user can access conversation from different project"


@pytest.mark.asyncio
async def test_conversation_update_authorization_bypass(test_app, setup_api_keys_table):
    """Test that update_conversation prevents cross-project modification with user auth.

    SECURITY TEST: This test ensures users cannot modify conversations
    from projects they don't own.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create conversation for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO {{tables.conversations}} (api_key_id, title, model_alias)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Original Title', 'default')
        RETURNING id
        """
    )
    conversation_id = result["id"]

    # User from project 2 tries to modify project 1's conversation - should get 404
    response = await test_app.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Hacked Title"},
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert (
        response.status_code == 404
    ), "Authorization bypass: user can modify conversation from different project"

    # Verify conversation was not modified
    result = await llmring_db.fetch_one(
        "SELECT title FROM {{tables.conversations}} WHERE id = $1", conversation_id
    )
    assert result["title"] == "Original Title", "Conversation should not have been modified"


@pytest.mark.asyncio
async def test_conversation_messages_authorization_bypass(test_app, setup_api_keys_table):
    """Test that get_conversation_messages prevents cross-project access.

    SECURITY TEST: This test ensures users cannot access messages
    from conversations in projects they don't own.
    """
    llmring_db = setup_api_keys_table

    # Create API key for project 1
    await llmring_db.execute(
        """
        INSERT INTO llmring_api.api_keys (id, project_id, name, key_hash)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 'Test Key 1', 'hash1')
        """
    )

    # Create conversation for project 1
    result = await llmring_db.fetch_one(
        """
        INSERT INTO {{tables.conversations}} (api_key_id, title, model_alias)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Private Conversation', 'default')
        RETURNING id
        """
    )
    conversation_id = result["id"]

    # User from project 2 tries to access project 1's conversation messages - should get 404
    response = await test_app.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert (
        response.status_code == 404
    ), "Authorization bypass: user can access messages from conversation in different project"


@pytest.mark.asyncio
async def test_invalid_uuid_format_raises_400():
    """Test that invalid UUID format in headers raises 400."""

    class MockRequest:
        headers = {"x-user-id": "not-a-uuid", "x-project-id": "also-not-a-uuid"}

    request = MockRequest()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_auth_context(request)

    assert exc_info.value.status_code == 400
    assert "Invalid UUID format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_mcp_endpoints_require_authentication(test_app):
    """Test that all MCP endpoints reject unauthenticated requests."""
    # Test endpoints that should require authentication
    endpoints = [
        ("GET", "/api/v1/mcp/tools/00000000-0000-0000-0000-000000000001"),
        ("POST", "/api/v1/mcp/tools/00000000-0000-0000-0000-000000000001/execute"),
        ("GET", "/api/v1/mcp/tools/00000000-0000-0000-0000-000000000001/history"),
        ("GET", "/api/v1/mcp/resources"),
        ("GET", "/api/v1/mcp/resources/00000000-0000-0000-0000-000000000001"),
        ("GET", "/api/v1/mcp/resources/00000000-0000-0000-0000-000000000001/content"),
        ("GET", "/api/v1/mcp/prompts"),
        ("GET", "/api/v1/mcp/prompts/00000000-0000-0000-0000-000000000001"),
        ("POST", "/api/v1/mcp/prompts/00000000-0000-0000-0000-000000000001/render"),
    ]

    for method, endpoint in endpoints:
        if method == "GET":
            response = await test_app.get(endpoint)
        elif method == "POST":
            response = await test_app.post(endpoint, json={})

        assert (
            response.status_code == 401
        ), f"{method} {endpoint} should require authentication (got {response.status_code})"


@pytest.mark.asyncio
async def test_mcp_tool_get_authorization_bypass(test_app, setup_api_keys_table):
    """Test that get_tool prevents cross-project access with user auth.

    SECURITY TEST: This test ensures users cannot access tools
    from projects they don't own.
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
    server_result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Server 1', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )

    # Create tool for project 1
    tool_result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.tools (server_id, name, description, input_schema, api_key_id)
        VALUES ($1, 'Private Tool', 'Secret tool', '{}', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """,
        server_result["id"],
    )
    tool_id = tool_result["id"]

    # User from project 2 tries to access project 1's tool - should get 404
    response = await test_app.get(
        f"/api/v1/mcp/tools/{tool_id}",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert (
        response.status_code == 404
    ), "Authorization bypass: user can access tool from different project"


@pytest.mark.asyncio
async def test_mcp_resource_get_authorization_bypass(test_app, setup_api_keys_table):
    """Test that get_resource prevents cross-project access with user auth.

    SECURITY TEST: This test ensures users cannot access resources
    from projects they don't own.
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
    server_result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Server 1', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )

    # Create resource for project 1
    resource_result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.resources (server_id, uri, name, description, api_key_id)
        VALUES ($1, 'file://secret.txt', 'Secret Resource', 'Private data', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """,
        server_result["id"],
    )
    resource_id = resource_result["id"]

    # User from project 2 tries to access project 1's resource - should get 404
    response = await test_app.get(
        f"/api/v1/mcp/resources/{resource_id}",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert (
        response.status_code == 404
    ), "Authorization bypass: user can access resource from different project"


@pytest.mark.asyncio
async def test_mcp_prompt_get_authorization_bypass(test_app, setup_api_keys_table):
    """Test that get_prompt prevents cross-project access with user auth.

    SECURITY TEST: This test ensures users cannot access prompts
    from projects they don't own.
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
    server_result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.servers (name, url, transport_type, api_key_id)
        VALUES ('Server 1', 'http://server1', 'http', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """
    )

    # Create prompt for project 1
    prompt_result = await llmring_db.fetch_one(
        """
        INSERT INTO mcp_client.prompts (server_id, name, description, api_key_id)
        VALUES ($1, 'Secret Prompt', 'Private prompt', '00000000-0000-0000-0000-000000000001')
        RETURNING id
        """,
        server_result["id"],
    )
    prompt_id = prompt_result["id"]

    # User from project 2 tries to access project 1's prompt - should get 404
    response = await test_app.get(
        f"/api/v1/mcp/prompts/{prompt_id}",
        headers={
            "X-User-ID": "20000000-0000-0000-0000-000000000002",
            "X-Project-ID": "10000000-0000-0000-0000-000000000002",
        },
    )

    assert (
        response.status_code == 404
    ), "Authorization bypass: user can access prompt from different project"
