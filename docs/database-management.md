# LLMRing Server Database Management

## Overview

LLMRing Server uses PostgreSQL for persistent storage and provides CLI commands for database management across three environments: test, development, and production.

## Environments

### Test Environment
- Database: `test_llmring_test` (auto-generated name)
- Schemas: `llmring_test`, `mcp_client` (for MCP data)
- Purpose: Automated testing with full isolation
- Lifecycle: Created and destroyed per test run

### Development Environment
- Database: `llmring_dev`
- Schemas: `llmring`, `mcp_client`
- Purpose: Local development
- Configuration: Default localhost connection

### Production Environment
- Database: Configured via `LLMRING_DATABASE_URL`
- Schemas: Configured via `LLMRING_DATABASE_SCHEMA` (default: `llmring`) + `mcp_client`
- Purpose: Production deployment
- Configuration: Must be explicitly set via environment variables

## CLI Commands

### Database Creation

Create a database for development:
```bash
llmring-server db create --env dev
```

Create a test database:
```bash
llmring-server db create --env test
```

### Migration Management

Apply migrations:
```bash
llmring-server db migrate --env dev
```

Check migration status:
```bash
llmring-server db status --env dev
```

### Running the Server

Start server in development mode:
```bash
llmring-server serve --env dev
```

Start server with auto-reload:
```bash
llmring-server serve --env dev --reload
```

Start server in production:
```bash
# Set required environment variables first
export LLMRING_DATABASE_URL="postgresql://user:pass@host/dbname"
export LLMRING_DATABASE_SCHEMA="llmring"

llmring-server serve --env prod
```

## Environment Variables

### Database Configuration
- `LLMRING_DATABASE_URL`: PostgreSQL connection string
- `LLMRING_DATABASE_SCHEMA`: Database schema (default: "llmring")
- `LLMRING_DATABASE_POOL_SIZE`: Connection pool size (default: 20)
- `LLMRING_DATABASE_POOL_OVERFLOW`: Additional connections allowed (default: 10)

### Test Database Configuration
- `TEST_DB_HOST`: Test database host (default: "localhost")
- `TEST_DB_PORT`: Test database port (default: "5432")
- `TEST_DB_USER`: Test database user (default: "postgres")
- `TEST_DB_PASSWORD`: Test database password (default: "postgres")

## Testing Integration

The test suite uses pgdbm fixtures for automatic database isolation:

```python
# In llmring/tests/conftest.py
@pytest_asyncio.fixture
async def llmring_server_client(test_db_factory):
    """Run llmring-server with isolated test database."""
    # Creates fresh database per test
    db = await test_db_factory.create_db(suffix="llmring", schema="llmring_test")
    
    # Apply migrations
    migrations = AsyncMigrationManager(db, ...)
    await migrations.apply_pending_migrations()
    
    # Inject test database into app
    server_app.state.db = db
    
    # Provide HTTP client for testing
    async with AsyncClient(...) as client:
        yield client
```

This ensures:
- Complete isolation between tests
- Automatic cleanup after each test
- No interference between parallel test runs

## Migration Files

Migrations are stored in `src/llmring_server/migrations/`:
- `001_initial.sql`: Core tables (usage logs, receipts)
- `002_profiles_and_receipts.sql`: Profiles and receipts support

Migration naming convention:
- Prefix with 3-digit number (001, 002, etc.)
- Descriptive name after underscore
- `.sql` extension

## Database Schema

The server uses a key-scoped architecture (no user management):

### Core Tables
- `usage_logs`: Request/response tracking (includes optional `alias` string and `profile`)
- `receipts`: Signed usage receipts (includes optional `alias` string and `profile`)

### Key Concepts
- All data is scoped by API key (via `X-API-Key` header)
- No user accounts or authentication in core server
- Profiles support (dev/staging/prod) per alias binding
- Receipts provide cryptographic proof of usage

## Troubleshooting

### Database Does Not Exist
```bash
# Create the database first
llmring-server db create --env dev
```

### Migration Conflicts
```bash
# Check current status
llmring-server db status --env dev

# Manually connect if needed
psql -d llmring_dev
```

### Connection Issues
- Verify PostgreSQL is running
- Check connection parameters in environment
- Ensure database user has necessary permissions

## Best Practices

1. **Always use environment-specific commands**: Don't mix test/dev/prod databases
2. **Run migrations before starting server**: Ensure schema is up-to-date
3. **Use test fixtures for testing**: Don't manually manage test databases
4. **Set production config explicitly**: Never rely on defaults in production
5. **Monitor migration status**: Check status after deployments

## Development Workflow

1. Create development database:
   ```bash
   llmring-server db create --env dev
   ```

2. Run migrations:
   ```bash
   llmring-server db migrate --env dev
   ```

3. Start development server:
   ```bash
   llmring-server serve --env dev --reload
   ```

4. Run tests (automatic database handling):
   ```bash
   pytest tests/
   ```