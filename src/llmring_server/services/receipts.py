import json
import hashlib
from typing import Optional
from pgdbm import AsyncDatabaseManager

from llmring_server.models.receipts import Receipt


class ReceiptsService:
    """Service for managing receipts."""

    def __init__(self, db: AsyncDatabaseManager):
        self.db = db

    async def store_receipt(self, api_key_id: str, receipt: Receipt) -> str:
        if not self._verify_signature(receipt):
            raise ValueError("Invalid receipt signature")

        query = """
            INSERT INTO {{tables.receipts}} (
                receipt_id, api_key_id, registry_version, model,
                tokens, cost, signature, metadata, receipt_timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """
        await self.db.fetch_one(
            query,
            receipt.id,
            api_key_id,
            receipt.registry_version,
            receipt.model,
            json.dumps(receipt.tokens.model_dump()),
            json.dumps(receipt.cost.model_dump()),
            receipt.signature,
            json.dumps({}),
            receipt.timestamp,
        )
        return receipt.id

    async def get_receipt(self, receipt_id: str, api_key_id: str) -> Optional[Receipt]:
        query = """
            SELECT * FROM {{tables.receipts}}
            WHERE receipt_id = $1 AND api_key_id = $2
        """
        result = await self.db.fetch_one(query, receipt_id, api_key_id)
        if not result:
            return None
        return Receipt(
            id=result["receipt_id"],
            timestamp=result["receipt_timestamp"],
            registry_version=result["registry_version"],
            model=result["model"],
            tokens=json.loads(result["tokens"]),
            cost=json.loads(result["cost"]),
            signature=result["signature"],
        )

    def _verify_signature(self, receipt: Receipt) -> bool:
        receipt_data = receipt.model_dump()
        stored_sig = receipt_data.pop("signature")
        content = json.dumps(receipt_data, sort_keys=True, default=str)
        expected_sig = hashlib.sha256(content.encode()).hexdigest()
        return stored_sig == expected_sig


