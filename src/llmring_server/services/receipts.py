import json
from typing import Optional
from pgdbm import AsyncDatabaseManager
from nacl import signing
import base64

from llmring_server.config import Settings
from llmring_server.models.receipts import Receipt
import rfc8785


settings = Settings()


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
                tokens, cost, signature, metadata, receipt_timestamp,
                alias, profile, lock_digest, key_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
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
            receipt.alias,
            receipt.profile,
            receipt.lock_digest,
            receipt.key_id,
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
            alias=result.get("alias"),
            profile=result.get("profile", "default"),
            lock_digest=result.get("lock_digest"),
            key_id=result.get("key_id", ""),
            tokens=json.loads(result["tokens"]),
            cost=json.loads(result["cost"]),
            signature=result["signature"],
        )

    def _verify_signature(self, receipt: Receipt) -> bool:
        try:
            sig = receipt.signature
            if not sig.startswith("ed25519:"):
                return False
            sig_b64 = sig.split(":", 1)[1]
            # Build canonical JSON without signature field
            data = receipt.model_dump()
            data.pop("signature", None)
            canonical = _canonicalize_bytes(data)
            verify_key_b64 = (
                settings.receipts_public_key_base64
                if hasattr(settings, "receipts_public_key_base64")
                else None
            )
            if not verify_key_b64:
                # If no public key configured, accept for dev only
                return False
            verify_key = signing.VerifyKey(_b64url_decode(verify_key_b64))
            verify_key.verify(canonical, _b64url_decode(sig_b64))
            return True
        except Exception:
            return False

    def issue_signature(self, payload_without_signature: dict) -> str:
        """Sign receipt payload using Ed25519 over JCS-canonicalized JSON.
        Returns signature string formatted as 'ed25519:<base64url>'.
        """
        private_key_b64 = getattr(settings, "receipts_private_key_base64", None)
        if not private_key_b64:
            raise RuntimeError("Signing key not configured")
        sign_key = signing.SigningKey(_b64url_decode(private_key_b64))
        canonical = _canonicalize_bytes(payload_without_signature)
        signed = sign_key.sign(canonical)
        sig = _b64url_encode(signed.signature)
        return f"ed25519:{sig}"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _canonicalize_bytes(obj: dict) -> bytes:
    # RFC 8785 JSON Canonicalization Scheme using rfc8785 lib
    out = rfc8785.dumps(obj)
    return out.encode("utf-8") if isinstance(out, str) else out
