from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional
from datetime import datetime

from llmring_server.models.usage import UsageLogRequest, UsageLogResponse, UsageStats
from llmring_server.services.usage import UsageService


router = APIRouter(prefix="/api/v1", tags=["usage"], responses={429: {"description": "Rate limit exceeded"}})


@router.post("/log", response_model=UsageLogResponse)
async def log_usage(request: Request, log: UsageLogRequest) -> UsageLogResponse:
    service = UsageService(request.app.state.db)

    # No strict rate limiting by default in this server; if Redis configured, it will be honored
    # Calculate cost if not provided
    if log.cost is not None:
        cost = log.cost
    else:
        from llmring_server.services.registry import RegistryService

        registry_service = RegistryService(request.app.state.db)
        registry = await registry_service.get_registry()

        cost = 0.0
        model_key = f"{log.model}"
        model = registry.models.get(model_key) or registry.models.get(f"{log.provider}/{log.model}")
        if model:
            if model.dollars_per_million_tokens_input:
                billable_input = log.input_tokens - log.cached_input_tokens
                cost += float(model.dollars_per_million_tokens_input) * billable_input / 1_000_000
            if model.dollars_per_million_tokens_output:
                cost += float(model.dollars_per_million_tokens_output) * log.output_tokens / 1_000_000

    timestamp = datetime.now()
    project_id = request.headers.get("X-Project-Key", "default")
    log_id = await service.log_usage(project_id, log, cost, timestamp)

    return UsageLogResponse(log_id=str(log_id), cost=cost, timestamp=timestamp)


@router.get("/stats", response_model=UsageStats)
async def get_stats(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    group_by: str = Query("day", description="Group results by time period", enum=["day", "week", "month"]),
):
    service = UsageService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    return await service.get_stats(api_key_id=project_id, start_date=start_date, end_date=end_date, group_by=group_by)


