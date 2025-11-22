"""Tests for API key authentication and registry v3.5 schema parsing. Ensures stateful routes require authentication and registry handles new schema."""

import pytest


@pytest.mark.asyncio
async def test_stateful_routes_require_project_key(test_app):
    # Usage log should 401 without header
    r = await test_app.post(
        "/api/v1/log",
        json={
            "model": "gpt-4o-mini",
            "provider": "openai",
            "input_tokens": 100,
            "output_tokens": 10,
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_registry_parsing_v35_schema(monkeypatch, test_app):
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict | None = None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, *args, **kwargs):
            if url.endswith("/manifest.json"):
                return FakeResponse(200, {"version": 2})
            if url.endswith("/openai/models.json"):
                return FakeResponse(
                    200,
                    {
                        "provider": "openai",
                        "version": 2,
                        "updated_at": "2025-08-20T00:00:00Z",
                        "models": {
                            "openai:gpt-5": {
                                "provider": "openai",
                                "model_name": "gpt-5",
                                "display_name": "GPT-5",
                                "max_input_tokens": 200000,
                                "max_output_tokens": 16384,
                                "dollars_per_million_tokens_input": 1.25,
                                "dollars_per_million_tokens_output": 10.0,
                                "supports_vision": True,
                                "supports_function_calling": True,
                                "supports_json_mode": True,
                                "supports_parallel_tool_calls": True,
                                "is_active": True,
                            }
                        },
                    },
                )
            # Other providers: pretend unavailable
            return FakeResponse(404, {})

    # Patch only the service module's httpx client, not the test client
    monkeypatch.setattr("httpx.AsyncClient", FakeClient, raising=True)

    r = await test_app.get("/registry.json")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "2"
    assert "models" in data and isinstance(data["models"], dict)
    model = data["models"]["openai:gpt-5"]
    # v3.5 field names should be present
    assert model["max_input_tokens"] == 200000
    assert model["max_output_tokens"] == 16384
    assert model["dollars_per_million_tokens_input"] == 1.25
    assert model["dollars_per_million_tokens_output"] == 10.0
    assert model["supports_json_mode"] is True
    assert model["is_active"] is True
