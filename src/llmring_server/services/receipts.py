"""Service for receipt generation, signing, and storage."""

import base64
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

import rfc8785
from nacl import signing
from pgdbm import AsyncDatabaseManager

from llmring_server.config import Settings
from llmring_server.models.receipts import (
    BatchReceipt,
    BatchReceiptSummary,
    Receipt,
    ReceiptGenerationRequest,
    UnsignedReceipt,
)
from llmring_server.services.registry import RegistryService


class ReceiptsService:
    """Service for managing receipts with Ed25519 signing."""

    def __init__(self, db: AsyncDatabaseManager, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or Settings()
        self.registry_service = RegistryService()

    async def calculate_cost_from_registry(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[float, float, float]:
        """
        Calculate cost from registry pricing.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")
            model: Model name (e.g., "gpt-4o-2024-08-06")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Tuple of (input_cost, output_cost, total_cost) in USD
        """
        try:
            registry = await self.registry_service.get_registry()
            model_key = f"{provider}:{model}"

            model_info = registry.models.get(model_key)
            if not model_info:
                # Try without provider prefix
                model_info = registry.models.get(model)

            if not model_info or not model_info.dollars_per_million_tokens_input:
                # Fallback to zero cost if model not found or pricing not available
                return (0.0, 0.0, 0.0)

            input_cost = (input_tokens / 1_000_000) * model_info.dollars_per_million_tokens_input
            output_cost = (output_tokens / 1_000_000) * model_info.dollars_per_million_tokens_output
            total_cost = input_cost + output_cost

            return (input_cost, output_cost, total_cost)
        except Exception:
            # If registry lookup fails, return zero cost
            return (0.0, 0.0, 0.0)

    async def generate_and_sign_receipt(
        self,
        api_key_id: str,
        alias: str,
        profile: str,
        lock_digest: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        input_cost: float,
        output_cost: float,
        conversation_id: Optional[UUID] = None,
    ) -> tuple[Receipt, UUID]:
        """
        Generate and sign a receipt for an LLM API call.

        This is the canonical method for creating receipts server-side.
        It generates an unsigned receipt, signs it with Ed25519, stores it,
        and returns the signed receipt along with its database UUID.

        Args:
            api_key_id: API key that owns this receipt
            alias: Alias used for the request
            profile: Profile used (e.g., "default", "prod")
            lock_digest: SHA256 digest of lockfile
            provider: Provider used (e.g., "openai", "anthropic")
            model: Model used (e.g., "gpt-4", "claude-3-opus")
            prompt_tokens: Input token count
            completion_tokens: Output token count
            input_cost: Cost for input tokens in USD
            output_cost: Cost for output tokens in USD
            conversation_id: Optional conversation ID to link receipt

        Returns:
            Tuple of (Signed Receipt object, database UUID)
        """
        # Create unsigned receipt
        unsigned = UnsignedReceipt(
            alias=alias,
            profile=profile,
            lock_digest=lock_digest,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
        )

        # Sign the receipt
        payload = unsigned.model_dump()
        signature = self._issue_signature(payload)

        # Create signed receipt
        signed_receipt = Receipt(**payload, signature=signature)

        # Store in database and get UUID
        receipt_uuid = await self._store_receipt(api_key_id, signed_receipt, conversation_id)

        return signed_receipt, receipt_uuid

    async def _store_receipt(
        self, api_key_id: str, receipt: Receipt, conversation_id: Optional[UUID] = None
    ) -> UUID:
        """Store a signed receipt in the database and return its UUID."""
        # Store in new flat schema matching the Receipt model
        query = """
            INSERT INTO {{tables.receipts}} (
                receipt_id, api_key_id, model, provider, alias, profile,
                lock_digest, signature, receipt_timestamp, conversation_id,
                tokens, cost, registry_version, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING id
        """

        # Store tokens and cost as JSONB for backward compatibility with existing schema
        tokens_json = json.dumps(
            {
                "input": receipt.prompt_tokens,
                "output": receipt.completion_tokens,
                "cached_input": 0,
            }
        )
        cost_json = json.dumps(
            {
                "input": receipt.input_cost,
                "output": receipt.output_cost,
                "total": receipt.total_cost,
            }
        )

        # Convert timestamp to naive if timezone-aware (database uses TIMESTAMP not TIMESTAMPTZ)
        timestamp_to_store = receipt.timestamp
        if timestamp_to_store.tzinfo is not None:
            timestamp_to_store = timestamp_to_store.replace(tzinfo=None)

        result = await self.db.fetch_one(
            query,
            receipt.receipt_id,
            api_key_id,
            receipt.model,
            receipt.provider,
            receipt.alias,
            receipt.profile,
            receipt.lock_digest,
            receipt.signature,
            timestamp_to_store,
            conversation_id,
            tokens_json,
            cost_json,
            "v1",  # registry_version - deprecated but kept for schema compatibility
            json.dumps({}),  # metadata
        )
        return result["id"] if result else None

    async def store_receipt(self, api_key_id: str, receipt: Receipt) -> str:
        """Store an externally-generated signed receipt."""
        if not self._verify_signature(receipt):
            raise ValueError("Invalid receipt signature")

        return await self._store_receipt(api_key_id, receipt)

    async def get_receipt(self, receipt_id: str, api_key_id: str) -> Optional[Receipt]:
        """Get a receipt by ID."""
        query = """
            SELECT * FROM {{tables.receipts}}
            WHERE receipt_id = $1 AND api_key_id = $2
        """
        result = await self.db.fetch_one(query, receipt_id, api_key_id)
        if not result:
            return None

        # Parse JSONB fields
        tokens = json.loads(result["tokens"])
        cost = json.loads(result["cost"])

        return Receipt(
            receipt_id=result["receipt_id"],
            timestamp=result["receipt_timestamp"],
            alias=result.get("alias", ""),
            profile=result.get("profile", "default"),
            lock_digest=result.get("lock_digest", ""),
            provider=result.get("provider", "unknown"),
            model=result["model"],
            prompt_tokens=tokens.get("input", 0),
            completion_tokens=tokens.get("output", 0),
            total_tokens=tokens.get("input", 0) + tokens.get("output", 0),
            input_cost=cost.get("input", 0.0),
            output_cost=cost.get("output", 0.0),
            total_cost=cost.get("total", 0.0),
            signature=result["signature"],
        )

    async def list_receipts(
        self, api_key_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[Receipt], int]:
        """List receipts for an API key with pagination."""
        # Get total count
        count_query = """
            SELECT COUNT(*) as total FROM {{tables.receipts}}
            WHERE api_key_id = $1
        """
        count_result = await self.db.fetch_one(count_query, api_key_id)
        total = count_result["total"] if count_result else 0

        # Get receipts
        query = """
            SELECT * FROM {{tables.receipts}}
            WHERE api_key_id = $1
            ORDER BY receipt_timestamp DESC
            LIMIT $2 OFFSET $3
        """
        results = await self.db.fetch_all(query, api_key_id, limit, offset)

        receipts = []
        for result in results:
            tokens = json.loads(result["tokens"])
            cost = json.loads(result["cost"])

            receipts.append(
                Receipt(
                    receipt_id=result["receipt_id"],
                    timestamp=result["receipt_timestamp"],
                    alias=result.get("alias", ""),
                    profile=result.get("profile", "default"),
                    lock_digest=result.get("lock_digest", ""),
                    provider=result.get("provider", "unknown"),
                    model=result["model"],
                    prompt_tokens=tokens.get("input", 0),
                    completion_tokens=tokens.get("output", 0),
                    total_tokens=tokens.get("input", 0) + tokens.get("output", 0),
                    input_cost=cost.get("input", 0.0),
                    output_cost=cost.get("output", 0.0),
                    total_cost=cost.get("total", 0.0),
                    signature=result["signature"],
                )
            )

        return receipts, total

    def _verify_signature(self, receipt: Receipt) -> bool:
        """Verify a receipt's Ed25519 signature."""
        try:
            if not receipt.signature:
                return False

            sig = receipt.signature
            if not sig.startswith("ed25519:"):
                return False

            sig_b64 = sig.split(":", 1)[1]

            # Build canonical JSON without signature field
            # Also exclude BatchReceipt-specific fields as signature is only on base Receipt
            data = receipt.model_dump(
                exclude={"signature", "receipt_type", "batch_summary", "description", "tags"}
            )
            # Convert datetime to ISO format for canonicalization
            if isinstance(data.get("timestamp"), datetime):
                data["timestamp"] = data["timestamp"].isoformat()
            canonical = _canonicalize_bytes(data)

            # Get public key from settings
            verify_key_b64 = self.settings.receipts_public_key_base64
            if not verify_key_b64:
                raise RuntimeError("Public key not configured for verification")

            verify_key = signing.VerifyKey(_b64url_decode(verify_key_b64))
            verify_key.verify(canonical, _b64url_decode(sig_b64))
            return True

        except Exception:
            return False

    def _issue_signature(self, payload_without_signature: dict) -> str:
        """
        Sign receipt payload using Ed25519 over JCS-canonicalized JSON.

        Args:
            payload_without_signature: Receipt data as dict (without signature field)

        Returns:
            Signature string formatted as 'ed25519:<base64url>'
        """
        private_key_b64 = self.settings.receipts_private_key_base64
        if not private_key_b64:
            raise RuntimeError("Signing key not configured")

        # Convert datetime to ISO format for canonicalization
        if isinstance(payload_without_signature.get("timestamp"), datetime):
            payload_without_signature["timestamp"] = payload_without_signature[
                "timestamp"
            ].isoformat()

        sign_key = signing.SigningKey(_b64url_decode(private_key_b64))
        canonical = _canonicalize_bytes(payload_without_signature)
        signed = sign_key.sign(canonical)
        sig = _b64url_encode(signed.signature)
        return f"ed25519:{sig}"

    def get_public_key_pem(self) -> str:
        """Get the public key in PEM format for verification."""
        public_key_b64 = self.settings.receipts_public_key_base64
        if not public_key_b64:
            raise RuntimeError("Public key not configured")

        # Convert base64url to PEM format
        public_key_bytes = _b64url_decode(public_key_b64)
        pem_header = "-----BEGIN PUBLIC KEY-----\n"
        pem_footer = "\n-----END PUBLIC KEY-----\n"

        # Base64 encode with line breaks
        b64_key = base64.b64encode(public_key_bytes).decode()
        pem_body = "\n".join([b64_key[i : i + 64] for i in range(0, len(b64_key), 64)])

        return f"{pem_header}{pem_body}{pem_footer}"

    # =====================================================
    # Phase 7.5: On-Demand Receipt Generation
    # =====================================================

    async def generate_on_demand_receipt(
        self,
        api_key_id: str,
        request: ReceiptGenerationRequest,
    ) -> tuple[BatchReceipt, int]:
        """
        Generate a receipt on-demand based on the request parameters.

        This is the main entry point for Phase 7.5 on-demand receipt generation.
        Supports four modes:
        1. Single conversation
        2. Date range (batch)
        3. Specific log IDs
        4. Since last receipt

        Returns:
            tuple: (BatchReceipt, certified_count)
        """
        # Determine which mode and fetch the appropriate logs
        if request.conversation_id:
            # Single conversation mode
            logs = await self._fetch_conversation_logs(api_key_id, request.conversation_id)
            log_type = "conversation"
        elif request.start_date and request.end_date:
            # Date range batch mode
            logs = await self._fetch_logs_by_date_range(
                api_key_id, request.start_date, request.end_date
            )
            log_type = "mixed"
        elif request.log_ids:
            # Specific log IDs mode
            logs = await self._fetch_logs_by_ids(api_key_id, request.log_ids)
            log_type = "mixed"
        elif request.since_last_receipt:
            # Since last receipt mode
            logs = await self._fetch_uncertified_logs(api_key_id)
            log_type = "mixed"
        else:
            raise ValueError(
                "Must specify one of: conversation_id, date range, log_ids, or since_last_receipt"
            )

        if not logs:
            raise ValueError("No logs found matching the criteria")

        # Generate the batch receipt
        receipt = await self._create_batch_receipt(
            api_key_id=api_key_id,
            logs=logs,
            log_type=log_type,
            description=request.description,
            tags=request.tags,
        )

        # Link receipt to logs
        await self._link_receipt_to_logs(receipt.receipt_id, logs, log_type)

        return receipt, len(logs)

    async def _fetch_conversation_logs(self, api_key_id: str, conversation_id: UUID) -> list[dict]:
        """Fetch logs for a single conversation."""
        query = """
            SELECT
                c.id as conversation_id,
                c.model_alias,
                c.total_input_tokens,
                c.total_output_tokens,
                c.total_cost,
                c.created_at
            FROM {{tables.conversations}} c
            WHERE c.id = $1 AND c.api_key_id = $2
        """
        result = await self.db.fetch_one(query, conversation_id, api_key_id)
        if not result:
            return []

        # Also get messages to extract provider/model
        msg_query = """
            SELECT metadata FROM {{tables.messages}}
            WHERE conversation_id = $1
            ORDER BY timestamp DESC
            LIMIT 1
        """
        msg_result = await self.db.fetch_one(msg_query, conversation_id)

        metadata = (
            json.loads(msg_result["metadata"]) if msg_result and msg_result.get("metadata") else {}
        )

        return [
            {
                "id": str(result["conversation_id"]),
                "type": "conversation",
                "alias": result.get("model_alias") or "default",
                "provider": metadata.get("provider", "unknown"),
                "model": metadata.get("model", "unknown"),
                "input_tokens": result["total_input_tokens"] or 0,
                "output_tokens": result["total_output_tokens"] or 0,
                "cost": float(result["total_cost"]) if result["total_cost"] else 0.0,
                "timestamp": result["created_at"],
            }
        ]

    async def _fetch_logs_by_date_range(
        self, api_key_id: str, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """Fetch logs within a date range."""
        # Fetch from both conversations and usage_logs
        conv_query = """
            SELECT
                c.id,
                'conversation' as type,
                c.model_alias as alias,
                c.total_input_tokens as input_tokens,
                c.total_output_tokens as output_tokens,
                c.total_cost as cost,
                c.created_at as timestamp
            FROM {{tables.conversations}} c
            WHERE c.api_key_id = $1
              AND c.created_at >= $2
              AND c.created_at <= $3
            ORDER BY c.created_at DESC
        """
        conversations = await self.db.fetch_all(conv_query, api_key_id, start_date, end_date)

        usage_query = """
            SELECT
                u.id,
                'usage' as type,
                u.alias,
                u.provider,
                u.model,
                u.input_tokens,
                u.output_tokens,
                u.cost,
                u.created_at as timestamp
            FROM {{tables.usage_logs}} u
            WHERE u.api_key_id = $1
              AND u.created_at >= $2
              AND u.created_at <= $3
              AND u.conversation_id IS NULL
            ORDER BY u.created_at DESC
        """
        usage_logs = await self.db.fetch_all(usage_query, api_key_id, start_date, end_date)

        # Combine and normalize
        all_logs = []
        for conv in conversations:
            all_logs.append(
                {
                    "id": str(conv["id"]),
                    "type": "conversation",
                    "alias": conv.get("alias") or "default",
                    "provider": "unknown",  # Would need to fetch from messages
                    "model": "unknown",
                    "input_tokens": conv.get("input_tokens") or 0,
                    "output_tokens": conv.get("output_tokens") or 0,
                    "cost": float(conv["cost"]) if conv.get("cost") else 0.0,
                    "timestamp": conv["timestamp"],
                }
            )

        for log in usage_logs:
            all_logs.append(
                {
                    "id": str(log["id"]),
                    "type": "usage",
                    "alias": log.get("alias") or "default",
                    "provider": log.get("provider", "unknown"),
                    "model": log.get("model", "unknown"),
                    "input_tokens": log.get("input_tokens") or 0,
                    "output_tokens": log.get("output_tokens") or 0,
                    "cost": float(log["cost"]) if log.get("cost") else 0.0,
                    "timestamp": log["timestamp"],
                }
            )

        return all_logs

    async def _fetch_logs_by_ids(self, api_key_id: str, log_ids: list[UUID]) -> list[dict]:
        """Fetch specific logs by IDs."""
        # Similar to date range but filter by IDs
        # For simplicity, try conversations first, then usage logs
        all_logs = []

        if log_ids:
            conv_query = """
                SELECT
                    c.id,
                    'conversation' as type,
                    c.model_alias as alias,
                    c.total_input_tokens as input_tokens,
                    c.total_output_tokens as output_tokens,
                    c.total_cost as cost,
                    c.created_at as timestamp
                FROM {{tables.conversations}} c
                WHERE c.api_key_id = $1 AND c.id = ANY($2)
            """
            conversations = await self.db.fetch_all(conv_query, api_key_id, log_ids)

            usage_query = """
                SELECT
                    u.id,
                    'usage' as type,
                    u.alias,
                    u.provider,
                    u.model,
                    u.input_tokens,
                    u.output_tokens,
                    u.cost,
                    u.created_at as timestamp
                FROM {{tables.usage_logs}} u
                WHERE u.api_key_id = $1 AND u.id = ANY($2)
            """
            usage_logs = await self.db.fetch_all(usage_query, api_key_id, log_ids)

            for conv in conversations:
                all_logs.append(
                    {
                        "id": str(conv["id"]),
                        "type": "conversation",
                        "alias": conv.get("alias") or "default",
                        "provider": "unknown",
                        "model": "unknown",
                        "input_tokens": conv.get("input_tokens") or 0,
                        "output_tokens": conv.get("output_tokens") or 0,
                        "cost": float(conv["cost"]) if conv.get("cost") else 0.0,
                        "timestamp": conv["timestamp"],
                    }
                )

            for log in usage_logs:
                all_logs.append(
                    {
                        "id": str(log["id"]),
                        "type": "usage",
                        "alias": log.get("alias") or "default",
                        "provider": log.get("provider", "unknown"),
                        "model": log.get("model", "unknown"),
                        "input_tokens": log.get("input_tokens") or 0,
                        "output_tokens": log.get("output_tokens") or 0,
                        "cost": float(log["cost"]) if log.get("cost") else 0.0,
                        "timestamp": log["timestamp"],
                    }
                )

        return all_logs

    async def _fetch_uncertified_logs(self, api_key_id: str) -> list[dict]:
        """Fetch logs that haven't been certified by any receipt."""
        # Find conversations not in receipt_logs
        conv_query = """
            SELECT
                c.id,
                'conversation' as type,
                c.model_alias as alias,
                c.total_input_tokens as input_tokens,
                c.total_output_tokens as output_tokens,
                c.total_cost as cost,
                c.created_at as timestamp
            FROM {{tables.conversations}} c
            WHERE c.api_key_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM {{tables.receipt_logs}} rl
                  WHERE rl.log_id = c.id AND rl.log_type = 'conversation'
              )
            ORDER BY c.created_at DESC
        """
        conversations = await self.db.fetch_all(conv_query, api_key_id)

        usage_query = """
            SELECT
                u.id,
                'usage' as type,
                u.alias,
                u.provider,
                u.model,
                u.input_tokens,
                u.output_tokens,
                u.cost,
                u.created_at as timestamp
            FROM {{tables.usage_logs}} u
            WHERE u.api_key_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM {{tables.receipt_logs}} rl
                  WHERE rl.log_id = u.id AND rl.log_type = 'usage'
              )
            ORDER BY u.created_at DESC
        """
        usage_logs = await self.db.fetch_all(usage_query, api_key_id)

        all_logs = []
        for conv in conversations:
            all_logs.append(
                {
                    "id": str(conv["id"]),
                    "type": "conversation",
                    "alias": conv.get("alias") or "default",
                    "provider": "unknown",
                    "model": "unknown",
                    "input_tokens": conv.get("input_tokens") or 0,
                    "output_tokens": conv.get("output_tokens") or 0,
                    "cost": float(conv["cost"]) if conv.get("cost") else 0.0,
                    "timestamp": conv["timestamp"],
                }
            )

        for log in usage_logs:
            all_logs.append(
                {
                    "id": str(log["id"]),
                    "type": "usage",
                    "alias": log.get("alias") or "default",
                    "provider": log.get("provider", "unknown"),
                    "model": log.get("model", "unknown"),
                    "input_tokens": log.get("input_tokens") or 0,
                    "output_tokens": log.get("output_tokens") or 0,
                    "cost": float(log["cost"]) if log.get("cost") else 0.0,
                    "timestamp": log["timestamp"],
                }
            )

        return all_logs

    async def _create_batch_receipt(
        self,
        api_key_id: str,
        logs: list[dict],
        log_type: str,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> BatchReceipt:
        """Create a batch receipt from aggregated logs."""
        # Aggregate statistics
        total_input_tokens = sum(log.get("input_tokens", 0) for log in logs)
        total_output_tokens = sum(log.get("output_tokens", 0) for log in logs)
        total_cost = sum(log.get("cost", 0.0) for log in logs)

        # Breakdown by model and alias
        by_model = {}
        by_alias = {}
        conversation_ids = []
        log_ids = []

        for log in logs:
            model = log.get("model", "unknown")
            alias = log.get("alias", "default")

            # By model
            if model not in by_model:
                by_model[model] = {"calls": 0, "cost": 0.0, "tokens": 0}
            by_model[model]["calls"] += 1
            by_model[model]["cost"] += log.get("cost", 0.0)
            by_model[model]["tokens"] += log.get("input_tokens", 0) + log.get("output_tokens", 0)

            # By alias
            if alias not in by_alias:
                by_alias[alias] = {"calls": 0, "cost": 0.0, "tokens": 0}
            by_alias[alias]["calls"] += 1
            by_alias[alias]["cost"] += log.get("cost", 0.0)
            by_alias[alias]["tokens"] += log.get("input_tokens", 0) + log.get("output_tokens", 0)

            # Track IDs
            if log["type"] == "conversation":
                conversation_ids.append(log["id"])
            else:
                log_ids.append(log["id"])

        # Determine date range
        timestamps = [log["timestamp"] for log in logs if log.get("timestamp")]
        start_date = min(timestamps).isoformat() if timestamps else None
        end_date = max(timestamps).isoformat() if timestamps else None

        # Create batch summary
        batch_summary = BatchReceiptSummary(
            total_conversations=len(conversation_ids),
            total_calls=len(logs),
            total_tokens=total_input_tokens + total_output_tokens,
            total_cost=total_cost,
            start_date=start_date,
            end_date=end_date,
            by_model=by_model,
            by_alias=by_alias,
            conversation_ids=conversation_ids,
            log_ids=log_ids,
        )

        # Create the receipt (use aggregated values)
        # For batch, we use a summary representation
        receipt_type = "single" if len(logs) == 1 else "batch"
        primary_log = logs[0] if logs else {}

        unsigned = UnsignedReceipt(
            alias=primary_log.get("alias", "batch"),
            profile="default",
            lock_digest="",
            provider=primary_log.get("provider", "batch"),
            model=(
                primary_log.get("model", "batch")
                if receipt_type == "single"
                else f"batch:{len(logs)} calls"
            ),
            prompt_tokens=total_input_tokens,
            completion_tokens=total_output_tokens,
            total_tokens=total_input_tokens + total_output_tokens,
            input_cost=0.0,  # Cost split not available for batch
            output_cost=0.0,
            total_cost=total_cost,
        )

        # Sign the receipt
        payload = unsigned.model_dump()
        signature = self._issue_signature(payload)

        # Create BatchReceipt with extended fields
        batch_receipt = BatchReceipt(
            **payload,
            signature=signature,
            receipt_type=receipt_type,
            batch_summary=batch_summary,
            description=description,
            tags=tags,
        )

        # Store in database
        await self._store_batch_receipt(api_key_id, batch_receipt)

        return batch_receipt

    async def _store_batch_receipt(self, api_key_id: str, receipt: BatchReceipt) -> str:
        """Store a batch receipt in the database."""
        query = """
            INSERT INTO {{tables.receipts}} (
                receipt_id, api_key_id, model, provider, alias, profile,
                lock_digest, signature, receipt_timestamp,
                tokens, cost, registry_version, metadata,
                receipt_type, batch_summary, description, tags
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            RETURNING id
        """

        # Store tokens and cost as JSONB
        tokens_json = json.dumps(
            {
                "input": receipt.prompt_tokens,
                "output": receipt.completion_tokens,
                "cached_input": 0,
            }
        )
        cost_json = json.dumps(
            {
                "input": receipt.input_cost,
                "output": receipt.output_cost,
                "total": receipt.total_cost,
            }
        )

        # Convert timestamp to naive if timezone-aware
        timestamp_to_store = receipt.timestamp
        if timestamp_to_store.tzinfo is not None:
            timestamp_to_store = timestamp_to_store.replace(tzinfo=None)

        # Convert batch_summary to JSON if present
        batch_summary_json = None
        if receipt.batch_summary:
            batch_summary_json = json.dumps(receipt.batch_summary.model_dump())

        # Convert tags to JSON if present
        tags_json = None
        if receipt.tags:
            tags_json = json.dumps(receipt.tags)

        await self.db.fetch_one(
            query,
            receipt.receipt_id,
            api_key_id,
            receipt.model,
            receipt.provider,
            receipt.alias,
            receipt.profile,
            receipt.lock_digest,
            receipt.signature,
            timestamp_to_store,
            tokens_json,
            cost_json,
            "v1",  # registry_version
            json.dumps({}),  # metadata
            receipt.receipt_type,
            batch_summary_json,
            receipt.description,
            tags_json,
        )
        return receipt.receipt_id

    async def _link_receipt_to_logs(self, receipt_id: str, logs: list[dict], log_type: str) -> None:
        """Link a receipt to the logs it certifies."""
        # Insert into receipt_logs table
        for log in logs:
            link_query = """
                INSERT INTO {{tables.receipt_logs}} (receipt_id, log_id, log_type)
                VALUES ($1, $2, $3)
                ON CONFLICT (receipt_id, log_id) DO NOTHING
            """
            await self.db.execute(link_query, receipt_id, UUID(log["id"]), log["type"])

    async def preview_receipt(
        self,
        api_key_id: str,
        request: ReceiptGenerationRequest,
    ) -> dict:
        """
        Preview what a receipt would certify without actually generating it.

        Returns a summary of what would be included in the receipt.
        """
        # Determine which mode and fetch the appropriate logs
        if request.conversation_id:
            logs = await self._fetch_conversation_logs(api_key_id, request.conversation_id)
        elif request.start_date and request.end_date:
            logs = await self._fetch_logs_by_date_range(
                api_key_id, request.start_date, request.end_date
            )
        elif request.log_ids:
            logs = await self._fetch_logs_by_ids(api_key_id, request.log_ids)
        elif request.since_last_receipt:
            logs = await self._fetch_uncertified_logs(api_key_id)
        else:
            raise ValueError(
                "Must specify one of: conversation_id, date range, log_ids, or since_last_receipt"
            )

        if not logs:
            return {
                "total_logs": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "message": "No logs found matching the criteria",
            }

        # Calculate statistics without generating receipt
        total_input_tokens = sum(log.get("input_tokens", 0) for log in logs)
        total_output_tokens = sum(log.get("output_tokens", 0) for log in logs)
        total_cost = sum(log.get("cost", 0.0) for log in logs)

        by_model = {}
        by_alias = {}

        for log in logs:
            model = log.get("model", "unknown")
            alias = log.get("alias", "default")

            if model not in by_model:
                by_model[model] = {"calls": 0, "cost": 0.0, "tokens": 0}
            by_model[model]["calls"] += 1
            by_model[model]["cost"] += log.get("cost", 0.0)
            by_model[model]["tokens"] += log.get("input_tokens", 0) + log.get("output_tokens", 0)

            if alias not in by_alias:
                by_alias[alias] = {"calls": 0, "cost": 0.0, "tokens": 0}
            by_alias[alias]["calls"] += 1
            by_alias[alias]["cost"] += log.get("cost", 0.0)
            by_alias[alias]["tokens"] += log.get("input_tokens", 0) + log.get("output_tokens", 0)

        timestamps = [log["timestamp"] for log in logs if log.get("timestamp")]
        start_date = min(timestamps).isoformat() if timestamps else None
        end_date = max(timestamps).isoformat() if timestamps else None

        return {
            "total_logs": len(logs),
            "total_conversations": len([l for l in logs if l["type"] == "conversation"]),
            "total_tokens": total_input_tokens + total_output_tokens,
            "total_cost": total_cost,
            "start_date": start_date,
            "end_date": end_date,
            "by_model": by_model,
            "by_alias": by_alias,
            "receipt_type": "single" if len(logs) == 1 else "batch",
        }

    async def get_uncertified_logs(
        self, api_key_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict], int]:
        """
        Get logs that haven't been certified by any receipt.

        Returns tuple of (logs, total_count).
        """
        logs = await self._fetch_uncertified_logs(api_key_id)
        total = len(logs)

        # Apply pagination
        paginated_logs = logs[offset : offset + limit]

        return paginated_logs, total

    async def get_logs_for_receipt(
        self, receipt_id: str, api_key_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict], int]:
        """
        Get all logs certified by a specific receipt.
        """
        # First verify the receipt belongs to this API key
        receipt = await self.get_receipt(receipt_id, api_key_id)
        if not receipt:
            raise ValueError("Receipt not found or access denied")

        # Get linked logs
        query = """
            SELECT rl.log_id, rl.log_type, rl.certified_at
            FROM {{tables.receipt_logs}} rl
            WHERE rl.receipt_id = $1
            ORDER BY rl.certified_at DESC
            LIMIT $2 OFFSET $3
        """
        links = await self.db.fetch_all(query, receipt_id, limit, offset)

        # Get total count
        count_query = """
            SELECT COUNT(*) as total
            FROM {{tables.receipt_logs}}
            WHERE receipt_id = $1
        """
        count_result = await self.db.fetch_one(count_query, receipt_id)
        total = count_result["total"] if count_result else 0

        # Fetch full log details
        logs = []
        for link in links:
            log_id = link["log_id"]
            log_type = link["log_type"]

            if log_type == "conversation":
                conv_query = """
                    SELECT c.*, 'conversation' as type
                    FROM {{tables.conversations}} c
                    WHERE c.id = $1
                """
                log_data = await self.db.fetch_one(conv_query, log_id)
            else:
                usage_query = """
                    SELECT u.*, 'usage' as type
                    FROM {{tables.usage_logs}} u
                    WHERE u.id = $1
                """
                log_data = await self.db.fetch_one(usage_query, log_id)

            if log_data:
                logs.append(dict(log_data))

        return logs, total


def _b64url_encode(data: bytes) -> str:
    """Encode bytes as base64url (no padding)."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    """Decode base64url string (add padding if needed)."""
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _canonicalize_bytes(obj: dict) -> bytes:
    """Canonicalize dict to bytes using RFC 8785 JCS."""
    out = rfc8785.dumps(obj)
    return out.encode("utf-8") if isinstance(out, str) else out
