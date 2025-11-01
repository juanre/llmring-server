"""MCP (Model Context Protocol) models for llmring-server."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ============= MCP Server Models =============


class MCPServerBase(BaseModel):
    """Base model for MCP servers."""

    name: str = Field(..., description="Server name")
    url: str = Field(..., description="Server URL")
    transport_type: str = Field(..., description="Transport type: stdio, http, websocket")
    auth_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Authentication configuration"
    )
    capabilities: Optional[Dict[str, Any]] = Field(default=None, description="Server capabilities")
    is_active: bool = Field(default=True, description="Whether server is active")


class MCPServerCreate(MCPServerBase):
    """Model for creating an MCP server."""

    api_key_id: Optional[str] = None


class MCPServerUpdate(BaseModel):
    """Model for updating an MCP server."""

    name: Optional[str] = None
    url: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    capabilities: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class MCPServer(MCPServerBase):
    """MCP server response model."""

    id: UUID
    api_key_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ============= MCP Tool Models =============


class MCPToolBase(BaseModel):
    """Base model for MCP tools."""

    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for tool input")
    is_active: bool = Field(default=True, description="Whether tool is active")


class MCPToolCreate(MCPToolBase):
    """Model for creating an MCP tool."""

    server_id: UUID = Field(..., description="Associated MCP server ID")
    api_key_id: Optional[str] = None


class MCPToolUpdate(BaseModel):
    """Model for updating an MCP tool."""

    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class MCPTool(MCPToolBase):
    """MCP tool response model."""

    id: UUID
    server_id: UUID
    api_key_id: Optional[str] = None
    created_at: datetime


class MCPToolWithServer(MCPTool):
    """MCP tool with server information."""

    server: Optional[Dict[str, Any]] = None  # Can be partial server info


# ============= MCP Resource Models =============


class MCPResourceBase(BaseModel):
    """Base model for MCP resources."""

    uri: str = Field(..., description="Resource URI")
    name: Optional[str] = Field(None, description="Resource name")
    description: Optional[str] = Field(None, description="Resource description")
    mime_type: Optional[str] = Field(None, description="MIME type")
    is_active: bool = Field(default=True, description="Whether resource is active")


class MCPResourceCreate(MCPResourceBase):
    """Model for creating an MCP resource."""

    server_id: UUID = Field(..., description="Associated MCP server ID")
    api_key_id: Optional[str] = None


class MCPResourceUpdate(BaseModel):
    """Model for updating an MCP resource."""

    name: Optional[str] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    is_active: Optional[bool] = None


class MCPResource(MCPResourceBase):
    """MCP resource response model."""

    id: UUID
    server_id: UUID
    api_key_id: Optional[str] = None
    created_at: datetime


# ============= MCP Prompt Models =============


class MCPPromptBase(BaseModel):
    """Base model for MCP prompts."""

    name: str = Field(..., description="Prompt name")
    description: Optional[str] = Field(None, description="Prompt description")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Prompt arguments schema")
    is_active: bool = Field(default=True, description="Whether prompt is active")


class MCPPromptCreate(MCPPromptBase):
    """Model for creating an MCP prompt."""

    server_id: UUID = Field(..., description="Associated MCP server ID")
    api_key_id: Optional[str] = None


class MCPPromptUpdate(BaseModel):
    """Model for updating an MCP prompt."""

    description: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class MCPPrompt(MCPPromptBase):
    """MCP prompt response model."""

    id: UUID
    server_id: UUID
    api_key_id: Optional[str] = None
    created_at: datetime


# ============= Tool Execution Models =============


class MCPToolExecutionRequest(BaseModel):
    """Request to record an MCP tool execution.

    Note: This records execution metadata for observability.
    Actual tool execution happens client-side via AsyncMCPClient.
    """

    input: Dict[str, Any] = Field(..., description="Tool input arguments")
    output: Optional[Dict[str, Any]] = Field(
        None, description="Tool output (if execution completed)"
    )
    error: Optional[str] = Field(None, description="Error message (if execution failed)")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    conversation_id: Optional[UUID] = Field(None, description="Associated conversation ID")


class MCPToolExecutionResponse(BaseModel):
    """Response from MCP tool execution."""

    id: UUID
    tool_id: UUID
    conversation_id: Optional[UUID] = None
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    executed_at: datetime


class MCPToolExecution(BaseModel):
    """MCP tool execution history record."""

    id: UUID
    tool_id: UUID
    conversation_id: Optional[UUID] = None
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    executed_at: datetime


# ============= Aggregated Models =============


class MCPCapabilities(BaseModel):
    """MCP server capabilities response."""

    tools: List[MCPTool] = Field(default_factory=list)
    resources: List[MCPResource] = Field(default_factory=list)
    prompts: List[MCPPrompt] = Field(default_factory=list)
    server: MCPServer
