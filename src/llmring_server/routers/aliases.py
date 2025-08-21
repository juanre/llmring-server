from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from pgdbm import AsyncDatabaseManager

from llmring_server.dependencies import get_project_id, get_db
from llmring_server.models.aliases import Alias, AliasRequest, BindRequest
from llmring_server.services.aliases import AliasesService

router = APIRouter(prefix="/api/v1/aliases", tags=["aliases"])


@router.get("/", response_model=List[Alias])
async def list_aliases(
    profile: Optional[str] = Query(None),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = AliasesService(db)
    return await service.list_aliases(project_id, profile)


@router.post("/bind", response_model=Alias)
async def bind_alias(
    body: BindRequest, 
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    """Canonical bind endpoint per source-of-truth: bind alias->model."""
    service = AliasesService(db)
    return await service.upsert_alias(
        project_id, body.alias, body.model, body.metadata, profile=body.profile
    )


@router.get("/resolve")
async def resolve_alias(
    alias: str = Query(...),
    profile: str = Query("default"),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = AliasesService(db)
    result = await service.get_alias(project_id, alias, profile)
    return {"alias": alias, "model": result.model if result else None}


@router.get("/{alias}", response_model=Alias)
async def get_alias(
    alias: str = Path(...),
    profile: str = Query("default"),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = AliasesService(db)
    result = await service.get_alias(project_id, alias, profile)
    return result


@router.put("/{alias}", response_model=Alias)
async def upsert_alias(
    alias: str,
    body: AliasRequest,
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = AliasesService(db)
    return await service.upsert_alias(
        project_id, alias, body.model, body.metadata, profile=body.profile
    )


@router.delete("/{alias}")
async def delete_alias(
    alias: str,
    profile: str = Query("default"),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = AliasesService(db)
    ok = await service.delete_alias(project_id, alias, profile)
    return {"deleted": ok}


@router.post("/bulk_upsert")
async def bulk_upsert(
    profile: str = Query("default"),
    items: Optional[List[BindRequest]] = Body(default=None),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = AliasesService(db)
    payload = (
        [
            {"alias": it.alias, "model": it.model, "metadata": it.metadata}
            for it in items
        ]
        if items
        else []
    )
    count = await service.bulk_upsert(project_id, profile, payload)
    return {"updated": count}
