"""
Receipt models for llmring-server.

These models are used for server-side receipt generation and signing.
They match the schema expected by the llmring client (llmring/src/llmring/receipts.py).

Phase 7.5: Extended to support on-demand and batch receipt generation.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Receipt(BaseModel):
    """
    Server-side receipt model that matches the client schema.

    This is the signed receipt returned to clients and stored in the database.
    Field names match llmring/src/llmring/receipts.py for compatibility.
    """

    # Identity
    receipt_id: str = Field(..., description="Unique receipt identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Receipt timestamp",
    )

    # Request info
    alias: str = Field(..., description="Alias used for the request")
    profile: str = Field(default="default", description="Profile used")
    lock_digest: str = Field(default="", description="SHA256 digest of lockfile")

    # Model info
    provider: str = Field(..., description="Provider used")
    model: str = Field(..., description="Model used")

    # Usage (flat fields, not nested)
    prompt_tokens: int = Field(..., description="Input tokens")
    completion_tokens: int = Field(..., description="Output tokens")
    total_tokens: int = Field(..., description="Total tokens")

    # Cost (flat fields, not nested)
    input_cost: float = Field(..., description="Cost for input tokens (USD)")
    output_cost: float = Field(..., description="Cost for output tokens (USD)")
    total_cost: float = Field(..., description="Total cost (USD)")

    # Signature (added by server during signing)
    signature: Optional[str] = Field(None, description="Ed25519 signature (ed25519:base64)")


class UnsignedReceipt(BaseModel):
    """
    Unsigned receipt used for generation before signing.
    Same as Receipt but without signature field requirement.
    """

    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:16]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alias: str
    profile: str = "default"
    lock_digest: str = ""
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float


class ReceiptRequest(BaseModel):
    """Request to store an externally-generated receipt."""
    receipt: Receipt


class ReceiptResponse(BaseModel):
    """Response after storing a receipt."""
    receipt_id: str
    status: str


class ReceiptListResponse(BaseModel):
    """Response for listing receipts."""

    receipts: list[Receipt]
    total: int
    limit: int
    offset: int


# =====================================================
# Phase 7.5: On-Demand Receipt Generation Models
# =====================================================


class BatchReceiptSummary(BaseModel):
    """Summary statistics for a batch receipt."""

    total_conversations: int = Field(..., description="Number of conversations certified")
    total_calls: int = Field(..., description="Number of API calls certified")
    total_tokens: int = Field(..., description="Total tokens across all calls")
    start_date: Optional[str] = Field(None, description="Start of date range (ISO format)")
    end_date: Optional[str] = Field(None, description="End of date range (ISO format)")
    by_model: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Breakdown by model (calls, cost, tokens)"
    )
    by_alias: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Breakdown by alias (calls, cost, tokens)"
    )
    conversation_ids: List[str] = Field(default_factory=list, description="List of conversation IDs certified")
    log_ids: List[str] = Field(default_factory=list, description="List of usage log IDs certified")


class BatchReceipt(Receipt):
    """
    Extended receipt model for batch certification.

    Inherits all fields from Receipt but adds:
    - receipt_type to distinguish single vs batch
    - batch_summary for aggregated statistics
    - description and tags for user metadata
    """

    receipt_type: str = Field(default="single", description="Type: 'single' or 'batch'")
    batch_summary: Optional[BatchReceiptSummary] = Field(
        None, description="Summary statistics for batch receipts"
    )
    description: Optional[str] = Field(None, description="User-provided description")
    tags: Optional[List[str]] = Field(None, description="User-provided tags for categorization")


class ReceiptGenerationRequest(BaseModel):
    """
    Request model for on-demand receipt generation.

    Supports four modes:
    1. Single conversation: conversation_id
    2. Date range (batch): start_date + end_date
    3. Specific log IDs: log_ids
    4. Since last receipt: since_last_receipt=True
    """

    # Option 1: Single conversation
    conversation_id: Optional[UUID] = Field(None, description="Generate receipt for a single conversation")

    # Option 2: Date range (batch receipt)
    start_date: Optional[datetime] = Field(None, description="Start date for batch receipt")
    end_date: Optional[datetime] = Field(None, description="End date for batch receipt")

    # Option 3: Specific log IDs
    log_ids: Optional[List[UUID]] = Field(None, description="Specific usage log IDs to certify")

    # Option 4: All logs since last receipt
    since_last_receipt: bool = Field(False, description="Certify all uncertified logs since last receipt")

    # Receipt metadata
    description: Optional[str] = Field(None, description="User-provided description for the receipt")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")


class ReceiptGenerationResponse(BaseModel):
    """Response model for receipt generation."""

    receipt: BatchReceipt = Field(..., description="The generated and signed receipt")
    certified_count: int = Field(..., description="Number of items certified by this receipt")
