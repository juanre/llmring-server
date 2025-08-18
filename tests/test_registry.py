import pytest


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
async def test_get_registry(test_app, llmring_db):
    # Insert a sample model
    await llmring_db.execute(
        """
        INSERT INTO {{tables.llm_models}} (
            model_name, provider, display_name, description,
            max_context, max_output_tokens,
            dollars_per_million_tokens_input, dollars_per_million_tokens_output,
            supports_vision, supports_function_calling,
            supports_json_mode, supports_parallel_tool_calls
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
        "gpt-4o-mini",
        "openai",
        "GPT-4o Mini",
        "desc",
        128000,
        16384,
        0.15,
        0.60,
        True,
        True,
        True,
        True,
    )

    r = await test_app.get("/registry.json")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "models" in data
    assert "gpt-4o-mini" in data["models"]

