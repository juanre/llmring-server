"""High-level service interface for llmring-server.

This module provides a clean interface for using llmring-server as a library.
"""

from typing import Optional
from pathlib import Path

from pgdbm import AsyncDatabaseManager, AsyncMigrationManager

from .services.aliases import AliasesService
from .services.usage import UsageService
from .services.receipts import ReceiptsService
from .services.registry import RegistryService


class LLMRingService:
    """High-level service interface for llmring-server functionality.
    
    This class provides a clean API for using llmring-server as a library,
    encapsulating all service functionality with a single database manager.
    """
    
    def __init__(self, db: AsyncDatabaseManager, run_migrations: bool = False):
        """Initialize the LLMRing service.
        
        Args:
            db: Database manager to use for all operations
            run_migrations: Whether to run migrations on initialization
        """
        self.db = db
        self._run_migrations = run_migrations
        
        # Initialize services
        self.aliases = AliasesService(db)
        self.usage = UsageService(db)
        self.receipts = ReceiptsService(db)
        self.registry = RegistryService()
    
    async def initialize(self) -> None:
        """Initialize the service, optionally running migrations."""
        if self._run_migrations:
            await self.run_migrations()
    
    async def run_migrations(self) -> dict:
        """Run database migrations.
        
        Returns:
            Dictionary with migration results
        """
        migrations_path = Path(__file__).parent / "migrations"
        if not migrations_path.exists():
            return {"error": "Migrations directory not found"}
        
        migration_manager = AsyncMigrationManager(
            self.db,
            migrations_path=str(migrations_path),
            module_name="llmring_server",
        )
        
        result = await migration_manager.apply_pending_migrations()
        return result
    
    async def check_health(self) -> dict:
        """Check service health.
        
        Returns:
            Health status dictionary
        """
        try:
            await self.db.fetch_one("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {e}"
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "database": db_status,
            "services": {
                "aliases": "ready",
                "usage": "ready",
                "receipts": "ready",
                "registry": "ready",
            }
        }