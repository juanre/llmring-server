"""Models for conversation and message tracking."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationBase(BaseModel):
    """Base model for conversations."""
    
    title: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = None
    model_alias: str = Field("default", max_length=255)
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)


class ConversationCreate(ConversationBase):
    """Model for creating a conversation."""
    
    project_id: Optional[UUID] = Field(None, description="Project that owns this conversation (NULL for local usage)")


class ConversationUpdate(BaseModel):
    """Model for updating a conversation."""
    
    title: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = None
    model_alias: Optional[str] = Field(None, max_length=255)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)


class Conversation(ConversationBase):
    """Full conversation model."""
    
    id: UUID
    project_id: Optional[UUID]  # NULL for local usage
    message_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class MessageBase(BaseModel):
    """Base model for messages."""
    
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: Optional[str] = None  # Can be None if privacy mode
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageCreate(MessageBase):
    """Model for creating a message."""
    
    conversation_id: Optional[UUID] = None  # Set by server/batch
    receipt_id: Optional[UUID] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class Message(MessageBase):
    """Full message model."""
    
    id: UUID
    conversation_id: UUID
    receipt_id: Optional[UUID] = None
    content_hash: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ConversationWithMessages(Conversation):
    """Conversation with its messages."""
    
    messages: List[Message] = Field(default_factory=list)


class MessageBatch(BaseModel):
    """Model for batch message operations."""
    
    conversation_id: UUID
    messages: List[MessageCreate]
    create_receipt: bool = True
    logging_level: str = "full"  # none, metadata, full