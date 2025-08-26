"""MCP (Model Context Protocol) service for llmring-server."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pgdbm import AsyncDatabaseManager

logger = logging.getLogger(__name__)


class MCPService:
    """Service for managing MCP servers, tools, resources, and prompts."""
    
    def __init__(self, db: AsyncDatabaseManager):
        """Initialize the MCP service.
        
        Args:
            db: Database manager instance
        """
        self.db = db
    
    # ============= MCP Server Management =============
    
    async def create_server(
        self,
        name: str,
        url: str,
        transport_type: str,
        auth_config: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        api_key_id: Optional[str] = None,
    ) -> UUID:
        """Create a new MCP server.
        
        Args:
            name: Server name
            url: Server URL
            transport_type: Transport type (stdio, http, websocket)
            auth_config: Authentication configuration
            capabilities: Server capabilities
            api_key_id: Optional project ID
            
        Returns:
            Server ID
        """
        query = """
            INSERT INTO mcp_client.servers (
                name, url, transport_type, auth_config, capabilities, api_key_id
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """
        
        result = await self.db.fetch_one(
            query, 
            name, 
            url, 
            transport_type, 
            json.dumps(auth_config) if auth_config else None,
            json.dumps(capabilities) if capabilities else None, 
            api_key_id
        )
        return result["id"]
    
    async def get_server(self, server_id: UUID, api_key_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get an MCP server by ID.
        
        Args:
            server_id: Server ID
            api_key_id: Optional API key ID for filtering
            
        Returns:
            Server data or None
        """
        query = """
            SELECT * FROM mcp_client.servers
            WHERE id = $1
        """
        params = [server_id]
        
        if api_key_id is not None:
            query += " AND api_key_id = $2"
            params.append(api_key_id)
        
        result = await self.db.fetch_one(query, *params)
        if not result:
            return None
        
        # Convert to dict and parse JSON fields
        server = dict(result)
        if server.get('auth_config') and isinstance(server['auth_config'], str):
            server['auth_config'] = json.loads(server['auth_config'])
        if server.get('capabilities') and isinstance(server['capabilities'], str):
            server['capabilities'] = json.loads(server['capabilities'])
        return server
    
    async def list_servers(
        self,
        api_key_id: Optional[str] = None,
        is_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """List MCP servers.
        
        Args:
            api_key_id: Filter by project ID
            is_active: Filter by active status
            
        Returns:
            List of servers
        """
        query = """
            SELECT * FROM mcp_client.servers
            WHERE is_active = $1
        """
        params = [is_active]
        
        if api_key_id is not None:
            query += " AND api_key_id = $2"
            params.append(api_key_id)
        else:
            query += " AND api_key_id IS NULL"
        
        query += " ORDER BY created_at DESC"
        
        results = await self.db.fetch_all(query, *params)
        servers = []
        for r in results:
            server = dict(r)
            if server.get('auth_config') and isinstance(server['auth_config'], str):
                server['auth_config'] = json.loads(server['auth_config'])
            if server.get('capabilities') and isinstance(server['capabilities'], str):
                server['capabilities'] = json.loads(server['capabilities'])
            servers.append(server)
        return servers
    
    async def update_server(
        self,
        server_id: UUID,
        name: Optional[str] = None,
        url: Optional[str] = None,
        auth_config: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """Update an MCP server.
        
        Args:
            server_id: Server ID
            name: New name
            url: New URL
            auth_config: New auth configuration
            capabilities: New capabilities
            is_active: New active status
            
        Returns:
            True if updated
        """
        updates = []
        values = []
        param_count = 0
        
        if name is not None:
            param_count += 1
            updates.append(f"name = ${param_count}")
            values.append(name)
        
        if url is not None:
            param_count += 1
            updates.append(f"url = ${param_count}")
            values.append(url)
        
        if auth_config is not None:
            param_count += 1
            updates.append(f"auth_config = ${param_count}")
            values.append(json.dumps(auth_config) if auth_config else None)
        
        if capabilities is not None:
            param_count += 1
            updates.append(f"capabilities = ${param_count}")
            values.append(json.dumps(capabilities) if capabilities else None)
        
        if is_active is not None:
            param_count += 1
            updates.append(f"is_active = ${param_count}")
            values.append(is_active)
        
        if not updates:
            return False
        
        param_count += 1
        values.append(server_id)
        
        query = f"""
            UPDATE mcp_client.servers
            SET {', '.join(updates)}
            WHERE id = ${param_count}
        """
        
        await self.db.execute(query, *values)
        return True
    
    async def delete_server(self, server_id: UUID) -> bool:
        """Delete an MCP server.
        
        Args:
            server_id: Server ID
            
        Returns:
            True if deleted
        """
        query = "DELETE FROM mcp_client.servers WHERE id = $1"
        await self.db.execute(query, server_id)
        return True
    
    async def refresh_server_capabilities(
        self,
        server_id: UUID,
        tools: List[Dict[str, Any]],
        resources: List[Dict[str, Any]],
        prompts: List[Dict[str, Any]],
    ) -> bool:
        """Refresh server capabilities by updating tools, resources, and prompts.
        
        Args:
            server_id: Server ID
            tools: List of tools
            resources: List of resources
            prompts: List of prompts
            
        Returns:
            True if refreshed
        """
        # Start transaction
        async with self.db.transaction():
            # Delete existing tools, resources, prompts
            await self.db.execute(
                "DELETE FROM mcp_client.tools WHERE server_id = $1", server_id
            )
            await self.db.execute(
                "DELETE FROM mcp_client.resources WHERE server_id = $1", server_id
            )
            await self.db.execute(
                "DELETE FROM mcp_client.prompts WHERE server_id = $1", server_id
            )
            
            # Insert new tools
            for tool in tools:
                await self.db.execute(
                    """
                    INSERT INTO mcp_client.tools (
                        server_id, name, description, input_schema
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    server_id,
                    tool["name"],
                    tool.get("description"),
                    tool.get("inputSchema", {}),
                )
            
            # Insert new resources
            for resource in resources:
                await self.db.execute(
                    """
                    INSERT INTO mcp_client.resources (
                        server_id, uri, name, description, mime_type
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    server_id,
                    resource["uri"],
                    resource.get("name"),
                    resource.get("description"),
                    resource.get("mimeType"),
                )
            
            # Insert new prompts
            for prompt in prompts:
                await self.db.execute(
                    """
                    INSERT INTO mcp_client.prompts (
                        server_id, name, description, arguments
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    server_id,
                    prompt["name"],
                    prompt.get("description"),
                    prompt.get("arguments"),
                )
            
            # Update server capabilities
            await self.db.execute(
                """
                UPDATE mcp_client.servers
                SET capabilities = $1, updated_at = $2
                WHERE id = $3
                """,
                {
                    "tools": len(tools),
                    "resources": len(resources),
                    "prompts": len(prompts),
                },
                datetime.utcnow(),
                server_id,
            )
        
        return True
    
    # ============= Tool Management =============
    
    async def create_tool(
        self,
        server_id: UUID,
        name: str,
        description: Optional[str] = None,
        input_schema: Dict[str, Any] = None,
        api_key_id: Optional[str] = None,
    ) -> UUID:
        """Create a new MCP tool.
        
        Args:
            server_id: Server ID
            name: Tool name
            description: Tool description
            input_schema: JSON schema for tool input
            api_key_id: Optional API key ID
            
        Returns:
            Tool ID
        """
        query = """
            INSERT INTO mcp_client.tools (
                server_id, name, description, input_schema, api_key_id
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        
        result = await self.db.fetch_one(
            query,
            server_id,
            name,
            description,
            json.dumps(input_schema) if input_schema else None,
            api_key_id
        )
        return result["id"]
    
    async def list_tools(
        self,
        server_id: Optional[UUID] = None,
        api_key_id: Optional[str] = None,
        is_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """List MCP tools.
        
        Args:
            server_id: Filter by server ID
            api_key_id: Filter by project ID
            is_active: Filter by active status
            
        Returns:
            List of tools
        """
        query = """
            SELECT t.*, s.name as server_name, s.url as server_url
            FROM mcp_client.tools t
            JOIN mcp_client.servers s ON t.server_id = s.id
            WHERE t.is_active = $1
        """
        params = [is_active]
        param_count = 1
        
        if server_id is not None:
            param_count += 1
            query += f" AND t.server_id = ${param_count}"
            params.append(server_id)
        
        if api_key_id is not None:
            param_count += 1
            query += f" AND t.api_key_id = ${param_count}"
            params.append(api_key_id)
        else:
            query += " AND t.api_key_id IS NULL"
        
        query += " ORDER BY t.name"
        
        results = await self.db.fetch_all(query, *params)
        tools = []
        for r in results:
            tool = dict(r)
            if tool.get('input_schema') and isinstance(tool['input_schema'], str):
                tool['input_schema'] = json.loads(tool['input_schema'])
            tools.append(tool)
        return tools
    
    async def get_tool(self, tool_id: UUID) -> Optional[Dict[str, Any]]:
        """Get an MCP tool by ID.
        
        Args:
            tool_id: Tool ID
            
        Returns:
            Tool data or None
        """
        query = """
            SELECT t.*, s.name as server_name, s.url as server_url
            FROM mcp_client.tools t
            JOIN mcp_client.servers s ON t.server_id = s.id
            WHERE t.id = $1
        """
        
        result = await self.db.fetch_one(query, tool_id)
        if not result:
            return None
        
        tool = dict(result)
        if tool.get('input_schema') and isinstance(tool['input_schema'], str):
            tool['input_schema'] = json.loads(tool['input_schema'])
        return tool
    
    async def execute_tool(
        self,
        tool_id: UUID,
        input: Dict[str, Any],
        conversation_id: Optional[UUID] = None,
    ) -> UUID:
        """Record tool execution.
        
        Args:
            tool_id: Tool ID
            input: Tool input
            conversation_id: Optional conversation ID
            
        Returns:
            Execution ID
        """
        query = """
            INSERT INTO mcp_client.tool_executions (
                tool_id, conversation_id, input
            ) VALUES ($1, $2, $3)
            RETURNING id
        """
        
        result = await self.db.fetch_one(query, tool_id, conversation_id, json.dumps(input) if input else None)
        return result["id"]
    
    async def update_tool_execution(
        self,
        execution_id: UUID,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> bool:
        """Update tool execution result.
        
        Args:
            execution_id: Execution ID
            output: Tool output
            error: Error message
            duration_ms: Execution duration
            
        Returns:
            True if updated
        """
        query = """
            UPDATE mcp_client.tool_executions
            SET output = $1, error = $2, duration_ms = $3
            WHERE id = $4
        """
        
        await self.db.execute(query, output, error, duration_ms, execution_id)
        return True
    
    async def get_tool_history(
        self,
        tool_id: UUID,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get tool execution history.
        
        Args:
            tool_id: Tool ID
            limit: Maximum results
            
        Returns:
            List of executions
        """
        query = """
            SELECT * FROM mcp_client.tool_executions
            WHERE tool_id = $1
            ORDER BY executed_at DESC
            LIMIT $2
        """
        
        results = await self.db.fetch_all(query, tool_id, limit)
        return [dict(r) for r in results]
    
    # ============= Resource Management =============
    
    async def list_resources(
        self,
        server_id: Optional[UUID] = None,
        api_key_id: Optional[str] = None,
        is_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """List MCP resources.
        
        Args:
            server_id: Filter by server ID
            api_key_id: Filter by project ID
            is_active: Filter by active status
            
        Returns:
            List of resources
        """
        query = """
            SELECT r.*, s.name as server_name, s.url as server_url
            FROM mcp_client.resources r
            JOIN mcp_client.servers s ON r.server_id = s.id
            WHERE r.is_active = $1
        """
        params = [is_active]
        param_count = 1
        
        if server_id is not None:
            param_count += 1
            query += f" AND r.server_id = ${param_count}"
            params.append(server_id)
        
        if api_key_id is not None:
            param_count += 1
            query += f" AND r.api_key_id = ${param_count}"
            params.append(api_key_id)
        else:
            query += " AND r.api_key_id IS NULL"
        
        query += " ORDER BY r.uri"
        
        results = await self.db.fetch_all(query, *params)
        return [dict(r) for r in results]
    
    async def get_resource(self, resource_id: UUID) -> Optional[Dict[str, Any]]:
        """Get an MCP resource by ID.
        
        Args:
            resource_id: Resource ID
            
        Returns:
            Resource data or None
        """
        query = """
            SELECT r.*, s.name as server_name, s.url as server_url
            FROM mcp_client.resources r
            JOIN mcp_client.servers s ON r.server_id = s.id
            WHERE r.id = $1
        """
        
        result = await self.db.fetch_one(query, resource_id)
        return dict(result) if result else None
    
    # ============= Prompt Management =============
    
    async def list_prompts(
        self,
        server_id: Optional[UUID] = None,
        api_key_id: Optional[str] = None,
        is_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """List MCP prompts.
        
        Args:
            server_id: Filter by server ID
            api_key_id: Filter by project ID
            is_active: Filter by active status
            
        Returns:
            List of prompts
        """
        query = """
            SELECT p.*, s.name as server_name, s.url as server_url
            FROM mcp_client.prompts p
            JOIN mcp_client.servers s ON p.server_id = s.id
            WHERE p.is_active = $1
        """
        params = [is_active]
        param_count = 1
        
        if server_id is not None:
            param_count += 1
            query += f" AND p.server_id = ${param_count}"
            params.append(server_id)
        
        if api_key_id is not None:
            param_count += 1
            query += f" AND p.api_key_id = ${param_count}"
            params.append(api_key_id)
        else:
            query += " AND p.api_key_id IS NULL"
        
        query += " ORDER BY p.name"
        
        results = await self.db.fetch_all(query, *params)
        return [dict(r) for r in results]
    
    async def get_prompt(self, prompt_id: UUID) -> Optional[Dict[str, Any]]:
        """Get an MCP prompt by ID.
        
        Args:
            prompt_id: Prompt ID
            
        Returns:
            Prompt data or None
        """
        query = """
            SELECT p.*, s.name as server_name, s.url as server_url
            FROM mcp_client.prompts p
            JOIN mcp_client.servers s ON p.server_id = s.id
            WHERE p.id = $1
        """
        
        result = await self.db.fetch_one(query, prompt_id)
        return dict(result) if result else None