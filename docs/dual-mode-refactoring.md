# LLMRing-Server Dual-Mode Refactoring

## Overview

LLMRing-Server has been refactored to support dual-mode operation, following the Pattern 2B documented in pgdbm. This allows the server to work both as a standalone service and as a library integrated into larger applications like llmring-api.

## Key Changes

### 1. Database Layer (`database.py`)

The `Database` class now supports both modes:

- **Standalone Mode**: Creates its own database connection with configurable pool sizes
- **Library Mode**: Uses an external `AsyncDatabaseManager` provided by the parent application

```python
class Database:
    def __init__(
        self,
        connection_string: Optional[str] = None,
        db_manager: Optional[AsyncDatabaseManager] = None,
        schema: str = "llmring",
        min_connections: int | None = None,
        max_connections: int | None = None,
    ):
        """Initialize database in standalone or library mode."""
```

### 2. Application Factory (`main.py`)

Created a `create_app()` function that configures the FastAPI application based on the mode:

```python
def create_app(
    db_manager: Optional[AsyncDatabaseManager] = None,
    run_migrations: bool = True,
    schema: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> FastAPI:
    """Create llmring-server app supporting both standalone and library modes."""
```

Key features:
- Detects mode based on presence of `db_manager`
- Manages database lifecycle appropriately for each mode
- Stores mode information in app state for debugging
- Allows migration control via `run_migrations` parameter

### 3. CLI Support (`cli.py`)

The CLI remains unchanged and continues to support standalone operation with test/dev/prod environments. The CLI always operates in standalone mode.

### 4. Test Coverage (`tests/test_dual_mode.py`)

Comprehensive tests verify both modes work correctly:

- **Dual-mode fixture**: Tests core endpoints in both standalone and library modes
- **Database tests**: Verify database operations work in both modes
- **Configuration tests**: Ensure custom settings and external databases work
- **API consistency**: Verifies both modes expose the same API interface

## Integration with LLMRing-API

LLMRing-API has been updated to use llmring-server as a library:

1. Creates a shared database connection pool
2. Passes it to llmring-server via `create_app()`
3. Uses schema isolation (llmring vs llmring_api schemas)
4. Mounts server routes dynamically after startup
5. Overrides specific endpoints like `/health` and `/` for SaaS customization

## Benefits

1. **Resource Efficiency**: Single database connection pool shared across services
2. **Schema Isolation**: Different services use different schemas in the same database
3. **Migration Management**: Each module manages its own migrations independently
4. **Flexible Deployment**: Can run standalone for simple deployments or integrated for complex ones
5. **Testability**: Both modes can be tested independently

## Migration Path

For existing deployments:

1. **Standalone deployments**: No changes needed, continue using the CLI
2. **Integrated deployments**: Update to use `create_app()` with shared database

## Testing

Run the dual-mode tests:

```bash
cd llmring-server
uv run pytest tests/test_dual_mode.py -xvs
```

Run integration tests from llmring:

```bash
cd llmring
uv run pytest tests/integration/test_server_integration.py -xvs
```

## Future Improvements

1. Add configuration for connection pool sharing strategies
2. Support for read replicas in library mode
3. Enhanced monitoring for multi-module deployments
4. Migration dependency resolution across modules