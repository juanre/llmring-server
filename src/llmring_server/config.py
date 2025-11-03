from enum import Enum
from typing import Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MessageLoggingLevel(str, Enum):
    """Message logging levels for conversation tracking."""

    NONE = "none"  # No message logging (default)
    METADATA = "metadata"  # Log message metadata only (no content)
    FULL = "full"  # Log full messages including content


class Settings(BaseSettings):
    """Server configuration loaded from environment variables or .env file.

    Supported env vars (aliases in parentheses):
    - LLMRING_DATABASE_URL
    - LLMRING_DATABASE_SCHEMA
    - LLMRING_DATABASE_POOL_SIZE
    - LLMRING_DATABASE_POOL_OVERFLOW
    - LLMRING_REDIS_URL
    - LLMRING_CACHE_TTL
    - LLMRING_API_PREFIX
    - LLMRING_CORS_ORIGINS  (comma-separated list)
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Database
    database_url: str = Field(
        default="postgresql://localhost/llmring",
        validation_alias=AliasChoices("LLMRING_DATABASE_URL"),
    )
    database_schema: str = Field(
        default="llmring",
        validation_alias=AliasChoices("LLMRING_DATABASE_SCHEMA"),
    )
    database_pool_size: int = Field(
        default=20,
        validation_alias=AliasChoices("LLMRING_DATABASE_POOL_SIZE"),
    )
    database_pool_overflow: int = Field(
        default=10,
        validation_alias=AliasChoices("LLMRING_DATABASE_POOL_OVERFLOW"),
    )

    # Redis cache
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("LLMRING_REDIS_URL"),
    )
    cache_ttl: int = Field(
        default=3600,
        validation_alias=AliasChoices("LLMRING_CACHE_TTL"),
    )

    # API Configuration (prefix not used at core level; routes include their own prefixes)
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:5174", "*"],
        validation_alias=AliasChoices("LLMRING_CORS_ORIGINS"),
    )

    # Registry configuration
    registry_base_url: str = Field(
        default="https://llmring.github.io/registry/",
        validation_alias=AliasChoices("LLMRING_REGISTRY_BASE_URL"),
    )

    # Message logging configuration
    message_logging_level: MessageLoggingLevel = Field(
        default=MessageLoggingLevel.FULL,
        validation_alias=AliasChoices("LLMRING_MESSAGE_LOGGING_LEVEL"),
        description="Level of message logging: none, metadata, or full",
    )
    message_retention_days: int = Field(
        default=30,
        validation_alias=AliasChoices("LLMRING_MESSAGE_RETENTION_DAYS"),
        description="How many days to retain message history",
    )
    enable_conversation_tracking: bool = Field(
        default=True,
        validation_alias=AliasChoices("LLMRING_ENABLE_CONVERSATION_TRACKING"),
        description="Whether to track conversations (even without message content)",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        # Support comma-separated string in env
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",")]
            return [p for p in parts if p]
        return value

    # Pydantic v2: use model_config above; no inner Config class
