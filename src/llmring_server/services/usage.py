"""Business logic for LLM usage logging and statistics aggregation. Logs usage data with Redis caching and provides daily/model-level analytics."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

import redis.asyncio as redis
from pgdbm import AsyncDatabaseManager

from llmring_server.config import MessageLoggingLevel, Settings
from llmring_server.models.usage import (
    DailyUsage,
    ModelUsage,
    UsageLogRequest,
    UsageStats,
    UsageSummary,
)

settings = Settings()


def _parse_iso_datetime(value: Optional[str], *, is_end_of_range: bool) -> Optional[datetime]:
    """Parse ISO-8601 date/time strings, normalising to UTC."""
    if not value:
        return None

    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    date_only = "T" not in value and " " not in value

    if date_only:
        if is_end_of_range:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999_999)
        else:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


class UsageService:
    """Service for usage logging and analytics."""

    def __init__(self, db: AsyncDatabaseManager):
        self.db = db
        self.redis = None
        try:
            self.redis = redis.from_url(settings.redis_url)
        except (redis.ConnectionError, redis.RedisError, ValueError):
            # Redis is optional for caching, continue without it
            pass

    async def log_usage(
        self,
        api_key_id: Optional[str],
        log: UsageLogRequest,
        cost: float,
        timestamp: datetime,
        conversation_id: Optional[UUID] = None,
        messages: Optional[List[Dict]] = None,
        logging_level: Optional[MessageLoggingLevel] = None,
        project_id: Optional[str] = None,
    ) -> Dict:
        """Log usage and optionally store conversation messages.

        Returns a dict with usage_id and optionally conversation details.
        """
        # Use default logging level from settings if not specified
        if logging_level is None:
            logging_level = settings.message_logging_level

        # Insert usage log with optional conversation_id
        query = """
            INSERT INTO {{tables.usage_logs}} (
                api_key_id, project_id, model, provider, input_tokens, output_tokens,
                cached_input_tokens, cost, latency_ms, origin, id_at_origin,
                created_at, metadata, alias, profile, conversation_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            RETURNING id
        """
        result = await self.db.fetch_one(
            query,
            api_key_id,
            project_id,
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
            conversation_id,
        )
        usage_id = str(result["id"]) if result else ""

        # Handle message storage if enabled
        messages_stored = 0
        if (
            messages
            and conversation_id
            and settings.enable_conversation_tracking
            and logging_level != MessageLoggingLevel.NONE
        ):
            # Import here to avoid circular dependency
            from llmring_server.services.conversations import ConversationService

            conv_service = ConversationService(self.db, settings)

            for msg in messages:
                from llmring_server.models.conversations import MessageCreate

                message_create = MessageCreate(
                    conversation_id=conversation_id,
                    role=msg.get("role"),
                    content=msg.get("content"),
                    input_tokens=msg.get("input_tokens"),
                    output_tokens=msg.get("output_tokens"),
                    metadata=msg.get("metadata", {}),
                )

                stored = await conv_service.add_message(message_create, logging_level=logging_level)
                if stored:
                    messages_stored += 1

        return {
            "usage_id": usage_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "messages_stored": messages_stored,
        }

    async def get_stats(
        self,
        api_key_id: Optional[str] = None,
        project_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: str = "day",
    ) -> UsageStats:
        end_dt = (
            _parse_iso_datetime(end_date, is_end_of_range=True)
            if end_date
            else datetime.now(timezone.utc)
        )
        start_dt = (
            _parse_iso_datetime(start_date, is_end_of_range=False)
            if start_date
            else datetime.now(timezone.utc) - timedelta(days=30)
        )

        # Ensure defaults are normalized to UTC if they were not parsed from input
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        # Clamp start to not exceed end
        if start_dt > end_dt:
            start_dt = end_dt

        filter_column = "api_key_id" if api_key_id else "project_id"
        filter_value = api_key_id or project_id

        summary_query = f"""
            SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(cost), 0) as total_cost,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COUNT(DISTINCT model) as unique_models,
                COUNT(DISTINCT origin) as unique_origins
            FROM {{tables.usage_logs}}
            WHERE {filter_column} = $1
                AND created_at >= $2::timestamptz
                AND created_at <= $3::timestamptz
        """
        summary_result = await self.db.fetch_one(summary_query, filter_value, start_dt, end_dt)
        # Guard against None result rows for mypy
        tr = (
            int(summary_result["total_requests"])
            if summary_result and summary_result["total_requests"] is not None
            else 0
        )
        tc = (
            Decimal(str(summary_result["total_cost"]))
            if summary_result and summary_result["total_cost"] is not None
            else Decimal("0")
        )
        tt = (
            int(summary_result["total_tokens"])
            if summary_result and summary_result["total_tokens"] is not None
            else 0
        )
        um = (
            int(summary_result["unique_models"])
            if summary_result and summary_result["unique_models"] is not None
            else 0
        )
        uo = (
            int(summary_result["unique_origins"])
            if summary_result and summary_result["unique_origins"] is not None
            else 0
        )
        summary = UsageSummary(
            total_requests=tr,
            total_cost=tc,
            total_tokens=tt,
            unique_models=um,
            unique_origins=uo,
        )

        daily_query = f"""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost,
                model as top_model
            FROM {{tables.usage_logs}}
            WHERE {filter_column} = $1
                AND created_at >= $2::timestamptz
                AND created_at <= $3::timestamptz
            GROUP BY DATE(created_at), model
            ORDER BY DATE(created_at) DESC, COUNT(*) DESC
        """
        daily_results = await self.db.fetch_all(daily_query, filter_value, start_dt, end_dt)
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

        model_query = f"""
            SELECT
                model,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM {{tables.usage_logs}}
            WHERE {filter_column} = $1
                AND created_at >= $2::timestamptz
                AND created_at <= $3::timestamptz
            GROUP BY model
        """
        model_results = await self.db.fetch_all(model_query, filter_value, start_dt, end_dt)
        by_model = {}
        for row in model_results:
            by_model[row["model"]] = ModelUsage(
                requests=row["requests"],
                cost=Decimal(str(row["cost"])),
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )

        origin_query = f"""
            SELECT
                origin,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost
            FROM {{tables.usage_logs}}
            WHERE {filter_column} = $1
                AND created_at >= $2::timestamptz
                AND created_at <= $3::timestamptz
                AND origin IS NOT NULL
            GROUP BY origin
        """
        origin_results = await self.db.fetch_all(origin_query, filter_value, start_dt, end_dt)
        by_origin = {}
        for row in origin_results:
            by_origin[row["origin"]] = {
                "requests": row["requests"],
                "cost": float(row["cost"]),
            }

        alias_query = f"""
            SELECT
                alias,
                COUNT(*) as requests,
                COALESCE(SUM(cost), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM {{tables.usage_logs}}
            WHERE {filter_column} = $1
                AND created_at >= $2::timestamptz
                AND created_at <= $3::timestamptz
                AND alias IS NOT NULL
            GROUP BY alias
        """
        alias_results = await self.db.fetch_all(alias_query, filter_value, start_dt, end_dt)
        by_alias = {}
        for row in alias_results:
            by_alias[row["alias"]] = ModelUsage(
                requests=row["requests"],
                cost=Decimal(str(row["cost"])),
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )

        return UsageStats(
            summary=summary,
            by_day=by_day,
            by_model=by_model,
            by_origin=by_origin,
            by_alias=by_alias,
        )

    async def get_logs(
        self,
        api_key_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        alias: Optional[str] = None,
        model: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        if not (api_key_id or project_id):
            raise ValueError("Must provide api_key_id or project_id")
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        end_dt = (
            _parse_iso_datetime(end_date, is_end_of_range=True)
            if end_date
            else datetime.now(timezone.utc)
        )
        start_dt = (
            _parse_iso_datetime(start_date, is_end_of_range=False)
            if start_date
            else end_dt - timedelta(days=30)
        )

        filter_column = "api_key_id" if api_key_id else "project_id"
        filter_value = api_key_id or project_id

        conditions = [f"{filter_column} = $1"]
        params: List[object] = [filter_value]
        idx = 2

        if start_dt:
            conditions.append(f"created_at >= ${idx}::timestamptz")
            params.append(start_dt)
            idx += 1
        if end_dt:
            conditions.append(f"created_at <= ${idx}::timestamptz")
            params.append(end_dt)
            idx += 1
        if alias:
            conditions.append(f"alias = ${idx}")
            params.append(alias)
            idx += 1
        if model:
            conditions.append(f"model = ${idx}")
            params.append(model)
            idx += 1
        if origin:
            conditions.append(f"origin = ${idx}")
            params.append(origin)
            idx += 1

        where_clause = " AND ".join(conditions)
        query = (
            "SELECT "
            "id, created_at, provider, model, alias, profile, origin, "
            "input_tokens, output_tokens, cached_input_tokens, cost, metadata, "
            "conversation_id, id_at_origin "
            "FROM {{tables.usage_logs}} "
            "WHERE " + where_clause + f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        )
        params.extend([limit, offset])

        rows = await self.db.fetch_all(query, *params)
        results: List[Dict[str, object]] = []
        for row in rows or []:
            metadata = row.get("metadata")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = None

            conversation_id = row.get("conversation_id")
            if conversation_id:
                conversation_id = str(conversation_id)

            results.append(
                {
                    "id": str(row["id"]),
                    "logged_at": row["created_at"],
                    "provider": row.get("provider"),
                    "model": row.get("model"),
                    "alias": row.get("alias"),
                    "profile": row.get("profile"),
                    "origin": row.get("origin"),
                    "input_tokens": row.get("input_tokens"),
                    "output_tokens": row.get("output_tokens"),
                    "cached_input_tokens": row.get("cached_input_tokens"),
                    "cost": float(row.get("cost") or 0),
                    "metadata": metadata,
                    "conversation_id": conversation_id,
                    "id_at_origin": row.get("id_at_origin"),
                }
            )

        return results
