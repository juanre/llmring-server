import os
import getpass
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pgdbm import AsyncMigrationManager
from pgdbm.fixtures.conftest import test_db_factory  # noqa: F401

# Ensure pgdbm test defaults are sane for local dev
os.environ.setdefault("TEST_DB_HOST", "localhost")
os.environ.setdefault("TEST_DB_PORT", "5432")
os.environ.setdefault("TEST_DB_USER", getpass.getuser())
# Leave password empty by default; override in environment if required
os.environ.setdefault("TEST_DB_PASSWORD", "")


@pytest_asyncio.fixture
async def llmring_db(test_db_factory):
    """Create llmring-server test DB with isolated schema and apply migrations."""
    db = await test_db_factory.create_db(suffix="llmring", schema="llmring_test")
    migrations = AsyncMigrationManager(
        db, migrations_path="src/llmring_server/migrations", module_name="llmring_test"
    )
    await migrations.apply_pending_migrations()
    return db


@pytest_asyncio.fixture
async def test_app(llmring_db):
    from llmring_server.main import app

    app.state.db = llmring_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


