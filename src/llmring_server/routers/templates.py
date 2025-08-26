"""API routes for conversation templates."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pgdbm import AsyncDatabaseManager

from llmring_server.dependencies import get_project_id, get_db
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
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Create a new conversation template."""
    service = TemplateService(db)
    
    # Override project_id with authenticated value
    template_data.project_id = project_id
    
    result = await service.create_template(template_data)
    if not result:
        raise HTTPException(500, "Failed to create template")
    
    return result


@router.get("/", response_model=List[ConversationTemplate])
async def list_templates(
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(50, ge=1, le=100, description="Maximum templates to return"),
    offset: int = Query(0, ge=0, description="Number of templates to skip"),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> List[ConversationTemplate]:
    """List conversation templates."""
    service = TemplateService(db)
    return await service.list_templates(
        project_id=project_id,
        created_by=created_by,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=List[ConversationTemplateStats])
async def get_template_stats(
    limit: int = Query(20, ge=1, le=50, description="Maximum templates to return"),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> List[ConversationTemplateStats]:
    """Get usage statistics for conversation templates."""
    service = TemplateService(db)
    return await service.get_template_stats(project_id=project_id, limit=limit)


@router.get("/{template_id}", response_model=ConversationTemplate)
async def get_template(
    template_id: UUID,
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Get a conversation template by ID."""
    service = TemplateService(db)
    
    result = await service.get_template(template_id, project_id)
    if not result:
        raise HTTPException(404, "Template not found")
    
    return result


@router.put("/{template_id}", response_model=ConversationTemplate)
async def update_template(
    template_id: UUID,
    update_data: ConversationTemplateUpdate,
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Update a conversation template."""
    service = TemplateService(db)
    
    result = await service.update_template(template_id, update_data, project_id)
    if not result:
        raise HTTPException(404, "Template not found")
    
    return result


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> dict:
    """Delete a conversation template."""
    service = TemplateService(db)
    
    success = await service.delete_template(template_id, project_id)
    if not success:
        raise HTTPException(404, "Template not found")
    
    return {"message": "Template deleted successfully"}


@router.post("/{template_id}/use", response_model=ConversationTemplate)
async def use_template(
    template_id: UUID,
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> ConversationTemplate:
    """Mark a template as used and update usage statistics."""
    service = TemplateService(db)
    
    result = await service.use_template(template_id, project_id)
    if not result:
        raise HTTPException(404, "Template not found")
    
    return result