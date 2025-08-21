import logging
from pathlib import Path
from typing import Optional

from pgdbm import AsyncDatabaseManager, DatabaseConfig
from pgdbm.migrations import AsyncMigrationManager

logger = logging.getLogger(__name__)


class Database:
    """Database manager using pgdbm."""

    def __init__(
        self,
        connection_string: str,
        schema: str = "llmring",
        min_connections: int | None = None,
        max_connections: int | None = None,
    ):
        self.config = DatabaseConfig(
            connection_string=connection_string,
            schema=schema,
            min_connections=min_connections or 10,
            max_connections=max_connections or 20,
        )
        self.db: Optional[AsyncDatabaseManager] = None
        self.migrations_path = Path(__file__).parent / "migrations"

    async def connect(self):
        """Initialize database connection."""
        self.db = AsyncDatabaseManager(self.config)
        await self.db.connect()
        logger.info("Database connected")

    async def disconnect(self):
        """Close database connection."""
        if self.db:
            await self.db.disconnect()
            logger.info("Database disconnected")

    async def run_migrations(self):
        """Apply pending migrations using pgdbm."""
        if not self.db:
            raise RuntimeError("Database not connected")

        migrations = AsyncMigrationManager(
            self.db,
            migrations_path=str(self.migrations_path),
            module_name="llmring_server",
        )
        result = await migrations.apply_pending_migrations()

        if result.get("applied"):
            logger.info(f"Applied {len(result['applied'])} migrations")

        return result
