from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TokenUsage(BaseModel):
    input: int
    output: int
    cached_input: int = 0


class CostBreakdown(BaseModel):
    amount: Decimal
    calculation: str


class Receipt(BaseModel):
    id: str
    timestamp: datetime
    registry_version: str  # deprecated in favor of per-provider versions; kept for compat
    model: str
    alias: str
    profile: str = "default"
    lock_digest: str
    key_id: str
    tokens: TokenUsage
    cost: CostBreakdown
    signature: str


class ReceiptRequest(BaseModel):
    receipt: Receipt


class UnsignedReceipt(BaseModel):
    id: str
    timestamp: datetime
    registry_version: str
    model: str
    alias: str
    profile: str = "default"
    lock_digest: str
    key_id: str
    tokens: TokenUsage
    cost: CostBreakdown


class ReceiptResponse(BaseModel):
    receipt_id: str
    status: str
