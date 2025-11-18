# ABOUTME: FastAPI router for conversation template management.
# ABOUTME: Handles template CRUD operations and tracks template usage statistics.

"""API routes for conversation templates."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pgdbm import AsyncDatabaseManager

from llmring_server.dependencies import get_auth_context, get_db
from llmring_server.models.templates import (
    ConversationTemplate,
    ConversationTemplateCreate,
    ConversationTemplateStats,
    ConversationTemplateUpdate,
)
from llmring_server.services.templates import TemplateService

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.post("/", response_model=ConversationTemplate)
async def create_template(
    template_data: ConversationTemplateCreate,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Create a new conversation template."""
    service = TemplateService(db)

    # Override api_key_id with authenticated value
    if auth_context["type"] == "api_key":
        template_data.api_key_id = auth_context["api_key_id"]
    else:
        # For user auth, we need to get the first active API key for the project
        # This query gets the first active API key associated with the project
        query = """
        SELECT id::text as api_key_id
        FROM llmring_api.api_keys
        WHERE project_id = $1 AND is_active = true
        LIMIT 1
        """
        result = await db.fetch_one(query, auth_context["project_id"])
        if not result:
            raise HTTPException(400, "No active API key found for project")
        template_data.api_key_id = result["api_key_id"]

    result = await service.create_template(template_data)
    if not result:
        raise HTTPException(500, "Failed to create template")

    return result


@router.get("/", response_model=List[ConversationTemplate])
async def list_templates(
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(50, ge=1, le=100, description="Maximum templates to return"),
    offset: int = Query(0, ge=0, description="Number of templates to skip"),
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> List[ConversationTemplate]:
    """List conversation templates."""
    service = TemplateService(db)

    if auth_context["type"] == "api_key":
        return await service.list_templates(
            api_key_id=auth_context["api_key_id"],
            created_by=created_by,
            limit=limit,
            offset=offset,
        )
    else:
        return await service.list_templates(
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
            created_by=created_by,
            limit=limit,
            offset=offset,
        )


@router.get("/stats", response_model=List[ConversationTemplateStats])
async def get_template_stats(
    limit: int = Query(20, ge=1, le=50, description="Maximum templates to return"),
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> List[ConversationTemplateStats]:
    """Get usage statistics for conversation templates."""
    service = TemplateService(db)

    if auth_context["type"] == "api_key":
        return await service.get_template_stats(api_key_id=auth_context["api_key_id"], limit=limit)
    else:
        return await service.get_template_stats(
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
            limit=limit,
        )


@router.get("/{template_id}", response_model=ConversationTemplate)
async def get_template(
    template_id: UUID,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Get a conversation template by ID."""
    service = TemplateService(db)

    if auth_context["type"] == "api_key":
        result = await service.get_template(template_id, api_key_id=auth_context["api_key_id"])
    else:
        result = await service.get_template(
            template_id,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not result:
        raise HTTPException(404, "Template not found")

    return result


@router.put("/{template_id}", response_model=ConversationTemplate)
async def update_template(
    template_id: UUID,
    update_data: ConversationTemplateUpdate,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Update a conversation template."""
    service = TemplateService(db)

    if auth_context["type"] == "api_key":
        result = await service.update_template(
            template_id, update_data, api_key_id=auth_context["api_key_id"]
        )
    else:
        result = await service.update_template(
            template_id,
            update_data,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not result:
        raise HTTPException(404, "Template not found")

    return result


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> dict:
    """Delete a conversation template."""
    service = TemplateService(db)

    if auth_context["type"] == "api_key":
        success = await service.delete_template(template_id, api_key_id=auth_context["api_key_id"])
    else:
        success = await service.delete_template(
            template_id,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not success:
        raise HTTPException(404, "Template not found")

    return {"message": "Template deleted successfully"}


@router.post("/{template_id}/use", response_model=ConversationTemplate)
async def use_template(
    template_id: UUID,
    auth_context: dict = Depends(get_auth_context),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Mark a template as used and update usage statistics."""
    service = TemplateService(db)

    if auth_context["type"] == "api_key":
        result = await service.use_template(template_id, api_key_id=auth_context["api_key_id"])
    else:
        result = await service.use_template(
            template_id,
            user_id=auth_context["user_id"],
            project_id=auth_context["project_id"],
        )

    if not result:
        raise HTTPException(404, "Template not found")

    return result
