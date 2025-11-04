# ABOUTME: Command-line interface for llmring-server database and server management.
# ABOUTME: Provides commands for migrations, database creation, and running the development server.

import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg
import click
import uvicorn
from pgdbm import AsyncDatabaseManager, AsyncMigrationManager, DatabaseConfig
from pgdbm.testing import AsyncTestDatabase, DatabaseTestConfig

from .config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """LLMRing Server CLI for database and server management."""
    pass


@cli.command()
@click.option(
    "--env",
    type=click.Choice(["test", "dev", "prod"]),
    default="dev",
    help="Environment to run",
)
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(env: str, host: str, port: int, reload: bool):
    """Run the LLMRing server."""
    # Set environment-specific database URL
    if env == "test":
        os.environ["LLMRING_DATABASE_URL"] = "postgresql://localhost/llmring_test"
        os.environ["LLMRING_DATABASE_SCHEMA"] = "llmring_test"
    elif env == "dev":
        os.environ.setdefault("LLMRING_DATABASE_URL", "postgresql://localhost/llmring_dev")
        os.environ.setdefault("LLMRING_DATABASE_SCHEMA", "llmring")
    elif env == "prod":
        # Production should use explicit environment variables
        if not os.environ.get("LLMRING_DATABASE_URL"):
            click.echo("Error: LLMRING_DATABASE_URL must be set for production", err=True)
            sys.exit(1)

    click.echo(f"Starting LLMRing server in {env} mode on {host}:{port}")
    uvicorn.run(
        "llmring_server.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option(
    "--env",
    type=click.Choice(["test", "dev", "prod"]),
    default="dev",
    help="Environment",
)
def migrate(env: str):
    """Apply database migrations."""
    asyncio.run(_migrate(env))


async def _migrate(env: str):
    """Apply migrations for the specified environment."""
    settings = _get_settings_for_env(env)

    db_config = DatabaseConfig(
        connection_string=settings.database_url,
        schema=settings.database_schema,
    )
    db = AsyncDatabaseManager(db_config)
    await db.connect()

    try:
        click.echo(f"Connected to {env} database")

        # Run migrations
        migrations_path = Path(__file__).parent / "migrations"
        migration_manager = AsyncMigrationManager(
            db, str(migrations_path), module_name="llmring_server"
        )

        result = await migration_manager.apply_pending_migrations()
        if result:
            click.echo(f"Applied migrations: {result}")
        else:
            click.echo("No pending migrations")

    finally:
        await db.disconnect()


@db.command()
@click.option(
    "--env",
    type=click.Choice(["test", "dev", "prod"]),
    default="dev",
    help="Environment",
)
def status(env: str):
    """Show migration status."""
    asyncio.run(_status(env))


async def _status(env: str):
    """Show migration status for the specified environment."""
    settings = _get_settings_for_env(env)

    config = DatabaseConfig(
        connection_string=settings.database_url,
        schema=settings.database_schema,
    )

    db = AsyncDatabaseManager(config)
    await db.connect()

    try:
        migrations_path = Path(__file__).parent / "migrations"
        migrations = AsyncMigrationManager(
            db,
            migrations_path=str(migrations_path),
            module_name="llmring_server",
        )

        # Get applied migrations from database (returns dict keyed by filename)
        applied_dict = await migrations.get_applied_migrations()

        # Get all available migrations from filesystem (returns list of Migration objects)
        all_migrations = await migrations.find_migration_files()

        # Determine pending migrations
        applied_names = set(applied_dict.keys())
        pending = [m for m in all_migrations if m.filename not in applied_names]

        click.echo(f"\n{env.upper()} Database Migration Status:")
        click.echo(f"Database: {settings.database_url}")
        click.echo(f"Schema: {settings.database_schema}")

        if applied_dict:
            click.echo(f"\nApplied migrations ({len(applied_dict)}):")
            for filename, migration in sorted(applied_dict.items()):
                applied_time = (
                    migration.applied_at.strftime("%Y-%m-%d %H:%M:%S")
                    if migration.applied_at
                    else "unknown"
                )
                click.echo(f"  ✓ {filename} (applied {applied_time})")

        if pending:
            click.echo(f"\nPending migrations ({len(pending)}):")
            for m in pending:
                click.echo(f"  ○ {m.filename}")
        else:
            click.echo("\nAll migrations applied ✓")
    finally:
        await db.disconnect()


