import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import redis.asyncio as redis
import httpx

from llmring_server.config import Settings
from llmring_server.models.registry import (
    RegistryResponse,
    LLMModel,
    ProviderInfo,
)


settings = Settings()


class RegistryService:
    """Service for managing model registry."""

    def __init__(self):
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

        base = settings.registry_base_url.rstrip("/") + "/"
        providers = self._get_default_providers()
        models: Dict[str, LLMModel] = {}
        manifest_version: Optional[str] = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                m = await client.get(base + "manifest.json")
                if m.status_code == 200:
                    manifest = m.json()
                    manifest_version = str(
                        manifest.get("version")
                        or manifest.get("schema_version")
                        or manifest.get("updated_at")
                        or ""
                    )
            except Exception:
                pass

            for provider_key in providers.keys():
                # v3.5 registry: models are in a provider folder and also archived per version
                url = f"{base}{provider_key}/models.json"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    raw_models = data.get("models") if isinstance(data, dict) else None
                    if not isinstance(raw_models, dict):
                        continue
                    for model_key, info in raw_models.items():
                        if not isinstance(info, dict):
                            continue
                        llm_model = LLMModel(
                            provider=info.get("provider") or provider_key,
                            model_name=info.get("model_name") or model_key.split(":", 1)[-1],
                            display_name=info.get("display_name"),
                            description=info.get("description"),
                            max_input_tokens=info.get("max_input_tokens"),
                            max_output_tokens=info.get("max_output_tokens"),
                            supports_vision=bool(info.get("supports_vision", False)),
                            supports_function_calling=bool(info.get("supports_function_calling", False)),
                            supports_json_mode=bool(info.get("supports_json_mode", False)),
                            supports_parallel_tool_calls=bool(info.get("supports_parallel_tool_calls", False)),
                            tool_call_format=info.get("tool_call_format"),
                            dollars_per_million_tokens_input=info.get("dollars_per_million_tokens_input"),
                            dollars_per_million_tokens_output=info.get("dollars_per_million_tokens_output"),
                            is_active=bool(info.get("is_active", True)),
                        )
                        models[model_key] = llm_model
                except Exception:
                    continue

        registry = RegistryResponse(
            version=manifest_version
            or (version or datetime.now().strftime("%Y.%m.%d")),
            generated_at=datetime.now(),
            models=models,
            providers=providers,
        )

        if self.redis:
            try:
                await self.redis.setex(
                    cache_key, settings.cache_ttl, registry.model_dump_json()
                )
            except Exception:
                pass

        return registry

    async def get_registry_version(self, version: str) -> RegistryResponse:
        # Fetch archived provider-specific versions and merge.
        base = settings.registry_base_url.rstrip("/") + "/"
        providers = self._get_default_providers()
        models: Dict[str, LLMModel] = {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            for provider_key in providers.keys():
                url = f"{base}{provider_key}/v/{version}/models.json"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    raw_models = data.get("models") if isinstance(data, dict) else None
                    if not isinstance(raw_models, dict):
                        continue
                    for model_key, info in raw_models.items():
                        if not isinstance(info, dict):
                            continue
                        llm_model = LLMModel(
                            provider=info.get("provider") or provider_key,
                            model_name=info.get("model_name") or model_key.split(":", 1)[-1],
                            display_name=info.get("display_name"),
                            description=info.get("description"),
                            max_input_tokens=info.get("max_input_tokens"),
                            max_output_tokens=info.get("max_output_tokens"),
                            supports_vision=bool(info.get("supports_vision", False)),
                            supports_function_calling=bool(info.get("supports_function_calling", False)),
                            supports_json_mode=bool(info.get("supports_json_mode", False)),
                            supports_parallel_tool_calls=bool(info.get("supports_parallel_tool_calls", False)),
                            tool_call_format=info.get("tool_call_format"),
                            dollars_per_million_tokens_input=info.get("dollars_per_million_tokens_input"),
                            dollars_per_million_tokens_output=info.get("dollars_per_million_tokens_output"),
                            is_active=bool(info.get("is_active", True)),
                        )
                        models[model_key] = llm_model
                except Exception:
                    continue

        registry = RegistryResponse(
            version=str(version),
            generated_at=datetime.now(),
            models=models,
            providers=providers,
        )
        return registry

    def filter_by_providers(
        self, registry: RegistryResponse, providers: List[str]
    ) -> RegistryResponse:
        filtered_models = {
            k: v for k, v in registry.models.items() if v.provider in providers
        }
        registry.models = filtered_models
        return registry

    def filter_by_capabilities(
        self, registry: RegistryResponse, capabilities: List[str]
    ) -> RegistryResponse:
        filtered_models = {}
        for model_name, model in registry.models.items():
            has_all = True
            for cap in capabilities:
                cap_field = (
                    f"supports_{cap}"
                    if cap
                    in [
                        "vision",
                        "function_calling",
                        "json_mode",
                        "parallel_tool_calls",
                    ]
                    else cap
                )
                if not getattr(model, cap_field, False):
                    has_all = False
                    break
            if has_all:
                filtered_models[model_name] = model
        registry.models = filtered_models
        return registry

    # Removed deprecated DB formatting helper

    def _get_default_providers(self) -> Dict[str, ProviderInfo]:
        return {
            "openai": ProviderInfo(
                name="OpenAI",
                base_url="https://api.openai.com/v1",
                models_endpoint="/models",
            ),
            "anthropic": ProviderInfo(
                name="Anthropic",
                base_url="https://api.anthropic.com",
                models_endpoint=None,
            ),
            "google": ProviderInfo(
                name="Google",
                base_url="https://generativelanguage.googleapis.com",
                models_endpoint="/v1/models",
            ),
        }
