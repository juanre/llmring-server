# ABOUTME: Pydantic models for conversation templates with reusable settings.
# ABOUTME: Defines template creation, updates, and usage tracking for conversation presets.

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

    api_key_id: Optional[str] = Field(
        None, max_length=255, description="API key that owns this template"
    )
    project_id: Optional[str] = Field(
        None, description="Project that owns this template for user-auth flows"
    )
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
    api_key_id: Optional[str]  # NULL for global templates
    project_id: Optional[str] = None
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
