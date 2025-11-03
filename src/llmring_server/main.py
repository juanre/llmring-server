import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pgdbm import AsyncDatabaseManager, DatabaseConfig
from pgdbm.migrations import AsyncMigrationManager

from .config import Settings

logger = logging.getLogger(__name__)


def create_app(
    db_manager: Optional[AsyncDatabaseManager] = None,
    run_migrations: bool = True,
    schema: Optional[str] = None,
    settings: Optional[Settings] = None,
    standalone: bool = True,
    include_meta_routes: bool = True,
) -> FastAPI:
    """Create llmring-server app supporting both standalone and library modes.

    Args:
        db_manager: External database (library mode) or None (standalone)
        run_migrations: Whether to apply migrations on startup
        schema: Override schema name
        settings: Override settings
        standalone: If True, include lifespan management. If False, assume external management.
        include_meta_routes: If True, include root and health endpoints. Set to False when mounting as sub-app.

    Returns:
        Configured FastAPI application
    """

    # Load settings if not provided
    if settings is None:
        settings = Settings()

    # Use provided schema or default from settings
    schema = schema or settings.database_schema

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifecycle."""
        mode = "library" if db_manager else "standalone"
        logger.info(f"Starting LLMRing Server in {mode} mode...")

        # In standalone mode, create and connect database
        if not db_manager:
            config = DatabaseConfig(
                connection_string=settings.database_url,
                schema=schema,
                min_connections=settings.database_pool_size,
                max_connections=settings.database_pool_size + settings.database_pool_overflow,
            )
            app.state.db = AsyncDatabaseManager(config)
            await app.state.db.connect()
            logger.info("Database connected (standalone mode)")
        else:
            # Library mode: use provided database
            app.state.db = db_manager
            logger.info("Using external database (library mode)")

        # Run migrations if requested
        if run_migrations:
            migrations_path = Path(__file__).parent / "migrations"
            if migrations_path.exists():
                migrations = AsyncMigrationManager(
                    app.state.db,
                    migrations_path=str(migrations_path),
                    module_name="llmring_server",
                )
                result = await migrations.apply_pending_migrations()
                if result.get("applied"):
                    logger.info(f"Applied migrations: {result['applied']}")
                else:
                    logger.info("No pending migrations")

        # Store settings in app state
        app.state.settings = settings
        app.state.external_db = db_manager is not None

        logger.info("LLMRing Server started successfully")

        try:
            yield
        finally:
            # Disconnect if in standalone mode
            if not db_manager and hasattr(app.state, "db"):
                await app.state.db.disconnect()
                logger.info("Database disconnected")
            logger.info("LLMRing Server shut down")

    # Create app
    if standalone:
        app = FastAPI(
            title="LLMRing Server",
            description="Self-hostable LLM model registry and usage tracking",
            version="0.1.1",
            lifespan=lifespan,
        )
    else:
        # Library mode: no lifespan management
        app = FastAPI(
            title="LLMRing Server",
            description="Self-hostable LLM model registry and usage tracking",
            version="0.1.1",
        )

    # Store settings immediately for reference (lifespan will update if needed)
    app.state.settings = settings

    # CORS for self-hosting (restrict in production; '*' is acceptable for local dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type", "If-None-Match"],
    )

    # In library mode, set db immediately since there's no lifespan
    if not standalone:
        if not db_manager:
            raise ValueError("db_manager required when standalone=False")
        app.state.db = db_manager
        app.state.external_db = True
        app.state.settings = settings

        # Run migrations if requested (in library mode)
        if run_migrations:
            import asyncio

            migrations_path = Path(__file__).parent / "migrations"
            if migrations_path.exists():
                migrations = AsyncMigrationManager(
                    db_manager,
                    migrations_path=str(migrations_path),
                    module_name="llmring_server",
                )
                # Create a task to run migrations asynchronously
                asyncio.create_task(migrations.apply_pending_migrations())

    # Import routers
    from .routers import registry  # noqa: E402
    from .routers import conversations, mcp, templates, usage

    # Include routers
    app.include_router(registry.router)
    app.include_router(usage.router)
    app.include_router(conversations.router)
    app.include_router(mcp.router)
    app.include_router(templates.router)

    # Add meta endpoints only if requested (not when used as sub-app)
    if include_meta_routes:

        @app.get("/")
        async def root():
            return {
                "name": "LLMRing Server",
                "version": "0.1.1",
                "docs": "/docs",
                "registry": "/registry",
            }

        @app.get("/health")
        async def health():
            """Health check endpoint."""
            try:
                await app.state.db.fetch_one("SELECT 1")
                return {"status": "healthy", "database": "connected"}
            except (
                asyncpg.PostgresError,
                asyncpg.InterfaceError,
                ConnectionError,
            ) as e:
                logger.error(f"Health check failed: {e}")
                return {"status": "unhealthy", "database": "disconnected"}

    return app


# Create default app instance for uvicorn
app = create_app()


def main():
    """Run the server in standalone mode."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
