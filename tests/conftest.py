import getpass
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pgdbm import AsyncMigrationManager

# Register external fixtures from pgdbm
pytest_plugins = ("pgdbm.fixtures.conftest",)

# Ensure pgdbm test defaults are sane for local dev
os.environ.setdefault("TEST_DB_HOST", "localhost")
os.environ.setdefault("TEST_DB_PORT", "5432")
os.environ.setdefault("TEST_DB_USER", getpass.getuser())
# Provide blank passwords so DSN can be constructed for local trust setups
os.environ.setdefault("TEST_DB_PASSWORD", "postgres")
os.environ.setdefault("DB_PASSWORD", "postgres")


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
    """Create test app with test database."""
    from llmring_server.config import Settings, ensure_receipt_keys
    from llmring_server.main import create_app

    # Ensure receipt signing keys are available for tests
    settings = Settings()
    settings = ensure_receipt_keys(settings)

    # Store keys in environment for the app
    os.environ["LLMRING_RECEIPTS_PRIVATE_KEY_B64"] = settings.receipts_private_key_base64
    os.environ["LLMRING_RECEIPTS_PUBLIC_KEY_B64"] = settings.receipts_public_key_base64

    # Create app in library mode with test database
    app = create_app(
        db_manager=llmring_db,
        schema="llmring_test",
        run_migrations=False,  # Already applied above
        standalone=False,  # Library mode for testing
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up
    os.environ.pop("LLMRING_RECEIPTS_PRIVATE_KEY_B64", None)
    os.environ.pop("LLMRING_RECEIPTS_PUBLIC_KEY_B64", None)
