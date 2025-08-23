from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UsageLogRequest(BaseModel):
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    alias: Optional[str] = None
    profile: Optional[str] = None
    cost: Optional[float] = None
    latency_ms: Optional[int] = None
    origin: Optional[str] = None
    id_at_origin: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UsageLogResponse(BaseModel):
    log_id: str
    cost: float
    timestamp: datetime


class UsageSummary(BaseModel):
    total_requests: int
    total_cost: Decimal
    total_tokens: int
    unique_models: int
    unique_origins: int


class DailyUsage(BaseModel):
    date: str
    requests: int
    cost: Decimal
    top_model: str


class ModelUsage(BaseModel):
    requests: int
    cost: Decimal
    input_tokens: int
    output_tokens: int


class UsageStats(BaseModel):
    summary: UsageSummary
    by_day: List[DailyUsage]
    by_model: Dict[str, ModelUsage]
    by_origin: Dict[str, Dict[str, Any]]
    by_alias: Dict[str, ModelUsage]
