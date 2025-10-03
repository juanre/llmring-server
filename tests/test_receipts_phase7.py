"""Tests for Phase 7: Server-Side Receipt Generation and Signing."""

from pathlib import Path
from uuid import UUID

import pytest

from llmring_server.config import Settings, ensure_receipt_keys, load_or_generate_keypair
from llmring_server.models.receipts import Receipt, UnsignedReceipt
from llmring_server.services.receipts import ReceiptsService


@pytest.mark.asyncio
async def test_generate_keypair():
    """Test Ed25519 keypair generation."""
    private_b64, public_b64 = load_or_generate_keypair()

    # Keys should be base64url encoded strings
    assert isinstance(private_b64, str)
    assert isinstance(public_b64, str)
    assert len(private_b64) > 0
    assert len(public_b64) > 0

    # Should not have padding
    assert "=" not in private_b64.rstrip("=")
    assert "=" not in public_b64.rstrip("=")


@pytest.mark.asyncio
async def test_generate_and_sign_receipt(llmring_db):
    """Test generating and signing a receipt."""
    # Setup keys
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    service = ReceiptsService(llmring_db, settings)

    # Generate receipt
    receipt = await service.generate_and_sign_receipt(
        api_key_id="test-key-123",
        alias="summarizer",
        profile="production",
        lock_digest="abc123",
        provider="openai",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        input_cost=0.001,
        output_cost=0.002,
    )

    # Verify receipt structure
    assert isinstance(receipt, Receipt)
    assert receipt.receipt_id.startswith("rcpt_")
    assert receipt.alias == "summarizer"
    assert receipt.profile == "production"
    assert receipt.provider == "openai"
    assert receipt.model == "gpt-4"
    assert receipt.prompt_tokens == 100
    assert receipt.completion_tokens == 50
    assert receipt.total_tokens == 150
    assert receipt.input_cost == 0.001
    assert receipt.output_cost == 0.002
    assert receipt.total_cost == 0.003

    # Verify signature
    assert receipt.signature is not None
    assert receipt.signature.startswith("ed25519:")


@pytest.mark.asyncio
async def test_verify_receipt_signature(llmring_db):
    """Test verifying a receipt's signature."""
    # Setup keys
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    service = ReceiptsService(llmring_db, settings)

    # Generate receipt
    receipt = await service.generate_and_sign_receipt(
        api_key_id="test-key-456",
        alias="chatbot",
        profile="default",
        lock_digest="",
        provider="anthropic",
        model="claude-3-opus",
        prompt_tokens=200,
        completion_tokens=100,
        input_cost=0.002,
        output_cost=0.004,
    )

    # Verify signature
    is_valid = service._verify_signature(receipt)
    assert is_valid is True


@pytest.mark.asyncio
async def test_verify_tampered_receipt(llmring_db):
    """Test that signature verification fails for tampered receipts."""
    # Setup keys
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    service = ReceiptsService(llmring_db, settings)

    # Generate receipt
    receipt = await service.generate_and_sign_receipt(
        api_key_id="test-key-789",
        alias="translator",
        profile="default",
        lock_digest="",
        provider="google",
        model="gemini-pro",
        prompt_tokens=300,
        completion_tokens=150,
        input_cost=0.003,
        output_cost=0.006,
    )

    # Tamper with receipt
    receipt.total_cost = 999.99

    # Verification should fail
    is_valid = service._verify_signature(receipt)
    assert is_valid is False


@pytest.mark.asyncio
async def test_store_and_retrieve_receipt(llmring_db):
    """Test storing and retrieving a receipt from the database."""
    # Setup keys
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    service = ReceiptsService(llmring_db, settings)
    api_key_id = "test-key-store"

    # Generate receipt (this also stores it)
    original_receipt = await service.generate_and_sign_receipt(
        api_key_id=api_key_id,
        alias="coder",
        profile="default",
        lock_digest="def456",
        provider="openai",
        model="gpt-4-turbo",
        prompt_tokens=400,
        completion_tokens=200,
        input_cost=0.004,
        output_cost=0.008,
    )

    # Retrieve receipt
    retrieved_receipt = await service.get_receipt(original_receipt.receipt_id, api_key_id)

    assert retrieved_receipt is not None
    assert retrieved_receipt.receipt_id == original_receipt.receipt_id
    assert retrieved_receipt.alias == original_receipt.alias
    assert retrieved_receipt.provider == original_receipt.provider
    assert retrieved_receipt.model == original_receipt.model
    assert retrieved_receipt.prompt_tokens == original_receipt.prompt_tokens
    assert retrieved_receipt.completion_tokens == original_receipt.completion_tokens
    assert retrieved_receipt.signature == original_receipt.signature


