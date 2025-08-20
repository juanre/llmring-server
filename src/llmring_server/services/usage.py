import json
from typing import Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pgdbm import AsyncDatabaseManager
import redis.asyncio as redis

from llmring_server.config import Settings
from llmring_server.models.usage import (
    UsageLogRequest,
    UsageStats,
    UsageSummary,
    DailyUsage,
    ModelUsage,
)


settings = Settings()


class UsageService:
    """Service for usage logging and analytics."""

    def __init__(self, db: AsyncDatabaseManager):
        self.db = db
        self.redis = None
        try:
            self.redis = redis.from_url(settings.redis_url)
        except Exception:
            pass

    async def log_usage(self, api_key_id: str, log: UsageLogRequest, cost: float, timestamp: datetime) -> str:
        query = """
            INSERT INTO {{tables.usage_logs}} (
                api_key_id, model, provider, input_tokens, output_tokens,
                cached_input_tokens, cost, latency_ms, origin, id_at_origin,
                created_at, metadata, alias, profile
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING id
        """
        result = await self.db.fetch_one(
            query,
            api_key_id,
            log.model,
            log.provider,
            log.input_tokens,
            log.output_tokens,
            log.cached_input_tokens,
            float(cost),
            log.latency_ms,
            log.origin,
            log.id_at_origin,
            timestamp,
            json.dumps(log.metadata),
            log.alias,
            log.profile or "default",
        )
        return str(result["id"]) if result else ""

    async def get_stats(
        self,
        api_key_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: str = "day",
    ) -> UsageStats:
        def _to_naive(dt: datetime) -> datetime:
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        if not end_date:
            end_dt = _to_naive(datetime.now(timezone.utc))
        else:
            end_dt = _to_naive(datetime.fromisoformat(end_date.replace("Z", "+00:00")))
        if not start_date:
            start_dt = _to_naive(datetime.now(timezone.utc) - timedelta(days=30))
        else:
            start_dt = _to_naive(
                datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            )

        summary_query = """
            SELECT 
                COUNT(*) as total_requests,
                COALESCE(SUM(cost), 0) as total_cost,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COUNT(DISTINCT model) as unique_models,
                COUNT(DISTINCT origin) as unique_origins
            FROM {{tables.usage_logs}}
            WHERE api_key_id = $1
                AND created_at >= $2::timestamp
                AND created_at <= $3::timestamp
        """
        summary_result = await self.db.fetch_one(summary_query, api_key_id, start_dt, end_dt)
        summary = UsageSummary(
            total_requests=summary_result["total_requests"] or 0,
            total_cost=Decimal(str(summary_result["total_cost"] or 0)),
            total_tokens=summary_result["total_tokens"] or 0,
            unique_models=summary_result["unique_models"] or 0,
            unique_origins=summary_result["unique_origins"] or 0,
        )

        daily_query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost,
                model as top_model
            FROM {{tables.usage_logs}}
            WHERE api_key_id = $1
                AND created_at >= $2::timestamp
                AND created_at <= $3::timestamp
            GROUP BY DATE(created_at), model
            ORDER BY DATE(created_at) DESC, COUNT(*) DESC
        """
        daily_results = await self.db.fetch_all(daily_query, api_key_id, start_dt, end_dt)
        by_day = []
        current_date = None
        day_data = None
        for row in daily_results:
            if row["date"] != current_date:
                if day_data:
                    by_day.append(day_data)
                current_date = row["date"]
                day_data = DailyUsage(
                    date=row["date"].isoformat(),
                    requests=row["requests"],
                    cost=Decimal(str(row["cost"])),
                    top_model=row["top_model"],
                )
        if day_data:
            by_day.append(day_data)

        model_query = """
            SELECT 
                model,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM {{tables.usage_logs}}
            WHERE api_key_id = $1
                AND created_at >= $2::timestamp
                AND created_at <= $3::timestamp
            GROUP BY model
        """
        model_results = await self.db.fetch_all(model_query, api_key_id, start_dt, end_dt)
        by_model = {}
        for row in model_results:
            by_model[row["model"]] = ModelUsage(
                requests=row["requests"],
                cost=Decimal(str(row["cost"])),
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )

        origin_query = """
            SELECT 
                origin,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost
            FROM {{tables.usage_logs}}
            WHERE api_key_id = $1
                AND created_at >= $2::timestamp
                AND created_at <= $3::timestamp
                AND origin IS NOT NULL
            GROUP BY origin
        """
        origin_results = await self.db.fetch_all(origin_query, api_key_id, start_dt, end_dt)
        by_origin = {}
        for row in origin_results:
            by_origin[row["origin"]] = {
                "requests": row["requests"],
                "cost": float(row["cost"]),
            }

        return UsageStats(
            summary=summary, by_day=by_day, by_model=by_model, by_origin=by_origin
        )
