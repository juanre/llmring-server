import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import redis.asyncio as redis
from pgdbm import AsyncDatabaseManager

from llmring_server.config import Settings
from llmring_server.models.registry import (
    RegistryResponse,
    LLMModel,
    ProviderInfo,
)


settings = Settings()


class RegistryService:
    """Service for managing model registry."""

    def __init__(self, db: AsyncDatabaseManager):
        self.db = db
        self.redis = None
        try:
            self.redis = redis.from_url(settings.redis_url)
        except Exception:
            pass

    async def get_registry(self, version: Optional[str] = None) -> RegistryResponse:
        cache_key = f"registry:{version or 'latest'}"
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    return RegistryResponse.model_validate_json(cached)
            except Exception:
                pass

        if version:
            query = """
                SELECT models_snapshot 
                FROM {{tables.registry_versions}}
                WHERE version = $1
            """
            result = await self.db.fetch_one(query, version)
            if not result:
                raise ValueError(f"Version {version} not found")
            models_data = result["models_snapshot"]
        else:
            query = """
                SELECT * FROM {{tables.llm_models}}
                WHERE inactive_from IS NULL
            """
            models = await self.db.fetch_all(query)
            models_data = self._format_registry(models)

        registry = RegistryResponse(
            version=version or datetime.now().strftime("%Y.%m.%d"),
            generated_at=datetime.now(),
            models=models_data.get("models", {}),
            providers=models_data.get("providers", self._get_default_providers()),
        )

        if self.redis:
            try:
                await self.redis.setex(cache_key, settings.cache_ttl, registry.model_dump_json())
            except Exception:
                pass

        return registry

    async def get_registry_version(self, version: str) -> RegistryResponse:
        query = """
            SELECT models_snapshot, created_at
            FROM {{tables.registry_versions}}
            WHERE version = $1
        """
        result = await self.db.fetch_one(query, version)
        if not result:
            raise ValueError(f"Version {version} not found")
        models_data = result["models_snapshot"]
        return RegistryResponse(
            version=version,
            generated_at=result["created_at"],
            models=models_data.get("models", {}),
            providers=models_data.get("providers", self._get_default_providers()),
        )

    def filter_by_providers(self, registry: RegistryResponse, providers: List[str]) -> RegistryResponse:
        filtered_models = {k: v for k, v in registry.models.items() if v.provider in providers}
        registry.models = filtered_models
        return registry

    def filter_by_capabilities(self, registry: RegistryResponse, capabilities: List[str]) -> RegistryResponse:
        filtered_models = {}
        for model_name, model in registry.models.items():
            has_all = True
            for cap in capabilities:
                cap_field = (
                    f"supports_{cap}"
                    if cap in ["vision", "function_calling", "json_mode", "parallel_tool_calls"]
                    else cap
                )
                if not getattr(model, cap_field, False):
                    has_all = False
                    break
            if has_all:
                filtered_models[model_name] = model
        registry.models = filtered_models
        return registry

    def _format_registry(self, models: List[Dict[str, Any]]) -> Dict[str, Any]:
        registry_models = {}
        for model in models:
            llm_model = LLMModel(
                id=model.get("id"),
                provider=model["provider"],
                model_name=model["model_name"],
                display_name=model.get("display_name"),
                description=model.get("description"),
                max_context=model.get("max_context"),
                max_output_tokens=model.get("max_output_tokens"),
                supports_vision=model.get("supports_vision", False),
                supports_function_calling=model.get("supports_function_calling", False),
                supports_json_mode=model.get("supports_json_mode", False),
                supports_parallel_tool_calls=model.get("supports_parallel_tool_calls", False),
                tool_call_format=model.get("tool_call_format"),
                dollars_per_million_tokens_input=model.get("dollars_per_million_tokens_input"),
                dollars_per_million_tokens_output=model.get("dollars_per_million_tokens_output"),
                inactive_from=model.get("inactive_from"),
                created_at=model.get("created_at"),
                updated_at=model.get("updated_at"),
            )
            registry_models[model["model_name"]] = llm_model
        return {"models": registry_models, "providers": self._get_default_providers()}

    def _get_default_providers(self) -> Dict[str, ProviderInfo]:
        return {
            "openai": ProviderInfo(name="OpenAI", base_url="https://api.openai.com/v1", models_endpoint="/models"),
            "anthropic": ProviderInfo(name="Anthropic", base_url="https://api.anthropic.com", models_endpoint=None),
            "google": ProviderInfo(
                name="Google",
                base_url="https://generativelanguage.googleapis.com",
                models_endpoint="/v1/models",
            ),
        }


