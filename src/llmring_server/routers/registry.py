from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from llmring_server.models.registry import RegistryResponse
from llmring_server.services.registry import RegistryService

router = APIRouter(
    prefix="/registry", tags=["registry"], responses={404: {"description": "Not found"}}
)


@router.get("/", response_model=RegistryResponse)
@router.get(".json", response_model=RegistryResponse, include_in_schema=False)
async def get_registry(
    request: Request,
    response: Response,
    version: Optional[str] = Query(None, description="Specific registry version; deprecated"),
    providers: Optional[str] = Query(
        None, description="Comma-separated list of providers to filter"
    ),
    capabilities: Optional[str] = Query(
        None, description="Comma-separated list of required capabilities"
    ),
):
    service = RegistryService()
    # For backward compatibility, still honors version; service will ignore and fetch latest remote
    registry = await service.get_registry(version=version)

    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["ETag"] = f'"{registry.version}"'

    if request.headers.get("If-None-Match") == f'"{registry.version}"':
        return Response(status_code=304)

    if providers:
        registry = service.filter_by_providers(registry, providers.split(","))
    if capabilities:
        registry = service.filter_by_capabilities(registry, capabilities.split(","))
    return registry


@router.get("/v/{version}/registry.json", response_model=RegistryResponse)
async def get_registry_version(request: Request, response: Response, version: str = Path(...)):
    service = RegistryService()
    try:
        registry = await service.get_registry_version(version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return registry
