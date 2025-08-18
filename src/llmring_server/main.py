from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import logging

from .config import Settings
from .database import Database


logger = logging.getLogger(__name__)
settings = Settings()

# Database instance
db = Database(settings.database_url, schema=settings.database_schema)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting LLMRing Server...")
    await db.connect()
    await db.run_migrations()
    app.state.db = db.db
    try:
        yield
    finally:
        logger.info("Shutting down...")
        await db.disconnect()


app = FastAPI(
    title="LLMRing Server",
    description="Self-hostable LLM model registry and usage tracking",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for self-hosting
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Simple project-based auth
async def get_project_id(x_project_key: Optional[str] = Header(None)) -> str:
    """Simple project identification."""
    if not x_project_key:
        raise HTTPException(401, "X-Project-Key header required")
    return x_project_key


# Dependency to inject database
async def get_db():
    if not db.db:
        raise HTTPException(500, "Database not initialized")
    return db.db


# Routers will be imported after app and deps to avoid circulars
from .routers import registry, usage, receipts, aliases  # noqa: E402


# Public endpoints (no auth)
app.include_router(registry.router)

# Project-scoped endpoints
app.include_router(usage.router, dependencies=[Depends(get_project_id)])
app.include_router(aliases.router, dependencies=[Depends(get_project_id)])
app.include_router(receipts.router, dependencies=[Depends(get_project_id)])


@app.get("/")
async def root():
    return {"name": "LLMRing Server", "version": "0.1.0", "docs": "/docs", "registry": "/registry"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        await db.db.fetch_one("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected"}


