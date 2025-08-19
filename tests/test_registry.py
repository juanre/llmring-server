import pytest
from datetime import datetime

from llmring_server.models.registry import RegistryResponse, LLMModel, ProviderInfo


@pytest.mark.asyncio
async def test_root(test_app):
    r = await test_app.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "LLMRing Server"
    assert "version" in data


@pytest.mark.asyncio
async def test_health(test_app):
    r = await test_app.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_get_registry(test_app):
    r = await test_app.get("/registry.json")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "models" in data
    # Expect provider-prefixed keys per v3.2 registry
    assert any(k.startswith("openai:") for k in data["models"].keys())
