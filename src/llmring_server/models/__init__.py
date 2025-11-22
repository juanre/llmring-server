"""Pydantic models for llmring-server API validation and responses. Exports models for conversations, MCP, registry, and usage tracking."""

"""Models for llmring-server."""

from llmring_server.models.conversations import (
    Conversation,
    ConversationBase,
    ConversationCreate,
    ConversationUpdate,
    ConversationWithMessages,
    Message,
    MessageBase,
    MessageBatch,
    MessageCreate,
)
from llmring_server.models.mcp import (
    MCPCapabilities,
    MCPPrompt,
    MCPPromptBase,
    MCPPromptCreate,
    MCPPromptUpdate,
    MCPResource,
    MCPResourceBase,
    MCPResourceCreate,
    MCPResourceUpdate,
    MCPServer,
    MCPServerBase,
    MCPServerCreate,
    MCPServerUpdate,
    MCPTool,
    MCPToolBase,
    MCPToolCreate,
    MCPToolExecution,
    MCPToolExecutionRequest,
    MCPToolExecutionResponse,
    MCPToolUpdate,
    MCPToolWithServer,
)
from llmring_server.models.registry import LLMModel, ProviderInfo, RegistryResponse
from llmring_server.models.usage import (
    DailyUsage,
    ModelUsage,
    UsageLogRequest,
    UsageLogResponse,
    UsageStats,
    UsageSummary,
)

__all__ = [
    # Conversations
    "Conversation",
    "ConversationBase",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationWithMessages",
    "Message",
    "MessageBase",
    "MessageBatch",
    "MessageCreate",
    # MCP
    "MCPServer",
    "MCPServerBase",
    "MCPServerCreate",
    "MCPServerUpdate",
    "MCPTool",
    "MCPToolBase",
    "MCPToolCreate",
    "MCPToolUpdate",
    "MCPToolWithServer",
    "MCPResource",
    "MCPResourceBase",
    "MCPResourceCreate",
    "MCPResourceUpdate",
    "MCPPrompt",
    "MCPPromptBase",
    "MCPPromptCreate",
    "MCPPromptUpdate",
    "MCPToolExecution",
    "MCPToolExecutionRequest",
    "MCPToolExecutionResponse",
    "MCPCapabilities",
    # Registry
    "LLMModel",
    "ProviderInfo",
    "RegistryResponse",
    # Usage
    "UsageLogRequest",
    "UsageLogResponse",
    "UsageSummary",
    "DailyUsage",
    "ModelUsage",
    "UsageStats",
]
