import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pgdbm import AsyncDatabaseManager

from .config import Settings
from .database import Database

logger = logging.getLogger(__name__)


def create_app(
    db_manager: Optional[AsyncDatabaseManager] = None,
    run_migrations: bool = True,
    schema: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> FastAPI:
    """Create llmring-server app supporting both standalone and library modes.
    
    Args:
        db_manager: External database (library mode) or None (standalone)
        run_migrations: Whether to apply migrations on startup
        schema: Override schema name
        settings: Override settings
    
    Returns:
        Configured FastAPI application
    """
    
    # Load settings if not provided
    if settings is None:
        settings = Settings()
    
    # Determine database mode
    if db_manager:
        # Library mode: use provided database
        database = Database(
            db_manager=db_manager,
            schema=schema or settings.database_schema,
        )
    else:
        # Standalone mode: create own connection
        database = Database(
            connection_string=settings.database_url,
            schema=schema or settings.database_schema,
            min_connections=settings.database_pool_size,
            max_connections=settings.database_pool_size + settings.database_pool_overflow,
        )
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifecycle."""
        mode = "library" if db_manager else "standalone"
        logger.info(f"Starting LLMRing Server in {mode} mode...")
        
        # Connect database (only needed in standalone mode)
        await database.connect()
        
        # Run migrations if requested
        if run_migrations:
            await database.run_migrations()
        
        # Store database and mode in app state
        app.state.db = database.db
        app.state.database = database
        app.state.external_db = db_manager is not None
        app.state.settings = settings
        
        try:
            yield
        finally:
            logger.info("Shutting down...")
            await database.disconnect()
    
    # Create app
    app = FastAPI(
        title="LLMRing Server",
        description="Self-hostable LLM model registry and usage tracking",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS for self-hosting (restrict in production; '*' is acceptable for local dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-Project-Key", "Content-Type", "If-None-Match"],
    )
    
    # Keep reference to database for dependency injection
    app.state._database_instance = database
    app.state._settings_instance = settings
    
    # Dependency to inject database
    async def get_db():
        if not app.state.db:
            raise HTTPException(500, "Database not initialized")
        return app.state.db
    
    # Import routers
    from .routers import aliases, receipts, registry, usage  # noqa: E402
    
    # Include routers
    app.include_router(registry.router)
    app.include_router(usage.router)
    app.include_router(aliases.router)
    app.include_router(receipts.router)
    
    # Add root endpoints
    @app.get("/")
    async def root():
        return {
            "name": "LLMRing Server",
            "version": "0.1.0",
            "docs": "/docs",
            "registry": "/registry",
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        try:
            await app.state.db.fetch_one("SELECT 1")
            return {"status": "healthy", "database": "connected"}
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "database": "disconnected"}
    
    @app.get("/receipts/public-key.pem", response_class=PlainTextResponse)
    async def receipts_public_key_pem():
        if not settings.receipts_public_key_base64:
            raise HTTPException(404, "Public key not configured")
        # Render as PEM SubjectPublicKeyInfo
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        
        raw = settings.receipts_public_key_base64
        padding = "=" * ((4 - len(raw) % 4) % 4)
        b = base64.urlsafe_b64decode(raw + padding)
        pub = Ed25519PublicKey.from_public_bytes(b)
        pem = pub.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        return pem.decode()
    
    @app.get("/receipts/public-keys.json", response_class=JSONResponse)
    async def receipts_public_keys_json():
        if not settings.receipts_public_key_base64 or not settings.receipts_key_id:
            raise HTTPException(404, "Public keys not configured")
        return {
            "keys": [
                {
                    "key_id": settings.receipts_key_id,
                    "public_key_pem": (await receipts_public_key_pem()),
                    "created_at": None,
                    "retired_at": None,
                }
            ]
        }
    
    return app


# Default app for standalone mode
app = create_app()

# For backward compatibility - expose db and settings at module level
db = app.state._database_instance
settings = app.state._settings_instance
