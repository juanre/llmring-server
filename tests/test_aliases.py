import pytest

PROJECT_HEADERS = {"X-Project-Key": "proj_test"}


@pytest.mark.asyncio
async def test_bind_list_resolve_delete_alias(test_app):
    # Bind
    r = await test_app.post(
        "/api/v1/aliases/bind",
        json={"alias": "pdf_converter", "model": "openai:gpt-4o-mini"},
        headers=PROJECT_HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["alias"] == "pdf_converter"
    assert data["model"] == "openai:gpt-4o-mini"

    # List
    r = await test_app.get("/api/v1/aliases/", headers=PROJECT_HEADERS)
    assert r.status_code == 200
    lst = r.json()
    assert any(a["alias"] == "pdf_converter" for a in lst)

    # Resolve
    r = await test_app.get(
        "/api/v1/aliases/resolve",
        params={"alias": "pdf_converter"},
        headers=PROJECT_HEADERS,
    )
    assert r.status_code == 200
    res = r.json()
    assert res["alias"] == "pdf_converter"
    assert res["model"] == "openai:gpt-4o-mini"

    # Delete
    r = await test_app.delete("/api/v1/aliases/pdf_converter", headers=PROJECT_HEADERS)
    assert r.status_code == 200
    assert r.json()["deleted"] is True
