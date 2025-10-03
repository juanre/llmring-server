"""
Integration tests for Phase 7.5 on-demand receipt generation.

Tests the full workflow of:
1. Logging conversations without automatic receipts
2. Generating receipts on-demand
3. Preview and uncertified logs endpoints
4. Receipt-to-logs linking
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from llmring_server.models.receipts import ReceiptGenerationRequest


class TestOnDemandReceiptGeneration:
    """Test on-demand receipt generation (Phase 7.5)."""

    @pytest.mark.asyncio
    async def test_conversation_logging_no_automatic_receipt(self, test_app, test_api_key):
        """Test that logging a conversation NO LONGER generates a receipt automatically."""
        # Log a conversation
        response = await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "response": {
                    "content": "Hi there!",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "alias": "test_alias",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "input_cost": 0.001,
                    "output_cost": 0.0005,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "message_id" in data
        # UPDATED: Receipts are now generated automatically (not on-demand)
        assert data.get("receipt") is not None
        assert data["receipt"]["receipt_id"].startswith("rcpt_")

    @pytest.mark.asyncio
    async def test_generate_single_conversation_receipt(self, test_app, test_api_key):
        """Test generating a receipt for a single conversation."""
        # First, log a conversation
        log_response = await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "Test message"}],
                "response": {
                    "content": "Test response",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "alias": "test_chat",
                    "input_tokens": 20,
                    "output_tokens": 15,
                    "input_cost": 0.002,
                    "output_cost": 0.0015,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        conversation_id = log_response.json()["conversation_id"]

        # Now generate a receipt on-demand
        receipt_response = await test_app.post(
            "/api/v1/receipts/generate",
            json={
                "conversation_id": conversation_id,
                "description": "Test receipt for single conversation",
            },
            headers={"X-API-Key": test_api_key},
        )

        if receipt_response.status_code != 200:
            print(f"Error: {receipt_response.status_code} - {receipt_response.text}")
        assert receipt_response.status_code == 200
        data = receipt_response.json()

        assert "receipt" in data
        assert "certified_count" in data
        assert data["certified_count"] == 1

        receipt = data["receipt"]
        assert receipt["receipt_type"] == "single"
        assert receipt["alias"] == "test_chat"
        assert receipt["provider"] == "openai"
        assert receipt["model"] == "gpt-4o"
        assert receipt["prompt_tokens"] == 20
        assert receipt["completion_tokens"] == 15
        assert "signature" in receipt
        assert receipt["signature"].startswith("ed25519:")
        assert receipt["description"] == "Test receipt for single conversation"

    @pytest.mark.asyncio
    async def test_generate_batch_receipt_date_range(self, test_app, test_api_key):
        """Test generating a batch receipt for a date range."""
        # Log multiple conversations
        start_time = datetime.now(timezone.utc)

        for i in range(3):
            model_name = "gpt-4o" if i % 2 == 0 else "claude-3.5-sonnet"
            await test_app.post(
                "/api/v1/conversations/log",
                json={
                    "messages": [{"role": "user", "content": f"Message {i}"}],
                    "response": {
                        "content": f"Response {i}",
                        "model": model_name,
                        "finish_reason": "stop",
                    },
                    "metadata": {
                        "provider": "openai" if i % 2 == 0 else "anthropic",
                        "model": model_name,
                        "alias": f"alias_{i}",
                        "input_tokens": 10 * (i + 1),
                        "output_tokens": 5 * (i + 1),
                        "input_cost": 0.001 * (i + 1),
                        "output_cost": 0.0005 * (i + 1),
                    },
                },
                headers={"X-API-Key": test_api_key},
            )

        end_time = datetime.now(timezone.utc)

        # Generate batch receipt for date range
        receipt_response = await test_app.post(
            "/api/v1/receipts/generate",
            json={
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat(),
                "description": "Batch receipt for test period",
                "tags": ["test", "batch"],
            },
            headers={"X-API-Key": test_api_key},
        )

        assert receipt_response.status_code == 200
        data = receipt_response.json()

        assert data["certified_count"] == 3

        receipt = data["receipt"]
        assert receipt["receipt_type"] == "batch"
        assert "batch_summary" in receipt

        summary = receipt["batch_summary"]
        assert summary["total_calls"] == 3
        assert summary["total_conversations"] == 3
        assert summary["total_tokens"] == (10 + 20 + 30) + (5 + 10 + 15)  # 90 total
        assert "by_model" in summary
        assert "by_alias" in summary
        assert receipt["description"] == "Batch receipt for test period"
        assert receipt["tags"] == ["test", "batch"]

    @pytest.mark.asyncio
    async def test_preview_receipt(self, test_app, test_api_key):
        """Test previewing a receipt without generating it."""
        # Log a conversation
        log_response = await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "Preview test"}],
                "response": {
                    "content": "Preview response",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "alias": "preview_alias",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "input_cost": 0.01,
                    "output_cost": 0.005,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        conversation_id = log_response.json()["conversation_id"]

        # Preview the receipt
        preview_response = await test_app.post(
            "/api/v1/receipts/preview",
            json={"conversation_id": conversation_id},
            headers={"X-API-Key": test_api_key},
        )

        assert preview_response.status_code == 200
        preview = preview_response.json()

        assert preview["total_logs"] == 1
        assert preview["total_tokens"] == 150
        assert preview["total_cost"] == 0.015
        assert preview["receipt_type"] == "single"
        assert "by_model" in preview
        assert "by_alias" in preview

    @pytest.mark.asyncio
    async def test_get_uncertified_logs(self, test_app, test_api_key):
        """Test fetching uncertified logs."""
        # Log a conversation (without generating receipt)
        await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "Uncertified"}],
                "response": {
                    "content": "Response",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "alias": "uncert",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "input_cost": 0.001,
                    "output_cost": 0.0005,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        # Fetch uncertified logs
        uncert_response = await test_app.get(
            "/api/v1/receipts/uncertified",
            headers={"X-API-Key": test_api_key},
        )

        assert uncert_response.status_code == 200
        data = uncert_response.json()

        assert "logs" in data
        assert "total" in data
        assert data["total"] >= 1  # At least the one we just logged
        assert len(data["logs"]) >= 1

    @pytest.mark.asyncio
    async def test_since_last_receipt(self, test_app, test_api_key):
        """Test generating receipt for logs since last receipt."""
        # Log first conversation and generate receipt
        log1 = await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "First"}],
                "response": {
                    "content": "First response",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "input_cost": 0.001,
                    "output_cost": 0.0005,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        conv1_id = log1.json()["conversation_id"]

        # Generate first receipt
        await test_app.post(
            "/api/v1/receipts/generate",
            json={"conversation_id": conv1_id},
            headers={"X-API-Key": test_api_key},
        )

        # Log second conversation (not certified)
        await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "Second"}],
                "response": {
                    "content": "Second response",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "input_cost": 0.002,
                    "output_cost": 0.001,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        # Generate receipt for logs since last receipt
        since_receipt = await test_app.post(
            "/api/v1/receipts/generate",
            json={"since_last_receipt": True},
            headers={"X-API-Key": test_api_key},
        )

        assert since_receipt.status_code == 200
        data = since_receipt.json()

        # Should only certify the second conversation
        assert data["certified_count"] >= 1

    @pytest.mark.asyncio
    async def test_get_receipt_logs(self, test_app, test_api_key):
        """Test fetching logs certified by a receipt."""
        # Log and generate receipt
        log_response = await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": "Test"}],
                "response": {
                    "content": "Response",
                    "model": "gpt-4o",
                    "finish_reason": "stop",
                },
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "input_cost": 0.001,
                    "output_cost": 0.0005,
                },
            },
            headers={"X-API-Key": test_api_key},
        )

        conversation_id = log_response.json()["conversation_id"]

        receipt_response = await test_app.post(
            "/api/v1/receipts/generate",
            json={"conversation_id": conversation_id},
            headers={"X-API-Key": test_api_key},
        )

        receipt_id = receipt_response.json()["receipt"]["receipt_id"]

        # Get logs for this receipt
        logs_response = await test_app.get(
            f"/api/v1/receipts/{receipt_id}/logs",
            headers={"X-API-Key": test_api_key},
        )

        assert logs_response.status_code == 200
        data = logs_response.json()

        assert "logs" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["receipt_id"] == receipt_id


@pytest.fixture
async def test_api_key():
    """Provide a test API key."""
    return "test_key_" + uuid4().hex[:16]
