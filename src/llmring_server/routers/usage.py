# ABOUTME: FastAPI router for LLM usage logging and statistics.
# ABOUTME: Handles usage log creation, retrieval with filtering, and aggregated statistics.

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pgdbm import AsyncDatabaseManager

from llmring_server.dependencies import get_db, get_project_id
from llmring_server.models.usage import UsageLogEntry, UsageLogRequest, UsageLogResponse, UsageStats
from llmring_server.services.usage import UsageService

router = APIRouter(
    prefix="/api/v1",
    tags=["usage"],
    responses={429: {"description": "Rate limit exceeded"}},
)


@router.post("/log", response_model=UsageLogResponse)
async def log_usage(
    log: UsageLogRequest,
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
) -> UsageLogResponse:
    service = UsageService(db)

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
                cost += float(model.dollars_per_million_tokens_input) * billable_input / 1_000_000
            if model.dollars_per_million_tokens_output:
                cost += (
                    float(model.dollars_per_million_tokens_output) * log.output_tokens / 1_000_000
                )

    timestamp = datetime.now()
    result = await service.log_usage(project_id, log, cost, timestamp)

    # Handle both old string return and new dict return for compatibility
    if isinstance(result, dict):
        log_id = result.get("usage_id", "")
    else:
        log_id = result  # Old string format

    return UsageLogResponse(log_id=str(log_id), cost=cost, timestamp=timestamp)


@router.get("/stats", response_model=UsageStats)
async def get_stats(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    group_by: str = Query(
        "day", description="Group results by time period", enum=["day", "week", "month"]
    ),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = UsageService(db)
    return await service.get_stats(
        api_key_id=project_id,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
    )


@router.get("/logs", response_model=list[UsageLogEntry])
async def list_usage_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End date (ISO 8601)"),
    alias: Optional[str] = Query(None, description="Filter by alias"),
    model: Optional[str] = Query(None, description="Filter by model"),
    origin: Optional[str] = Query(None, description="Filter by origin"),
    project_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    service = UsageService(db)
    logs = await service.get_logs(
        api_key_id=project_id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        alias=alias,
        model=model,
        origin=origin,
    )
    return logs