@pytest.mark.asyncio
async def test_list_receipts(llmring_db):
    """Test listing receipts with pagination."""
    # Setup keys
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    service = ReceiptsService(llmring_db, settings)
    api_key_id = "test-key-list"

    # Generate multiple receipts
    for i in range(5):
        await service.generate_and_sign_receipt(
            api_key_id=api_key_id,
            alias=f"alias_{i}",
            profile="default",
            lock_digest="",
            provider="openai",
            model="gpt-4",
            prompt_tokens=100 * i,
            completion_tokens=50 * i,
            input_cost=0.001 * i,
            output_cost=0.002 * i,
        )

    # List all receipts
    receipts, total = await service.list_receipts(api_key_id, limit=10, offset=0)

    assert total == 5
    assert len(receipts) == 5

    # Test pagination
    receipts_page1, total = await service.list_receipts(api_key_id, limit=2, offset=0)
    assert len(receipts_page1) == 2
    assert total == 5

    receipts_page2, total = await service.list_receipts(api_key_id, limit=2, offset=2)
    assert len(receipts_page2) == 2


@pytest.mark.asyncio
async def test_receipt_isolation_by_api_key(llmring_db):
    """Test that receipts are properly isolated by API key."""
    # Setup keys
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    service = ReceiptsService(llmring_db, settings)

    # Create receipts for different API keys
    receipt1 = await service.generate_and_sign_receipt(
        api_key_id="key-1",
        alias="test",
        profile="default",
        lock_digest="",
        provider="openai",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        input_cost=0.001,
        output_cost=0.002,
    )

    receipt2 = await service.generate_and_sign_receipt(
        api_key_id="key-2",
        alias="test",
        profile="default",
        lock_digest="",
        provider="openai",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        input_cost=0.001,
        output_cost=0.002,
    )

    # key-1 should only see receipt1
    retrieved = await service.get_receipt(receipt1.receipt_id, "key-1")
    assert retrieved is not None

    # key-1 should NOT see receipt2
    retrieved = await service.get_receipt(receipt2.receipt_id, "key-1")
    assert retrieved is None

    # key-2 should only see receipt2
    retrieved = await service.get_receipt(receipt2.receipt_id, "key-2")
    assert retrieved is not None


@pytest.mark.asyncio
async def test_conversation_logging_with_receipt(test_app):
    """Test that conversation logging generates receipts."""
    # Keys are set up by the session-scoped fixture in conftest.py
    # Log a conversation
    response = await test_app.post(
        "/api/v1/conversations/log",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "response": {
                "content": "Hi there!",
                "model": "gpt-4",
                "finish_reason": "stop",
            },
            "metadata": {
                "provider": "openai",
                "model": "gpt-4",
                "alias": "chatbot",
                "profile": "default",
                "input_tokens": 10,
                "output_tokens": 5,
                "input_cost": 0.0001,
                "output_cost": 0.0002,
            },
        },
        headers={"X-API-Key": "test-project"},
    )

    assert response.status_code == 200
    data = response.json()

    # Should have conversation_id and message_id
    assert "conversation_id" in data
    assert "message_id" in data

    # Phase 7.5: Receipt should be None (no automatic generation)
    assert data.get("receipt") is None

    # Generate receipt on-demand (must use same API key as conversation logging)
    conversation_id = data["conversation_id"]
    receipt_response = await test_app.post(
        "/api/v1/receipts/generate",
        json={"conversation_id": conversation_id},
        headers={"X-API-Key": "test-project"},
    )

    if receipt_response.status_code != 200:
        print(f"Error generating receipt: {receipt_response.status_code} - {receipt_response.text}")
    assert receipt_response.status_code == 200
    receipt_data = receipt_response.json()
    receipt = receipt_data["receipt"]

    assert receipt["receipt_id"].startswith("rcpt_")
    assert receipt["alias"] == "chatbot"
    assert receipt["provider"] == "openai"
    assert receipt["model"] == "gpt-4"
    assert receipt["prompt_tokens"] == 10
    assert receipt["completion_tokens"] == 5
    assert receipt["signature"] is not None
    assert receipt["signature"].startswith("ed25519:")


