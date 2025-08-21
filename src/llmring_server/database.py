import logging
from pathlib import Path
from typing import Optional

from pgdbm import AsyncDatabaseManager, DatabaseConfig
from pgdbm.migrations import AsyncMigrationManager

logger = logging.getLogger(__name__)


class Database:
    """Database manager supporting dual-mode operation.
    
    Can work standalone (creates own connection) or integrated
    (uses external connection pool).
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        db_manager: Optional[AsyncDatabaseManager] = None,
        schema: str = "llmring",
        min_connections: int | None = None,
        max_connections: int | None = None,
    ):
        """Initialize database in standalone or library mode.
        
        Args:
            connection_string: Connection string for standalone mode
            db_manager: External database manager for library mode
            schema: Schema name (defaults to 'llmring')
            min_connections: Min pool connections (standalone mode only)
            max_connections: Max pool connections (standalone mode only)
        """
        if not connection_string and not db_manager:
            raise ValueError("Either connection_string or db_manager required")
        
        self._external_db = db_manager is not None
        self.db = db_manager
        self._connection_string = connection_string
        self.schema = schema
        self._min_connections = min_connections or 10
        self._max_connections = max_connections or 20
        self.migrations_path = Path(__file__).parent / "migrations"

    async def connect(self):
        """Initialize database connection (standalone mode only)."""
        if not self._external_db:
            config = DatabaseConfig(
                connection_string=self._connection_string,
                schema=self.schema,
                min_connections=self._min_connections,
                max_connections=self._max_connections,
            )
            self.db = AsyncDatabaseManager(config)
            await self.db.connect()
            logger.info("Database connected (standalone mode)")
        else:
            logger.info("Using external database (library mode)")

    async def disconnect(self):
        """Close database connection (standalone mode only)."""
        if not self._external_db and self.db:
            await self.db.disconnect()
            logger.info("Database disconnected")

    async def run_migrations(self):
        """Apply pending migrations using pgdbm."""
        if not self.db:
            raise RuntimeError("Database not connected")

        migrations = AsyncMigrationManager(
            self.db,
            migrations_path=str(self.migrations_path),
            module_name=f"llmring_server_{self.schema}",
            schema=self.schema
        )
        result = await migrations.apply_pending_migrations()

        if result.get("applied"):
            logger.info(f"Applied {len(result['applied'])} migrations for schema {self.schema}")

        return result
