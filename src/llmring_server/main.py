import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import Settings
from .database import Database

logger = logging.getLogger(__name__)
settings = Settings()

# Database instance
db = Database(
    settings.database_url,
    schema=settings.database_schema,
    min_connections=settings.database_pool_size,
    max_connections=settings.database_pool_size + settings.database_pool_overflow,
)


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


# Keep only app setup here; enforce the project header via a shared dependency


# Dependency to inject database
async def get_db():
    if not db.db:
        raise HTTPException(500, "Database not initialized")
    return db.db


# Routers will be imported after app and deps to avoid circulars
from .routers import aliases, receipts, registry, usage  # noqa: E402

app.include_router(registry.router)

app.include_router(usage.router)
app.include_router(aliases.router)
app.include_router(receipts.router)


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
        await db.db.fetch_one("SELECT 1")
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
