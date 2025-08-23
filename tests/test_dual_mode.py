"""Test dual-mode operation of llmring-server."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pgdbm import AsyncDatabaseManager
from pgdbm.fixtures.conftest import test_db_factory  # noqa: F401

from llmring_server.config import Settings
from llmring_server.main import create_app


@pytest_asyncio.fixture(params=["standalone", "library"])
async def dual_mode_app(request, test_db_factory):
    """Test fixture that creates llmring-server in both modes."""
    mode = request.param
    
    if mode == "standalone":
        # Create standalone app with its own database
        settings = Settings(
            database_url="postgresql://localhost/test_llmring_standalone",
            database_schema="llmring_test",
        )
        app = create_app(settings=settings)
        
        # Store mode for tests
        app.state.test_mode = "standalone"
        
    else:  # library mode
        # Create external database manager
        external_db = await test_db_factory.create_db(
            suffix="llmring_library",
            schema="llmring_lib"
        )
        
        # Create app with external database
        settings = Settings()  # Use defaults for other settings
        app = create_app(
            db_manager=external_db,
            schema="llmring_lib",
            settings=settings,
            standalone=False,  # Library mode
        )
        
        # Store mode for tests
        app.state.test_mode = "library"
    
    # Create async test client using transport
    from httpx import ASGITransport
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mode


@pytest.mark.asyncio
async def test_dual_mode_health_check(dual_mode_app):
    """Test that health check endpoint exists in both modes."""
    client, mode = dual_mode_app
    
    response = await client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    # Health check returns status even if db not connected
    assert "status" in data
    assert data["status"] in ["healthy", "unhealthy"]
    
    # Both modes should have same response structure
    assert "database" in data


@pytest.mark.asyncio
async def test_dual_mode_root_endpoint(dual_mode_app):
    """Test root endpoint in both modes."""
    client, mode = dual_mode_app
    
    response = await client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "LLMRing Server"
    assert data["version"] == "0.1.0"
    assert data["registry"] == "/registry"


@pytest.mark.asyncio
async def test_dual_mode_registry_endpoint(dual_mode_app):
    """Test registry endpoint in both modes."""
    client, mode = dual_mode_app
    
    # Registry endpoint returns JSON, so use full path
    response = await client.get("/registry.json")
    assert response.status_code in [200, 304]  # 304 if ETag matches
    
    # Both modes should return the same registry structure
    if response.status_code == 200:
        data = response.json()
        assert "version" in data
        assert "models" in data


@pytest.mark.asyncio
async def test_create_app_with_custom_settings(monkeypatch):
    """Test creating app with custom settings."""
    # Use environment variables for Settings
    monkeypatch.setenv("LLMRING_DATABASE_URL", "postgresql://localhost/custom_db")
    monkeypatch.setenv("LLMRING_DATABASE_SCHEMA", "custom_schema")
    
    settings = Settings()
    assert settings.database_schema == "custom_schema"
    
    app = create_app(settings=settings)
    
    # Check that settings were applied
    assert app.state.settings == settings


@pytest.mark.asyncio
async def test_create_app_with_external_db(test_db_factory):
    """Test creating app with external database manager."""
    external_db = await test_db_factory.create_db(
        suffix="external",
        schema="external_schema"
    )
    
    app = create_app(
        db_manager=external_db,
        schema="external_schema",
        run_migrations=False,  # Skip migrations for this test
        standalone=False,
    )
    
    # Check that external db was used (set in non-standalone mode)
    assert app.state.external_db is True
    assert app.state.db == external_db


@pytest.mark.asyncio
@pytest.mark.parametrize("run_migrations", [True, False])
async def test_create_app_migration_control(run_migrations, test_db_factory):
    """Test that migrations can be controlled via parameter."""
    external_db = await test_db_factory.create_db(
        suffix="migration_test",
        schema="test_schema"
    )
    
    app = create_app(
        db_manager=external_db,
        run_migrations=run_migrations,
        standalone=False,
    )
    
    # This test verifies the parameter is accepted
    assert app.state.external_db is True


@pytest.mark.asyncio
async def test_both_modes_share_api_interface(test_db_factory):
    """Test that both modes expose the same API interface."""
    # Create standalone app
    standalone_app = create_app(
        settings=Settings(
            database_url="postgresql://localhost/test_standalone",
            database_schema="standalone"
        )
    )
    
    # Create library mode app
    external_db = await test_db_factory.create_db(
        suffix="library",
        schema="library"
    )
    library_app = create_app(
        db_manager=external_db,
        schema="library",
        standalone=False,
    )
    
    # Both should have the same routes
    standalone_routes = {route.path for route in standalone_app.routes}
    library_routes = {route.path for route in library_app.routes}
    
    assert standalone_routes == library_routes
    
    # Key route patterns should exist in both
    # Some are exact, some are prefixes
    expected_patterns = ["/", "/health", "/registry", "/api/v1/log", "/api/v1/stats"]
    for pattern in expected_patterns:
        found = any(route.startswith(pattern) for route in standalone_routes)
        assert found, f"Pattern {pattern} not found in routes"


@pytest.mark.asyncio
async def test_include_meta_routes_parameter(test_db_factory):
    """Test that include_meta_routes parameter controls root/health endpoints."""
    external_db = await test_db_factory.create_db(
        suffix="meta_routes_test",
        schema="test_schema"
    )
    
    # Create app with meta routes
    app_with_meta = create_app(
        db_manager=external_db,
        standalone=False,
        include_meta_routes=True,
    )
    
    # Create app without meta routes
    app_without_meta = create_app(
        db_manager=external_db,
        standalone=False,
        include_meta_routes=False,
    )
    
    with_meta_routes = {route.path for route in app_with_meta.routes}
    without_meta_routes = {route.path for route in app_without_meta.routes}
    
    # Root and health should be in with_meta but not without_meta
    assert "/" in with_meta_routes
    assert "/health" in with_meta_routes
    assert "/" not in without_meta_routes
    assert "/health" not in without_meta_routes
    
    # Other routes should be the same