from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal


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
    registry_version: str
    model: str
    tokens: TokenUsage
    cost: CostBreakdown
    signature: str


class ReceiptRequest(BaseModel):
    receipt: Receipt


class ReceiptResponse(BaseModel):
    receipt_id: str
    status: str