@pytest.mark.asyncio
async def test_list_receipts_endpoint(test_app):
    """Test the GET /api/v1/receipts endpoint."""
    import os

    from llmring_server.config import load_or_generate_keypair

    private_b64, public_b64 = load_or_generate_keypair()
    os.environ["LLMRING_RECEIPTS_PRIVATE_KEY_B64"] = private_b64
    os.environ["LLMRING_RECEIPTS_PUBLIC_KEY_B64"] = public_b64

    # Create some receipts by logging conversations and generating receipts on-demand
    for i in range(3):
        log_response = await test_app.post(
            "/api/v1/conversations/log",
            json={
                "messages": [{"role": "user", "content": f"Test {i}"}],
                "response": {"content": f"Response {i}", "model": "gpt-4"},
                "metadata": {
                    "provider": "openai",
                    "model": "gpt-4",
                    "alias": f"alias_{i}",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "input_cost": 0.0001,
                    "output_cost": 0.0002,
                },
            },
            headers={"X-API-Key": "test-list-receipts"},
        )

        # Generate receipt on-demand (Phase 7.5)
        conversation_id = log_response.json()["conversation_id"]
        await test_app.post(
            "/api/v1/receipts/generate",
            json={"conversation_id": conversation_id},
            headers={"X-API-Key": "test-list-receipts"},
        )

    # List receipts
    response = await test_app.get(
        "/api/v1/receipts/?limit=10&offset=0",
        headers={"X-API-Key": "test-list-receipts"},
    )

    assert response.status_code == 200
    data = response.json()

    assert "receipts" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data

    assert data["total"] == 3
    assert len(data["receipts"]) == 3


@pytest.mark.asyncio
async def test_get_public_key_endpoints(test_app):
    """Test public key retrieval endpoints."""
    import os

    from llmring_server.config import load_or_generate_keypair

    private_b64, public_b64 = load_or_generate_keypair()
    os.environ["LLMRING_RECEIPTS_PRIVATE_KEY_B64"] = private_b64
    os.environ["LLMRING_RECEIPTS_PUBLIC_KEY_B64"] = public_b64

    # Test PEM endpoint
    response = await test_app.get("/api/v1/receipts/public-key.pem")
    assert response.status_code == 200
    pem_content = response.text
    assert "-----BEGIN PUBLIC KEY-----" in pem_content
    assert "-----END PUBLIC KEY-----" in pem_content

    # Test JSON endpoint
    response = await test_app.get("/api/v1/receipts/public-keys.json")
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert "current_key_id" in data
    assert len(data["keys"]) >= 1
    assert data["keys"][0]["algorithm"] == "Ed25519"
    assert data["keys"][0]["format"] == "base64url"


@pytest.mark.asyncio
async def test_verify_receipt_endpoint(test_app):
    """Test the POST /api/v1/receipts/verify endpoint."""
    # Keys are set up by the session-scoped fixture in conftest.py
    # Log a conversation to get a receipt (Phase 7.5: on-demand)
    log_response = await test_app.post(
        "/api/v1/conversations/log",
        json={
            "messages": [{"role": "user", "content": "Verify me"}],
            "response": {"content": "Verified!", "model": "gpt-4"},
            "metadata": {
                "provider": "openai",
                "model": "gpt-4",
                "alias": "verifier",
                "input_tokens": 10,
                "output_tokens": 5,
                "input_cost": 0.0001,
                "output_cost": 0.0002,
            },
        },
        headers={"X-API-Key": "test-verify"},
    )

    assert log_response.status_code == 200
    conversation_id = log_response.json()["conversation_id"]

    # Generate receipt on-demand
    receipt_response = await test_app.post(
        "/api/v1/receipts/generate",
        json={"conversation_id": conversation_id},
        headers={"X-API-Key": "test-verify"},
    )

    if receipt_response.status_code != 200:
        print(f"Error: {receipt_response.status_code} - {receipt_response.text}")
    assert receipt_response.status_code == 200
    receipt = receipt_response.json()["receipt"]

    # Verify the receipt
    verify_response = await test_app.post(
        "/api/v1/receipts/verify",
        json=receipt,
    )

    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    assert verify_data["valid"] is True
    assert verify_data["receipt_id"] == receipt["receipt_id"]
    assert verify_data["algorithm"] == "Ed25519"

    # Tamper with receipt and verify it fails
    receipt["total_cost"] = 999.99
    verify_response = await test_app.post(
        "/api/v1/receipts/verify",
        json=receipt,
    )

    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    assert verify_data["valid"] is False
