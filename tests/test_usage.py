# ABOUTME: Tests for usage logging and statistics endpoints.
# ABOUTME: Covers usage log creation, retrieval with filtering, and aggregated stats.

import pytest

PROJECT_HEADERS = {"X-API-Key": "proj_test"}


@pytest.mark.asyncio
async def test_log_and_stats(test_app, llmring_db):
    # Ensure a model for cost calculation path
    # Use live registry pricing

    # Log
    r = await test_app.post(
        "/api/v1/log",
        json={
            "model": "gpt-4o-mini",
            "provider": "openai",
            "input_tokens": 1000,
            "output_tokens": 200,
            "cached_input_tokens": 0,
            "alias": "summarizer",
        },
        headers=PROJECT_HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert "log_id" in data

    # Stats
    r = await test_app.get("/api/v1/stats", headers=PROJECT_HEADERS)
    assert r.status_code == 200
    stats = r.json()
    assert "summary" in stats
    # Optional: verify by_alias is present
    assert "by_alias" in stats
    assert isinstance(stats["by_alias"], dict)


@pytest.mark.asyncio
async def test_usage_logs_endpoint(test_app, llmring_db):
    payload = {
        "model": "gpt-4o-mini",
        "provider": "openai",
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_input_tokens": 0,
        "alias": "fast",
        "origin": "tests",
    }

    r = await test_app.post("/api/v1/log", json=payload, headers=PROJECT_HEADERS)
    assert r.status_code == 200

    r = await test_app.get("/api/v1/logs", headers=PROJECT_HEADERS)
    assert r.status_code == 200
    logs = r.json()
    assert isinstance(logs, list)
    assert logs
    row = logs[0]
    assert row["model"] == "gpt-4o-mini"
    assert row["alias"] == "fast"
