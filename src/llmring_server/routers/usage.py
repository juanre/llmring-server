from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from llmring_server.dependencies import get_project_id
from llmring_server.models.usage import UsageLogRequest, UsageLogResponse, UsageStats
from llmring_server.services.usage import UsageService

router = APIRouter(
    prefix="/api/v1",
    tags=["usage"],
    responses={429: {"description": "Rate limit exceeded"}},
)


@router.post("/log", response_model=UsageLogResponse)
async def log_usage(
    request: Request, log: UsageLogRequest, project_id: str = Depends(get_project_id)
) -> UsageLogResponse:
    service = UsageService(request.app.state.db)

    # No built-in rate limiting in core server
    # Calculate cost if not provided
    if log.cost is not None:
        cost = log.cost
    else:
        from llmring_server.services.registry import RegistryService

        registry_service = RegistryService()
        registry = await registry_service.get_registry()

        cost = 0.0
        # Registry models map may use provider-prefixed keys per v3.2
        model_key = f"{log.provider}:{log.model}" if ":" not in log.model else log.model
        model = (
            registry.models.get(model_key)
            or registry.models.get(log.model)
            or registry.models.get(f"{log.provider}/{log.model}")
        )
        if model:
            if model.dollars_per_million_tokens_input:
                billable_input = log.input_tokens - log.cached_input_tokens
                cost += (
                    float(model.dollars_per_million_tokens_input)
                    * billable_input
                    / 1_000_000
                )
            if model.dollars_per_million_tokens_output:
                cost += (
                    float(model.dollars_per_million_tokens_output)
                    * log.output_tokens
                    / 1_000_000
                )

    timestamp = datetime.now()
    log_id = await service.log_usage(project_id, log, cost, timestamp)

    return UsageLogResponse(log_id=str(log_id), cost=cost, timestamp=timestamp)


@router.get("/stats", response_model=UsageStats)
async def get_stats(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    group_by: str = Query(
        "day", description="Group results by time period", enum=["day", "week", "month"]
    ),
    project_id: str = Depends(get_project_id),
):
    service = UsageService(request.app.state.db)
    return await service.get_stats(
        api_key_id=project_id,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
    )
