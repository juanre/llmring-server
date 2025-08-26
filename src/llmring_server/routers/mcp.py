"""MCP (Model Context Protocol) router for llmring-server."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pgdbm import AsyncDatabaseManager

from llmring_server.dependencies import get_db, get_project_id
from llmring_server.models.mcp import (
    MCPCapabilities,
    MCPPrompt,
    MCPResource,
    MCPServer,
    MCPServerCreate,
    MCPServerUpdate,
    MCPTool,
    MCPToolCreate,
    MCPToolExecution,
    MCPToolExecutionRequest,
    MCPToolExecutionResponse,
    MCPToolWithServer,
)
from llmring_server.services.mcp_service import MCPService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


async def get_mcp_service(db: AsyncDatabaseManager = Depends(get_db)) -> MCPService:
    """Get MCP service dependency."""
    return MCPService(db)


# ============= MCP Server Endpoints =============

@router.post("/servers", response_model=MCPServer)
async def create_server(
    server: MCPServerCreate,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> MCPServer:
    """Register a new MCP server."""
    try:
        server_id = await mcp_service.create_server(
            name=server.name,
            url=server.url,
            transport_type=server.transport_type,
            auth_config=server.auth_config,
            capabilities=server.capabilities,
            api_key_id=api_key,
        )
        
        server_data = await mcp_service.get_server(server_id)
        if not server_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create server"
            )
        
        return MCPServer(**server_data)
    except Exception as e:
        logger.error(f"Error creating MCP server: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/servers", response_model=List[MCPServer])
async def list_servers(
    is_active: bool = True,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> List[MCPServer]:
    """List MCP servers."""
    try:
        servers = await mcp_service.list_servers(
            api_key_id=api_key,
            is_active=is_active,
        )
        return [MCPServer(**s) for s in servers]
    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/servers/{server_id}", response_model=MCPServer)
async def get_server(
    server_id: UUID,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> MCPServer:
    """Get an MCP server by ID."""
    try:
        server = await mcp_service.get_server(server_id, api_key_id=api_key)
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        return MCPServer(**server)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP server: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/servers/{server_id}", response_model=MCPServer)
async def update_server(
    server_id: UUID,
    update: MCPServerUpdate,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> MCPServer:
    """Update an MCP server."""
    try:
        updated = await mcp_service.update_server(
            server_id=server_id,
            name=update.name,
            url=update.url,
            auth_config=update.auth_config,
            capabilities=update.capabilities,
            is_active=update.is_active,
        )
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        
        server = await mcp_service.get_server(server_id, api_key_id=api_key)
        return MCPServer(**server)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating MCP server: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: UUID,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> dict:
    """Delete an MCP server."""
    try:
        deleted = await mcp_service.delete_server(server_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        return {"message": "Server deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting MCP server: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/servers/{server_id}/refresh", response_model=MCPCapabilities)
async def refresh_server_capabilities(
    server_id: UUID,
    capabilities: dict,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> MCPCapabilities:
    """Refresh server capabilities (tools, resources, prompts)."""
    try:
        # Extract tools, resources, prompts from capabilities
        tools = capabilities.get("tools", [])
        resources = capabilities.get("resources", [])
        prompts = capabilities.get("prompts", [])
        
        # Refresh in database
        await mcp_service.refresh_server_capabilities(
            server_id=server_id,
            tools=tools,
            resources=resources,
            prompts=prompts,
        )
        
        # Get updated data
        server = await mcp_service.get_server(server_id, api_key_id=api_key)
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        
        tools_list = await mcp_service.list_tools(server_id=server_id)
        resources_list = await mcp_service.list_resources(server_id=server_id)
        prompts_list = await mcp_service.list_prompts(server_id=server_id)
        
        return MCPCapabilities(
            server=MCPServer(**server),
            tools=[MCPTool(**t) for t in tools_list],
            resources=[MCPResource(**r) for r in resources_list],
            prompts=[MCPPrompt(**p) for p in prompts_list],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing server capabilities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============= Tool Endpoints =============

@router.post("/tools", response_model=MCPTool)
async def create_tool(
    tool: MCPToolCreate,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> MCPTool:
    """Create a new MCP tool."""
    try:
        tool_id = await mcp_service.create_tool(
            server_id=tool.server_id,
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            api_key_id=api_key,
        )
        
        tool_data = await mcp_service.get_tool(tool_id)
        if not tool_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tool"
            )
        
        return MCPTool(**tool_data)
    except Exception as e:
        logger.error(f"Error creating MCP tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/tools", response_model=List[MCPToolWithServer])
async def list_tools(
    server_id: Optional[UUID] = None,
    is_active: bool = True,
    mcp_service: MCPService = Depends(get_mcp_service),
    api_key: str = Depends(get_project_id),
) -> List[MCPToolWithServer]:
    """List all MCP tools."""
    try:
        tools = await mcp_service.list_tools(
            server_id=server_id,
            api_key_id=api_key,
            is_active=is_active,
        )
        
        # Build response with server info
        result = []
        for tool in tools:
            # Extract server info from joined query
            server_info = {
                "id": tool["server_id"],
                "name": tool.get("server_name"),
                "url": tool.get("server_url"),
            }
            
            # Create tool with server
            tool_with_server = MCPToolWithServer(
                id=tool["id"],
                server_id=tool["server_id"],
                api_key_id=tool.get("api_key_id"),
                name=tool["name"],
                description=tool.get("description"),
                input_schema=tool["input_schema"],
                is_active=tool["is_active"],
                created_at=tool["created_at"],
                server=server_info,
            )
            result.append(tool_with_server)
        
        return result
    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tools/{tool_id}", response_model=MCPToolWithServer)
async def get_tool(
    tool_id: UUID,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPToolWithServer:
    """Get an MCP tool by ID."""
    try:
        tool = await mcp_service.get_tool(tool_id)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tool not found"
            )
        
        # Extract server info
        server_info = {
            "id": tool["server_id"],
            "name": tool.get("server_name"),
            "url": tool.get("server_url"),
        }
        
        return MCPToolWithServer(
            id=tool["id"],
            server_id=tool["server_id"],
            api_key_id=tool.get("api_key_id"),
            name=tool["name"],
            description=tool.get("description"),
            input_schema=tool["input_schema"],
            is_active=tool["is_active"],
            created_at=tool["created_at"],
            server=server_info,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/tools/{tool_id}/execute", response_model=MCPToolExecutionResponse)
async def execute_tool(
    tool_id: UUID,
    request: MCPToolExecutionRequest,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPToolExecutionResponse:
    """Execute an MCP tool."""
    try:
        # Record execution start
        execution_id = await mcp_service.execute_tool(
            tool_id=tool_id,
            input=request.input,
            conversation_id=request.conversation_id,
        )
        
        # Note: Actual tool execution would happen here via MCP transport
        # For now, we just record the execution
        
        return MCPToolExecutionResponse(
            id=execution_id,
            tool_id=tool_id,
            conversation_id=request.conversation_id,
            input=request.input,
            output=None,  # Would be filled by actual execution
            error=None,
            duration_ms=None,
            executed_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"Error executing MCP tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tools/{tool_id}/history", response_model=List[MCPToolExecution])
async def get_tool_history(
    tool_id: UUID,
    limit: int = 100,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> List[MCPToolExecution]:
    """Get tool execution history."""
    try:
        executions = await mcp_service.get_tool_history(
            tool_id=tool_id,
            limit=limit,
        )
        return [MCPToolExecution(**e) for e in executions]
    except Exception as e:
        logger.error(f"Error getting tool history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============= Resource Endpoints =============

@router.get("/resources", response_model=List[MCPResource])
async def list_resources(
    server_id: Optional[UUID] = None,
    api_key_id: Optional[UUID] = None,
    is_active: bool = True,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> List[MCPResource]:
    """List all MCP resources."""
    try:
        resources = await mcp_service.list_resources(
            server_id=server_id,
            api_key_id=api_key_id,
            is_active=is_active,
        )
        return [MCPResource(**r) for r in resources]
    except Exception as e:
        logger.error(f"Error listing MCP resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/resources/{resource_id}", response_model=MCPResource)
async def get_resource(
    resource_id: UUID,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPResource:
    """Get an MCP resource by ID."""
    try:
        resource = await mcp_service.get_resource(resource_id)
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        return MCPResource(**resource)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP resource: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/resources/{resource_id}/content")
async def get_resource_content(
    resource_id: UUID,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> dict:
    """Get resource content."""
    try:
        resource = await mcp_service.get_resource(resource_id)
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        # Note: Actual content fetching would happen here via MCP transport
        # For now, return resource info
        return {"resource": resource, "content": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resource content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============= Prompt Endpoints =============

@router.get("/prompts", response_model=List[MCPPrompt])
async def list_prompts(
    server_id: Optional[UUID] = None,
    api_key_id: Optional[UUID] = None,
    is_active: bool = True,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> List[MCPPrompt]:
    """List all MCP prompts."""
    try:
        prompts = await mcp_service.list_prompts(
            server_id=server_id,
            api_key_id=api_key_id,
            is_active=is_active,
        )
        return [MCPPrompt(**p) for p in prompts]
    except Exception as e:
        logger.error(f"Error listing MCP prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/prompts/{prompt_id}", response_model=MCPPrompt)
async def get_prompt(
    prompt_id: UUID,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPPrompt:
    """Get an MCP prompt by ID."""
    try:
        prompt = await mcp_service.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found"
            )
        return MCPPrompt(**prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/prompts/{prompt_id}/render")
async def render_prompt(
    prompt_id: UUID,
    arguments: dict,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> dict:
    """Render a prompt with arguments."""
    try:
        prompt = await mcp_service.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found"
            )
        
        # Note: Actual prompt rendering would happen here via MCP transport
        # For now, return prompt info
        return {"prompt": prompt, "arguments": arguments, "rendered": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )