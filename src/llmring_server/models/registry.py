from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class LLMModel(BaseModel):
    id: Optional[int] = None
    provider: str = Field(..., description="Model provider (anthropic, openai, google, ollama)")
    model_name: str = Field(..., description="Model name")
    display_name: Optional[str] = None
    description: Optional[str] = None

    max_context: Optional[int] = Field(None, description="Maximum context length")
    max_output_tokens: Optional[int] = Field(None, description="Maximum output tokens")
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    supports_parallel_tool_calls: bool = False
    tool_call_format: Optional[str] = None

    dollars_per_million_tokens_input: Optional[Decimal] = Field(None)
    dollars_per_million_tokens_output: Optional[Decimal] = Field(None)

    inactive_from: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProviderInfo(BaseModel):
    name: str
    base_url: str
    models_endpoint: Optional[str] = None


class RegistryResponse(BaseModel):
    version: str
    generated_at: datetime
    models: Dict[str, LLMModel]
    providers: Dict[str, ProviderInfo]


