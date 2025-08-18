import pytest


PROJECT_HEADERS = {"X-Project-Key": "proj_test"}


@pytest.mark.asyncio
async def test_log_and_stats(test_app, llmring_db):
    # Ensure a model for cost calculation path
    await llmring_db.execute(
        """
        INSERT INTO {{tables.llm_models}} (
            model_name, provider, display_name, description,
            max_context, max_output_tokens,
            dollars_per_million_tokens_input, dollars_per_million_tokens_output
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        "gpt-4o-mini",
        "openai",
        "GPT-4o Mini",
        "desc",
        128000,
        16384,
        0.15,
        0.60,
    )

    # Log
    r = await test_app.post(
        "/api/v1/log",
        json={
            "model": "gpt-4o-mini",
            "provider": "openai",
            "input_tokens": 1000,
            "output_tokens": 200,
            "cached_input_tokens": 0,
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

