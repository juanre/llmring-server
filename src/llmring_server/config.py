import base64
from enum import Enum
from pathlib import Path
from typing import Optional

from nacl import signing
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

    # Receipts signing/verification keys (base64-encoded Ed25519)
    receipts_private_key_base64: str | None = Field(
        default=None, validation_alias=AliasChoices("LLMRING_RECEIPTS_PRIVATE_KEY_B64")
    )
    receipts_public_key_base64: str | None = Field(
        default=None, validation_alias=AliasChoices("LLMRING_RECEIPTS_PUBLIC_KEY_B64")
    )
    receipts_key_id: str | None = Field(
        default=None, validation_alias=AliasChoices("LLMRING_RECEIPTS_KEY_ID")
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


def load_or_generate_keypair(
    key_file: Optional[Path] = None,
) -> tuple[str, str]:
    """
    Load or generate Ed25519 keypair for receipt signing.

    This function either:
    1. Loads an existing keypair from a file (if key_file provided and exists)
    2. Generates a new keypair and optionally saves it

    Args:
        key_file: Optional path to save/load keypair. If None, generates ephemeral keys.

    Returns:
        Tuple of (private_key_base64url, public_key_base64url)

    Example:
        >>> private_b64, public_b64 = load_or_generate_keypair(Path(".keys/receipt_signing_key"))
        >>> settings.receipts_private_key_base64 = private_b64
        >>> settings.receipts_public_key_base64 = public_b64
    """

    def _b64url_encode(data: bytes) -> str:
        """Encode bytes as base64url (no padding)."""
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    def _b64url_decode(data: str) -> bytes:
        """Decode base64url string (add padding if needed)."""
        padding = "=" * ((4 - len(data) % 4) % 4)
        return base64.urlsafe_b64decode(data + padding)

    # Try to load existing key
    if key_file and key_file.exists():
        try:
            content = key_file.read_text().strip()
            lines = content.split("\n")
            if len(lines) >= 2:
                private_b64 = lines[0].strip()
                public_b64 = lines[1].strip()

                # Validate the keys
                signing.SigningKey(_b64url_decode(private_b64))
                signing.VerifyKey(_b64url_decode(public_b64))

                return private_b64, public_b64
        except Exception as e:
            raise RuntimeError(f"Failed to load keypair from {key_file}: {e}")

    # Generate new keypair
    signing_key = signing.SigningKey.generate()
    verify_key = signing_key.verify_key

    private_b64 = _b64url_encode(bytes(signing_key))
    public_b64 = _b64url_encode(bytes(verify_key))

    # Save if key_file specified
    if key_file:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(f"{private_b64}\n{public_b64}\n")
        key_file.chmod(0o600)  # Secure permissions

    return private_b64, public_b64


def ensure_receipt_keys(settings: Settings, key_file: Optional[Path] = None) -> Settings:
    """
    Ensure receipt signing keys are configured.

    If keys are not configured in settings, generates or loads them.

    Args:
        settings: Settings instance to update
        key_file: Optional path to key file

    Returns:
        Updated settings instance

    Example:
        >>> settings = Settings()
        >>> settings = ensure_receipt_keys(settings, Path(".keys/receipt_key"))
    """
    if not settings.receipts_private_key_base64 or not settings.receipts_public_key_base64:
        private_b64, public_b64 = load_or_generate_keypair(key_file)
        settings.receipts_private_key_base64 = private_b64
        settings.receipts_public_key_base64 = public_b64

        if not settings.receipts_key_id:
            # Generate a simple key ID from public key hash
            import hashlib

            key_hash = hashlib.sha256(public_b64.encode()).hexdigest()[:16]
            settings.receipts_key_id = f"key_{key_hash}"

    return settings
