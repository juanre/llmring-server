from fastapi import APIRouter, Request, Path, Query
from typing import List, Optional

from llmring_server.models.aliases import Alias, AliasRequest, BindRequest
from llmring_server.services.aliases import AliasesService


router = APIRouter(prefix="/api/v1/aliases", tags=["aliases"]) 


@router.get("/", response_model=List[Alias])
async def list_aliases(request: Request):
    service = AliasesService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    return await service.list_aliases(project_id)


@router.post("/bind", response_model=Alias)
async def bind_alias(request: Request, body: BindRequest):
    """Canonical bind endpoint per source-of-truth: bind alias->model."""
    service = AliasesService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    return await service.upsert_alias(project_id, body.alias, body.model, body.metadata)


@router.get("/resolve")
async def resolve_alias(request: Request, alias: str = Query(...)):
    service = AliasesService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    result = await service.get_alias(project_id, alias)
    return {"alias": alias, "model": result.model if result else None}


@router.get("/{alias}", response_model=Alias)
async def get_alias(request: Request, alias: str = Path(...)):
    service = AliasesService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    result = await service.get_alias(project_id, alias)
    return result


@router.put("/{alias}", response_model=Alias)
async def upsert_alias(request: Request, alias: str, body: AliasRequest):
    service = AliasesService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    return await service.upsert_alias(project_id, alias, body.model, body.metadata)


@router.delete("/{alias}")
async def delete_alias(request: Request, alias: str):
    service = AliasesService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    ok = await service.delete_alias(project_id, alias)
    return {"deleted": ok}