@db.command()
@click.option("--env", type=click.Choice(["test", "dev"]), default="dev", help="Environment")
def create(env: str):
    """Create database for the specified environment."""
    asyncio.run(_create_db(env))


async def _create_db(env: str):
    """Create database for the specified environment."""
    if env == "test":
        await _create_test_db()
    elif env == "dev":
        await _create_dev_db()


async def _create_dev_db():
    """Create the development database."""
    import asyncpg

    # Connect to postgres database to create the dev database
    conn = await asyncpg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        database="postgres",
    )

    try:
        # Check if database exists
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'llmring_dev'")

        if not exists:
            await conn.execute("CREATE DATABASE llmring_dev")
            click.echo("Created database: llmring_dev")
        else:
            click.echo("Database llmring_dev already exists")
    finally:
        await conn.close()

    # Now connect to the new database and apply migrations
    settings = _get_settings_for_env("dev")
    db_config = DatabaseConfig(
        connection_string=settings.database_url,
        schema=settings.database_schema,
    )
    db = AsyncDatabaseManager(db_config)
    await db.connect()

    try:
        # Run migrations
        migrations_path = Path(__file__).parent / "migrations"
        migration_manager = AsyncMigrationManager(
            db, str(migrations_path), module_name="llmring_server"
        )

        result = await migration_manager.apply_pending_migrations()
        if result:
            click.echo(f"Applied migrations: {result}")
        else:
            click.echo("No pending migrations")
    finally:
        await db.disconnect()


async def _create_test_db():
    """Create and prepare a test database."""
    test_config = DatabaseTestConfig(
        host=os.environ.get("TEST_DB_HOST", "localhost"),
        port=int(os.environ.get("TEST_DB_PORT", "5432")),
        user=os.environ.get("TEST_DB_USER", "postgres"),
        password=os.environ.get("TEST_DB_PASSWORD", "postgres"),
    )

    test_db = AsyncTestDatabase(test_config)

    try:
        # Create test database
        await test_db.create_test_database(suffix="llmring_test")
        click.echo("Created test database")

        # Get connection to the test database
        db_config = test_db.get_test_db_config(schema="llmring_test")
        db = AsyncDatabaseManager(db_config)
        await db.connect()

        try:
            # Apply migrations
            migrations_path = Path(__file__).parent / "migrations"
            migrations = AsyncMigrationManager(
                db,
                migrations_path=str(migrations_path),
                module_name="llmring_test",
            )

            result = await migrations.apply_pending_migrations()
            if result.get("applied"):
                click.echo(f"Applied {len(result['applied'])} migrations to test database")

            click.echo(f"Test database ready: {test_db.test_db_name}")
        finally:
            await db.disconnect()

    except (asyncpg.PostgresError, ValueError, ConnectionError) as e:
        click.echo(f"Error creating test database: {e}", err=True)
        await test_db.drop_test_database()
        sys.exit(1)


@db.command()
def drop_test():
    """Drop the test database."""
    asyncio.run(_drop_test_db())


async def _drop_test_db():
    """Drop the test database."""
    test_config = DatabaseTestConfig(
        host=os.environ.get("TEST_DB_HOST", "localhost"),
        port=int(os.environ.get("TEST_DB_PORT", "5432")),
        user=os.environ.get("TEST_DB_USER", "postgres"),
        password=os.environ.get("TEST_DB_PASSWORD", "postgres"),
    )

    test_db = AsyncTestDatabase(test_config)
    test_db.test_db_name = "test_llmring_test"  # Match what create_test creates

    try:
        await test_db.drop_test_database()
        click.echo("Dropped test database")
    except (asyncpg.PostgresError, ValueError, ConnectionError) as e:
        click.echo(f"Error dropping test database: {e}", err=True)


def _get_settings_for_env(env: str) -> Settings:
    """Get settings for the specified environment."""
    if env == "test":
        os.environ["LLMRING_DATABASE_URL"] = "postgresql://localhost/llmring_test"
        os.environ["LLMRING_DATABASE_SCHEMA"] = "llmring_test"
    elif env == "dev":
        os.environ.setdefault("LLMRING_DATABASE_URL", "postgresql://localhost/llmring_dev")
        os.environ.setdefault("LLMRING_DATABASE_SCHEMA", "llmring")
    elif env == "prod":
        if not os.environ.get("LLMRING_DATABASE_URL"):
            raise click.ClickException("LLMRING_DATABASE_URL must be set for production")

    return Settings()


def main():
    """CLI entry point for llmring-server."""
    cli()


if __name__ == "__main__":
    main()
