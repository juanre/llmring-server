"""Tests for MCP (Model Context Protocol) server and tool management. Covers MCP servers, tools, resources, prompts, and tool execution tracking."""

"""Tests for MCP (Model Context Protocol) integration."""

from uuid import uuid4

import pytest

from llmring_server.models.mcp import (
    MCPPromptCreate,
    MCPResourceCreate,
    MCPServerCreate,
    MCPServerUpdate,
    MCPToolCreate,
    MCPToolExecution,
)


@pytest.mark.asyncio
async def test_create_mcp_server(test_app):
    """Test creating an MCP server."""
    response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Test MCP Server",
            "url": "http://localhost:8080",
            "transport_type": "http",
            "auth_config": {"type": "bearer", "token": "test-token"},
            "capabilities": {"tools": True, "resources": True, "prompts": False},
        },
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test MCP Server"
    assert data["url"] == "http://localhost:8080"
    assert data["transport_type"] == "http"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_mcp_servers(test_app):
    """Test listing MCP servers."""
    # Create multiple servers
    for i in range(3):
        await test_app.post(
            "/api/v1/mcp/servers",
            json={
                "name": f"Server {i}",
                "url": f"http://localhost:808{i}",
                "transport_type": "http",
            },
            headers={"X-API-Key": "test-list-project"},
        )

    # List them
    response = await test_app.get(
        "/api/v1/mcp/servers",
        headers={"X-API-Key": "test-list-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


@pytest.mark.asyncio
async def test_get_mcp_server(test_app):
    """Test getting a specific MCP server."""
    # Create a server
    create_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Get Test Server",
            "url": "http://localhost:8080",
            "transport_type": "stdio",
        },
        headers={"X-API-Key": "test-project"},
    )
    assert create_response.status_code == 200
    server_id = create_response.json()["id"]

    # Get the server
    response = await test_app.get(
        f"/api/v1/mcp/servers/{server_id}",
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == server_id
    assert data["name"] == "Get Test Server"


@pytest.mark.asyncio
async def test_update_mcp_server(test_app):
    """Test updating an MCP server."""
    # Create a server
    create_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Original Name",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": "test-project"},
    )
    assert create_response.status_code == 200
    server_id = create_response.json()["id"]

    # Update it
    response = await test_app.patch(
        f"/api/v1/mcp/servers/{server_id}",
        json={
            "name": "Updated Name",
            "is_active": False,
        },
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_mcp_server(test_app):
    """Test deleting an MCP server."""
    # Create a server
    create_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "To Delete",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": "test-project"},
    )
    assert create_response.status_code == 200
    server_id = create_response.json()["id"]

    # Delete it
    response = await test_app.delete(
        f"/api/v1/mcp/servers/{server_id}",
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200

    # Verify it's gone
    get_response = await test_app.get(
        f"/api/v1/mcp/servers/{server_id}",
        headers={"X-API-Key": "test-project"},
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_mcp_tool(test_app):
    """Test creating an MCP tool."""
    # First create a server
    server_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Tool Server",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": "test-project"},
    )
    assert server_response.status_code == 200
    server_id = server_response.json()["id"]

    # Create a tool
    response = await test_app.post(
        "/api/v1/mcp/tools",
        json={
            "server_id": server_id,
            "name": "test_tool",
            "description": "A test tool",
            "input_schema": {
                "type": "object",
                "properties": {"input": {"type": "string"}},
            },
        },
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test_tool"
    assert data["server_id"] == server_id


@pytest.mark.asyncio
async def test_list_mcp_tools(test_app):
    """Test listing MCP tools."""
    # Create a server
    server_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Tools Server",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": "test-tools-project"},
    )
    assert server_response.status_code == 200
    server_id = server_response.json()["id"]

    # Create multiple tools
    for i in range(3):
        await test_app.post(
            "/api/v1/mcp/tools",
            json={
                "server_id": server_id,
                "name": f"tool_{i}",
                "description": f"Tool {i}",
                "input_schema": {"type": "object"},
            },
            headers={"X-API-Key": "test-tools-project"},
        )

    # List tools for the server
    response = await test_app.get(
        f"/api/v1/mcp/tools?server_id={server_id}",
        headers={"X-API-Key": "test-tools-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_execute_mcp_tool(test_app):
    """Test executing an MCP tool."""
    # Create a server and tool
    server_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Execution Server",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": "test-project"},
    )
    assert server_response.status_code == 200
    server_id = server_response.json()["id"]

    tool_response = await test_app.post(
        "/api/v1/mcp/tools",
        json={
            "server_id": server_id,
            "name": "exec_tool",
            "description": "Executable tool",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
            },
        },
        headers={"X-API-Key": "test-project"},
    )
    assert tool_response.status_code == 200
    tool_id = tool_response.json()["id"]

    # Execute the tool
    response = await test_app.post(
        f"/api/v1/mcp/tools/{tool_id}/execute",
        json={
            "input": {"message": "Hello MCP"},
        },
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["tool_id"] == tool_id
    assert data["input"] == {"message": "Hello MCP"}


@pytest.mark.asyncio
async def test_mcp_server_isolation_by_api_key(test_app):
    """Test that MCP servers are isolated by API key."""
    # Create server with one API key
    create_response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Isolated Server",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": "project-1"},
    )
    assert create_response.status_code == 200
    server_id = create_response.json()["id"]

    # Try to get it with a different API key
    response = await test_app.get(
        f"/api/v1/mcp/servers/{server_id}",
        headers={"X-API-Key": "project-2"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mcp_requires_auth(test_app):
    """Test that MCP endpoints require authentication."""
    # Try without header
    response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "No Auth",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
    )
    assert response.status_code == 401

    # Try with empty header
    response = await test_app.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Empty Auth",
            "url": "http://localhost:8080",
            "transport_type": "http",
        },
        headers={"X-API-Key": ""},
    )
    assert response.status_code == 401
