# ABOUTME: FastAPI router for conversation and message management endpoints.
# ABOUTME: Handles conversation CRUD, message batching, and configurable message logging levels.

"""API routes for conversation and message management."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pgdbm import AsyncDatabaseManager

from llmring_server.config import Settings
from llmring_server.dependencies import get_auth_context, get_db, get_settings
from llmring_server.models.conversations import (
    Conversation,
    ConversationCreate,
    ConversationLogRequest,
    ConversationLogResponse,
    ConversationUpdate,
    ConversationWithMessages,
    Message,
    MessageBatch,
)
from llmring_server.services.conversations import ConversationService

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("/", response_model=Conversation)
async def create_conversation(
    conversation_data: ConversationCreate,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Conversation:
    """Create a new conversation."""
    if not settings.enable_conversation_tracking:
        raise HTTPException(400, "Conversation tracking is disabled")

    service = ConversationService(db, settings)

    # For creation, we need an api_key_id to associate with the conversation
    # API key auth provides it directly
    if auth_context["type"] == "api_key":
        conversation_data.api_key_id = auth_context["api_key_id"]
    else:
        conversation_data.project_id = auth_context["project_id"]

    result = await service.create_conversation(conversation_data)
    if not result:
        raise HTTPException(500, "Failed to create conversation")

    return result


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: UUID,
    include_messages: bool = Query(True, description="Include messages in response"),
    message_limit: int = Query(100, ge=1, le=1000, description="Maximum messages to return"),
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConversationWithMessages:
    """Get a conversation with optional messages."""
    service = ConversationService(db, settings)

    if include_messages:
        if auth_context["type"] == "api_key":
            result = await service.get_conversation_with_messages(
                conversation_id, api_key_id=auth_context["api_key_id"], message_limit=message_limit
            )
        else:
            result = await service.get_conversation_with_messages(
                conversation_id,
                user_id=auth_context["user_id"],
                project_id=auth_context["project_id"],
                message_limit=message_limit,
            )
    else:
        if auth_context["type"] == "api_key":
            conversation = await service.get_conversation(
                conversation_id, api_key_id=auth_context["api_key_id"]
            )
        else:
            conversation = await service.get_conversation(
                conversation_id,
                user_id=auth_context["user_id"],
                project_id=auth_context["project_id"],
            )

        if conversation:
            result = ConversationWithMessages(**conversation.model_dump(), messages=[])
        else:
            result = None

    if not result:
        raise HTTPException(404, "Conversation not found")

    return result


@router.patch("/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: UUID,
    update_data: ConversationUpdate,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Conversation:
    """Update a conversation."""
    service = ConversationService(db, settings)

    if auth_context["type"] == "api_key":
        result = await service.update_conversation(
            conversation_id, update_data, api_key_id=auth_context["api_key_id"]
        )
    else:
        result = await service.update_conversation(
            conversation_id,
            update_data,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not result:
        raise HTTPException(404, "Conversation not found")

    return result


@router.get("/", response_model=List[Conversation])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[Conversation]:
    """List conversations for the authenticated user."""
    if not settings.enable_conversation_tracking:
        return []

    service = ConversationService(db, settings)
    if auth_context["type"] == "api_key":
        return await service.list_conversations(
            api_key_id=auth_context["api_key_id"], limit=limit, offset=offset
        )
    else:
        return await service.list_conversations(
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
            limit=limit,
            offset=offset,
        )


@router.get("/{conversation_id}/messages", response_model=List[Message])
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[Message]:
    """Get messages for a conversation."""
    service = ConversationService(db, settings)

    # Verify conversation belongs to user
    if auth_context["type"] == "api_key":
        conversation = await service.get_conversation(
            conversation_id, api_key_id=auth_context["api_key_id"]
        )
    else:
        conversation = await service.get_conversation(
            conversation_id,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not conversation:
        raise HTTPException(404, "Conversation not found")

    return await service.get_conversation_messages(conversation_id, limit=limit, offset=offset)


@router.post("/{conversation_id}/messages/batch", response_model=List[Message])
async def add_messages_batch(
    conversation_id: UUID,
    batch: MessageBatch,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[Message]:
    """Add multiple messages to a conversation."""
    if settings.message_logging_level == "none":
        raise HTTPException(400, "Message logging is disabled")

    service = ConversationService(db, settings)

    # Verify conversation belongs to user
    if auth_context["type"] == "api_key":
        conversation = await service.get_conversation(
            conversation_id, api_key_id=auth_context["api_key_id"]
        )
    else:
        conversation = await service.get_conversation(
            conversation_id,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not conversation:
        raise HTTPException(404, "Conversation not found")

    # Ensure batch conversation_id matches
    batch.conversation_id = conversation_id

    return await service.add_messages_batch(batch)


@router.delete("/old-messages")
async def cleanup_old_messages(
    retention_days: Optional[int] = Query(None, description="Override default retention days"),
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Clean up old messages based on retention policy (admin only)."""
    # Admin check should be added when role-based access control is implemented
    service = ConversationService(db, settings)

    deleted_count = await service.cleanup_old_messages(retention_days)

    return {
        "deleted_count": deleted_count,
        "retention_days": retention_days or settings.message_retention_days,
    }


@router.post("/log", response_model=ConversationLogResponse)
async def log_conversation(
    log_request: ConversationLogRequest,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConversationLogResponse:
    """
    Log a full conversation with messages and response.

    This endpoint is used by the llmring decorators and LoggingService
    to store complete conversations including messages, responses, and metadata.

    The conversation will be stored with:
    - All input messages
    - The assistant's response
    - Usage metadata (tokens, cost)
    - Provider and model information

    This ensures complete cost tracking and audit trail.
    """
    if not settings.enable_conversation_tracking:
        raise HTTPException(400, "Conversation tracking is disabled")

    conversation_service = ConversationService(db, settings)

    # For logging, we need an api_key_id to associate with the conversation
    # API key auth provides it directly
    api_key_id = auth_context.get("api_key_id")
    project_id = auth_context.get("project_id") if auth_context["type"] == "user" else None

    result = await conversation_service.log_conversation(
        api_key_id=api_key_id,
        messages=log_request.messages,
        response=log_request.response,
        metadata=log_request.metadata.model_dump(),
        project_id=project_id,
    )

    conversation_id = result["conversation_id"]

    return ConversationLogResponse(
        conversation_id=conversation_id,
        message_id=result["message_id"],
    )
