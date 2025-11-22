"""Pydantic models for LLM model registry responses. Defines model metadata, provider information, and pricing data from GitHub Pages registry."""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class LLMModel(BaseModel):
    provider: str = Field(..., description="Model provider (anthropic, openai, google, ollama)")
    model_name: str = Field(..., description="Model name")
    display_name: Optional[str] = None
    description: Optional[str] = None

    # v3.5 naming
    max_input_tokens: Optional[int] = Field(None, description="Maximum input tokens")
    max_output_tokens: Optional[int] = Field(None, description="Maximum output tokens")
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    supports_parallel_tool_calls: bool = False
    tool_call_format: Optional[str] = None

    dollars_per_million_tokens_input: Optional[float] = Field(None)
    dollars_per_million_tokens_output: Optional[float] = Field(None)
    is_active: bool = True


class ProviderInfo(BaseModel):
    name: str
    base_url: str
    models_endpoint: Optional[str] = None


class RegistryResponse(BaseModel):
    version: str
    generated_at: datetime
    models: Dict[str, LLMModel]
    providers: Dict[str, ProviderInfo]
