"""Models for conversation templates."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationTemplateBase(BaseModel):
    """Base model for conversation templates."""
    
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: str = Field("claude-3-sonnet-20240229", max_length=255)
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)
    tool_config: Dict[str, Any] = Field(default_factory=dict)


class ConversationTemplateCreate(ConversationTemplateBase):
    """Model for creating a conversation template."""
    
    project_id: Optional[UUID] = Field(None, description="Project that owns this template")
    created_by: str = Field(..., max_length=255, description="User who created this template")


class ConversationTemplateUpdate(BaseModel):
    """Model for updating a conversation template."""
    
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = Field(None, max_length=255)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)
    tool_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ConversationTemplate(ConversationTemplateBase):
    """Full conversation template model."""
    
    id: UUID
    project_id: Optional[UUID]  # NULL for global templates
    created_by: str
    is_active: bool = True
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class ConversationTemplateStats(BaseModel):
    """Statistics for a conversation template."""
    
    template_id: UUID
    template_name: str
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime