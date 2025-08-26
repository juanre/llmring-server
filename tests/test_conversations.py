"""Tests for conversation and message management."""

import pytest
from uuid import uuid4

from llmring_server.models.conversations import (
    ConversationCreate,
    ConversationUpdate,
    MessageBatch,
    MessageCreate,
)
from llmring_server.services.conversations import ConversationService


@pytest.mark.asyncio
async def test_create_conversation(test_app):
    """Test creating a new conversation."""
    response = await test_app.post(
        "/conversations/",
        json={
            "title": "Test Conversation",
            "system_prompt": "You are a helpful assistant",
            "model_alias": "default",
            "temperature": 0.7,
            "max_tokens": 1000,
        },
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Conversation"
    assert data["system_prompt"] == "You are a helpful assistant"
    # api_key_id is optional and can be None for local usage
    assert "api_key_id" in data
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_conversation(test_app):
    """Test retrieving a conversation."""
    # First create a conversation
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Test Get Conversation",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "test-project"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Get the conversation
    response = await test_app.get(
        f"/conversations/{conversation_id}",
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == conversation_id
    assert data["title"] == "Test Get Conversation"
    assert "messages" in data  # Should include messages by default


@pytest.mark.asyncio
async def test_get_conversation_without_messages(test_app):
    """Test retrieving a conversation without messages."""
    # First create a conversation
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Test Without Messages",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "test-project"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Get the conversation without messages
    response = await test_app.get(
        f"/conversations/{conversation_id}?include_messages=false",
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == conversation_id
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_get_conversation_not_found(test_app):
    """Test getting a non-existent conversation."""
    fake_id = str(uuid4())
    response = await test_app.get(
        f"/conversations/{fake_id}",
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_conversation_wrong_api_key(test_app):
    """Test that conversations are isolated by API key."""
    # Create conversation with one API key
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Isolated Conversation",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "project-1"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Try to get it with a different API key
    response = await test_app.get(
        f"/conversations/{conversation_id}",
        headers={"X-Project-Key": "project-2"},
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_conversation(test_app):
    """Test updating a conversation."""
    # Create conversation
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Original Title",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "test-project"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Update it
    response = await test_app.patch(
        f"/conversations/{conversation_id}",
        json={
            "title": "Updated Title",
            "temperature": 0.5,
        },
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["temperature"] == 0.5


@pytest.mark.asyncio
async def test_list_conversations(test_app):
    """Test listing conversations."""
    # Create multiple conversations
    for i in range(3):
        await test_app.post(
            "/conversations/",
            json={
                "title": f"Conversation {i}",
                "model_alias": "default",
            },
            headers={"X-Project-Key": "test-list-project"},
        )
    
    # List them
    response = await test_app.get(
        "/conversations/",
        headers={"X-Project-Key": "test-list-project"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    
    # Test pagination
    response = await test_app.get(
        "/conversations/?limit=2",
        headers={"X-Project-Key": "test-list-project"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2


@pytest.mark.asyncio
async def test_add_messages_batch(test_app):
    """Test adding messages to a conversation."""
    # Create conversation
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Message Test",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "test-project"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Add messages
    response = await test_app.post(
        f"/conversations/{conversation_id}/messages/batch",
        json={
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
                {
                    "role": "assistant",
                    "content": "Hi there!",
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
            ],
            "logging_level": "full",
        },
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there!"


@pytest.mark.asyncio
async def test_add_messages_metadata_only(test_app):
    """Test adding messages with metadata logging level."""
    # Create conversation
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Metadata Test",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "test-project"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Add messages with metadata logging
    response = await test_app.post(
        f"/conversations/{conversation_id}/messages/batch",
        json={
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": "This content should be hashed",
                },
            ],
            "logging_level": "metadata",
        },
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 1
    assert messages[0]["content"] is None  # Content should be None
    assert messages[0]["content_hash"] is not None  # But hash should exist


@pytest.mark.asyncio
async def test_get_conversation_messages(test_app):
    """Test getting messages for a conversation."""
    # Create conversation and add messages
    create_response = await test_app.post(
        "/conversations/",
        json={
            "title": "Messages Test",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "test-project"},
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]
    
    # Add some messages
    await test_app.post(
        f"/conversations/{conversation_id}/messages/batch",
        json={
            "conversation_id": conversation_id,
            "messages": [
                {"role": "user", "content": "Message 1"},
                {"role": "assistant", "content": "Reply 1"},
                {"role": "user", "content": "Message 2"},
                {"role": "assistant", "content": "Reply 2"},
            ],
            "logging_level": "full",
        },
        headers={"X-Project-Key": "test-project"},
    )
    
    # Get messages
    response = await test_app.get(
        f"/conversations/{conversation_id}/messages",
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 4
    
    # Test pagination
    response = await test_app.get(
        f"/conversations/{conversation_id}/messages?limit=2&offset=1",
        headers={"X-Project-Key": "test-project"},
    )
    
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["content"] == "Reply 1"


@pytest.mark.asyncio
async def test_conversation_stats_update(llmring_db):
    """Test that conversation stats are updated automatically."""
    from llmring_server.config import Settings
    
    settings = Settings()
    service = ConversationService(llmring_db, settings)
    
    # Create conversation
    conversation_data = ConversationCreate(
        api_key_id="test-key",  # Set consistent api_key_id  
        title="Stats Test",
        model_alias="default",
    )
    conversation = await service.create_conversation(conversation_data)
    assert conversation is not None
    
    # Add messages with token counts
    batch = MessageBatch(
        conversation_id=conversation.id,
        messages=[
            MessageCreate(
                role="user",
                content="Hello",
            ),
            MessageCreate(
                role="assistant",
                content="Hi!",
                input_tokens=10,
                output_tokens=5,
            ),
        ],
        logging_level="full",
    )
    await service.add_messages_batch(batch)
    
    # Get updated conversation
    updated = await service.get_conversation(conversation.id, "test-key")
    assert updated is not None
    assert updated.message_count == 2
    assert updated.total_input_tokens == 10
    assert updated.total_output_tokens == 5


@pytest.mark.asyncio
async def test_conversation_requires_auth(test_app):
    """Test that conversation endpoints require authentication."""
    # Try without header
    response = await test_app.post(
        "/conversations/",
        json={
            "title": "No Auth",
            "model_alias": "default",
        },
    )
    assert response.status_code == 401
    
    # Try with empty header
    response = await test_app.post(
        "/conversations/",
        json={
            "title": "Empty Auth",
            "model_alias": "default",
        },
        headers={"X-Project-Key": ""},
    )
    assert response.status_code == 401
    
    # Try with whitespace in key
    response = await test_app.post(
        "/conversations/",
        json={
            "title": "Bad Auth",
            "model_alias": "default",
        },
        headers={"X-Project-Key": "has spaces"},
    )
    assert response.status_code == 400