"""Service for conversation and message management."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pgdbm import AsyncDatabaseManager

from llmring_server.config import MessageLoggingLevel, Settings
from llmring_server.models.conversations import (
    Conversation,
    ConversationCreate,
    ConversationUpdate,
    ConversationWithMessages,
    Message,
    MessageBatch,
    MessageCreate,
)
from llmring_server.models.usage import UsageLogRequest
from llmring_server.services.receipts import ReceiptsService


class ConversationService:
    """Service for managing conversations and messages."""

    def __init__(self, db: AsyncDatabaseManager, settings: Settings):
        self.db = db
        self.settings = settings

    async def create_conversation(self, conversation: ConversationCreate) -> Conversation:
        """Create a new conversation."""
        if not self.settings.enable_conversation_tracking:
            raise ValueError("Conversation tracking is disabled")

        query = """
            INSERT INTO {{tables.conversations}} (
                api_key_id, title, system_prompt, model_alias,
                temperature, max_tokens
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """

        result = await self.db.fetch_one(
            query,
            conversation.api_key_id,
            conversation.title,
            conversation.system_prompt,
            conversation.model_alias,
            conversation.temperature,
            conversation.max_tokens,
        )

        return Conversation(**result) if result else None

    async def get_conversation(
        self, conversation_id: UUID, api_key_id: Optional[str] = None
    ) -> Optional[Conversation]:
        """Get a conversation by ID."""
        query = """
            SELECT * FROM {{tables.conversations}}
            WHERE id = $1
        """
        params = [conversation_id]

        if api_key_id:
            query += " AND api_key_id = $2"
            params.append(api_key_id)

        result = await self.db.fetch_one(query, *params)
        return Conversation(**result) if result else None

    async def update_conversation(
        self,
        conversation_id: UUID,
        update: ConversationUpdate,
        api_key_id: Optional[str] = None,
    ) -> Optional[Conversation]:
        """Update a conversation."""
        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if update.title is not None:
            updates.append(f"title = ${param_count}")
            params.append(update.title)
            param_count += 1

        if update.system_prompt is not None:
            updates.append(f"system_prompt = ${param_count}")
            params.append(update.system_prompt)
            param_count += 1

        if update.model_alias is not None:
            updates.append(f"model_alias = ${param_count}")
            params.append(update.model_alias)
            param_count += 1

        if update.temperature is not None:
            updates.append(f"temperature = ${param_count}")
            params.append(update.temperature)
            param_count += 1

        if update.max_tokens is not None:
            updates.append(f"max_tokens = ${param_count}")
            params.append(update.max_tokens)
            param_count += 1

        if not updates:
            return await self.get_conversation(conversation_id, api_key_id)

        updates.append(f"updated_at = ${param_count}")
        params.append(datetime.now(timezone.utc))
        param_count += 1

        query = f"""
            UPDATE {{{{tables.conversations}}}}
            SET {', '.join(updates)}
            WHERE id = ${param_count}
        """
        params.append(conversation_id)
        param_count += 1

        if api_key_id:
            query += f" AND api_key_id = ${param_count}"
            params.append(api_key_id)

        query += " RETURNING *"

        result = await self.db.fetch_one(query, *params)
        return Conversation(**result) if result else None

    async def add_message(
        self,
        message: MessageCreate,
        logging_level: MessageLoggingLevel = MessageLoggingLevel.FULL,
    ) -> Message:
        """Add a message to a conversation."""
        if logging_level == MessageLoggingLevel.NONE:
            # Don't store message at all
            return None

        # Calculate content hash
        content_hash = None
        stored_content = None

        if message.content:
            content_hash = hashlib.sha256(message.content.encode()).hexdigest()

            if logging_level == MessageLoggingLevel.FULL:
                stored_content = message.content
            # For METADATA level, we store the hash but not the content

        query = """
            INSERT INTO {{tables.messages}} (
                conversation_id, receipt_id, role, content, content_hash,
                input_tokens, output_tokens, tool_calls, tool_results, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """

        result = await self.db.fetch_one(
            query,
            message.conversation_id,
            message.receipt_id,
            message.role,
            stored_content,  # None if metadata-only mode
            content_hash,
            message.input_tokens,
            message.output_tokens,
            json.dumps(message.tool_calls) if message.tool_calls else None,
            json.dumps(message.tool_results) if message.tool_results else None,
            json.dumps(message.metadata),
        )

        if result:
            # Parse JSON fields if they're strings
            if isinstance(result.get("metadata"), str):
                result["metadata"] = json.loads(result["metadata"])
            if isinstance(result.get("tool_calls"), str):
                result["tool_calls"] = json.loads(result["tool_calls"])
            if isinstance(result.get("tool_results"), str):
                result["tool_results"] = json.loads(result["tool_results"])
            return Message(**result)
        return None

    async def add_messages_batch(self, batch: MessageBatch) -> List[Message]:
        """Add multiple messages to a conversation."""
        messages = []

        for message_create in batch.messages:
            # Set conversation_id from batch
            message_create.conversation_id = batch.conversation_id

            message = await self.add_message(
                message_create, logging_level=MessageLoggingLevel(batch.logging_level)
            )
            if message:
                messages.append(message)

        return messages

    async def get_conversation_messages(
        self, conversation_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation."""
        query = """
            SELECT * FROM {{tables.messages}}
            WHERE conversation_id = $1
            ORDER BY timestamp ASC
            LIMIT $2 OFFSET $3
        """

        results = await self.db.fetch_all(query, conversation_id, limit, offset)
        messages = []
        for r in results:
            # Parse JSON fields if they're strings
            if isinstance(r.get("metadata"), str):
                r["metadata"] = json.loads(r["metadata"])
            if isinstance(r.get("tool_calls"), str):
                r["tool_calls"] = json.loads(r["tool_calls"])
            if isinstance(r.get("tool_results"), str):
                r["tool_results"] = json.loads(r["tool_results"])
            messages.append(Message(**r))
        return messages

    async def get_conversation_with_messages(
        self,
        conversation_id: UUID,
        api_key_id: Optional[str] = None,
        message_limit: int = 100,
    ) -> Optional[ConversationWithMessages]:
        """Get a conversation with its messages."""
        conversation = await self.get_conversation(conversation_id, api_key_id)
        if not conversation:
            return None

        messages = await self.get_conversation_messages(conversation_id, limit=message_limit)

        return ConversationWithMessages(**conversation.model_dump(), messages=messages)

    async def log_usage_with_conversation(
        self,
        api_key_id: str,
        usage_log: UsageLogRequest,
        cost: float,
        timestamp: datetime,
        conversation_id: Optional[UUID] = None,
        messages: Optional[List[Dict]] = None,
    ) -> Dict:
        """Log usage and optionally store messages."""
        # First, create the usage log with conversation_id
        query = """
            INSERT INTO {{tables.usage_logs}} (
                api_key_id, model, provider, input_tokens, output_tokens,
                cached_input_tokens, cost, latency_ms, origin, id_at_origin,
                created_at, metadata, alias, profile, conversation_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING id
        """

        usage_result = await self.db.fetch_one(
            query,
            api_key_id,
            usage_log.model,
            usage_log.provider,
            usage_log.input_tokens,
            usage_log.output_tokens,
            usage_log.cached_input_tokens,
            float(cost),
            usage_log.latency_ms,
            usage_log.origin,
            usage_log.id_at_origin,
            timestamp,
            json.dumps(usage_log.metadata),
            usage_log.alias,
            usage_log.profile or "default",
            conversation_id,
        )

        usage_id = str(usage_result["id"]) if usage_result else None

        # If we have messages and conversation tracking is enabled, store them
        stored_messages = []
        if (
            messages
            and conversation_id
            and self.settings.enable_conversation_tracking
            and self.settings.message_logging_level != MessageLoggingLevel.NONE
        ):
            for msg in messages:
                message_create = MessageCreate(
                    conversation_id=conversation_id,
                    role=msg.get("role"),
                    content=msg.get("content"),
                    tool_calls=msg.get("tool_calls"),
                    tool_results=msg.get("tool_results"),
                    metadata=msg.get("metadata", {}),
                )

                stored_message = await self.add_message(
                    message_create, logging_level=self.settings.message_logging_level
                )
                if stored_message:
                    stored_messages.append(stored_message)

        return {
            "usage_id": usage_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "messages_stored": len(stored_messages),
        }

    async def cleanup_old_messages(self, retention_days: Optional[int] = None) -> int:
        """Clean up old messages based on retention policy."""
        days = retention_days or self.settings.message_retention_days

        query = """
            DELETE FROM {{tables.messages}}
            WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '$1 days'
        """

        result = await self.db.execute(query, days)
        return result

    async def list_conversations(
        self, api_key_id: str, limit: int = 20, offset: int = 0
    ) -> List[Conversation]:
        """List conversations for an API key."""
        query = """
            SELECT * FROM {{tables.conversations}}
            WHERE api_key_id = $1
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3
        """

        results = await self.db.fetch_all(query, api_key_id, limit, offset)
        return [Conversation(**r) for r in results]

    async def log_conversation(
        self,
        api_key_id: str,
        messages: List[Dict[str, Any]],
        response: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Log a full conversation with messages and response.

        This method:
        1. Creates or finds a conversation
        2. Stores all messages (input + response)
        3. Generates receipt for the LLM API call
        4. Links receipt to assistant message
        5. Returns conversation_id, message_id, and receipt_id

        Args:
            api_key_id: API key that owns this conversation
            messages: List of message dicts (role, content)
            response: Response dict (content, model, finish_reason, usage)
            metadata: Metadata dict (provider, model, alias, cost, tokens, etc.)

        Returns:
            Dict with conversation_id, message_id, and receipt_id
        """
        if not self.settings.enable_conversation_tracking:
            raise ValueError("Conversation tracking is disabled")

        # Create a new conversation for this interaction
        # Use alias or model as the title
        title = f"{metadata.get('alias', metadata.get('model', 'unknown'))} conversation"

        conversation_create = ConversationCreate(
            api_key_id=api_key_id,
            title=title,
            model_alias=metadata.get("alias")
            or f"{metadata.get('provider')}:{metadata.get('model')}",
            temperature=0.7,  # Default, could be passed in metadata
        )

        conversation = await self.create_conversation(conversation_create)
        conversation_id = conversation.id

        # Calculate total cost from input_cost + output_cost if not explicitly provided
        total_cost = metadata.get("cost") or (
            (metadata.get("input_cost") or 0.0) + (metadata.get("output_cost") or 0.0)
        )

        # Store all input messages
        stored_messages = []
        for msg in messages:
            message_create = MessageCreate(
                conversation_id=conversation_id,
                role=msg.get("role", "user"),
                content=msg.get("content"),
                tool_calls=msg.get("tool_calls"),
                metadata=msg.get("metadata", {}),
            )

            stored_message = await self.add_message(
                message_create,
                logging_level=self.settings.message_logging_level,
            )
            if stored_message:
                stored_messages.append(stored_message)

        # Generate receipt for this LLM API call
        receipts_service = ReceiptsService(self.db, self.settings)

        # Calculate cost from registry if not provided
        input_tokens = metadata.get("input_tokens", 0)
        output_tokens = metadata.get("output_tokens", 0)

        if metadata.get("cost"):
            # Cost provided in metadata, use it
            total_cost = metadata.get("cost")
            # Estimate input/output split (simple heuristic)
            input_cost = total_cost * 0.25  # Rough estimate
            output_cost = total_cost * 0.75
        else:
            # Calculate from registry
            input_cost, output_cost, total_cost = (
                await receipts_service.calculate_cost_from_registry(
                    provider=metadata.get("provider", "unknown"),
                    model=response.get("model", metadata.get("model", "unknown")),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            )

        receipt, receipt_uuid = await receipts_service.generate_and_sign_receipt(
            api_key_id=api_key_id,
            alias=metadata.get("alias") or "default",
            profile=metadata.get("profile") or "default",
            lock_digest=metadata.get("lock_digest") or "",
            provider=metadata.get("provider") or "unknown",
            model=response.get("model") or metadata.get("model") or "unknown",
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            conversation_id=conversation_id,
        )

        # Store the assistant's response with receipt link (UUID not VARCHAR)
        # Note: response.model is the actual model returned by the LLM (e.g., "gpt-4-0613")
        # metadata.model is what the user requested (e.g., "gpt-4")
        # We prefer the actual model from the response
        assistant_message = MessageCreate(
            conversation_id=conversation_id,
            receipt_id=receipt_uuid,  # Link to the receipt's UUID in the database
            role="assistant",
            content=response.get("content"),
            tool_calls=response.get("tool_calls"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata={
                "model": response.get(
                    "model", metadata.get("model")
                ),  # Fallback to metadata if response doesn't have it
                "finish_reason": response.get("finish_reason"),
                "usage": response.get("usage", {}),
                "provider": metadata.get("provider"),  # Provider from metadata
                "cost": total_cost,
            },
        )

        response_message = await self.add_message(
            assistant_message,
            logging_level=self.settings.message_logging_level,
        )

        # Note: Conversation statistics (including cost) are automatically updated by the
        # database trigger (update_conversation_stats) when the message with receipt is inserted.
        # No manual cost update needed!

        return {
            "conversation_id": str(conversation_id),
            "message_id": str(response_message.id) if response_message else None,
            "receipt_id": receipt.receipt_id,
            "receipt": receipt,  # Return the full receipt object
            "messages_stored": len(stored_messages) + 1,
        }
