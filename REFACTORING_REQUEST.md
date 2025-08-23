# Refactoring Request: llmring-server

**Date**: 2025-08-23  
**Source-of-Truth Version**: v3.7  
**Priority**: High

## Executive Summary

Following the architectural clarification in source-of-truth v3.7, llmring-server needs significant refactoring to align with the new understanding that **aliases are purely local to each codebase** and **Projects are for usage/billing organization, not alias storage**.

## Current State (Misaligned)

The server currently:
- Stores aliases in the database (aliases table)
- Provides sync endpoints for push/pull of aliases
- Treats Projects as containers for aliases
- Manages alias bindings centrally

## Target State (Per v3.7)

The server should:
- **NOT store aliases** at all
- Focus solely on **usage tracking and receipts**
- Store only **logs** with alias names (not their bindings)
- Treat Projects as **usage contexts** for cost allocation

## Required Changes

### 1. Database Schema Changes

**Remove:**
- `aliases` table entirely
- Any foreign keys or references to aliases
- Sync-related tables or columns

**Keep/Enhance:**
- `usage_logs` table (stores which alias was used, not what it resolves to)
- `receipts` table
- `projects` table (reframe as usage contexts)
- `api_keys` table

**Modify usage_logs to include:**
```sql
-- Current (wrong)
alias_id REFERENCES aliases(id)

-- Target (correct)
alias_name VARCHAR(255)  -- Just the name used, no resolution
```

### 2. API Endpoints to Remove

Delete these endpoints entirely:
- `POST /aliases` - Create alias
- `GET /aliases` - List aliases
- `PUT /aliases/{alias_id}` - Update alias
- `DELETE /aliases/{alias_id}` - Delete alias
- `POST /sync/push` - Push aliases to server
- `POST /sync/pull` - Pull aliases from server
- Any alias management endpoints

### 3. API Endpoints to Modify

**`POST /log` endpoint:**
- Currently: May validate alias exists in DB
- Target: Accept any alias name, just log it
- Store: alias_name (string), not alias_id (FK)

**`GET /stats` endpoint:**
- Currently: May join with aliases table
- Target: Group by alias_name string
- Show: Usage per alias name without resolution details

### 4. Core Service Changes

**UsageService:**
```python
# Current (wrong)
async def log_usage(self, alias_id: str, ...):
    alias = await self.get_alias(alias_id)
    # ... validate and log

# Target (correct)
async def log_usage(self, alias_name: str, model_used: str, ...):
    # Just log the usage, no alias validation
    # alias_name is just a string label
```

**Remove entirely:**
- AliasService
- SyncService
- Any alias-related business logic

### 5. Receipt Changes

Receipts should include:
- `alias_name`: The alias used (string)
- `model_used`: The actual model that was called
- `project_key`: For usage attribution
- No alias resolution details

### 6. Project Conceptual Shift

Projects should be reframed as:
- **Usage contexts** (e.g., "Production", "Development", "Client A")
- **Cost allocation units**
- **API key containers**
- **NOT alias containers**

Example project use cases:
- Different environments: dev/staging/prod
- Different teams: frontend/backend/data-science
- Different clients: client-a/client-b
- Different applications: web-app/mobile-app/cli-tool

### 7. Documentation Updates

Update all references to clarify:
- Aliases live in lockfiles, not the server
- Projects organize usage, not aliases
- Server tracks what was used, not how it's configured

## Migration Strategy

1. **Phase 1**: Add new columns (alias_name) alongside old ones
2. **Phase 2**: Update endpoints to use new columns
3. **Phase 3**: Remove alias management endpoints
4. **Phase 4**: Drop old tables/columns
5. **Phase 5**: Update documentation

## Benefits of This Refactoring

1. **Simpler server**: No complex alias management
2. **True decentralization**: Each codebase owns its config
3. **Clearer separation**: Config (lockfile) vs Usage (server)
4. **Better scalability**: No sync conflicts between codebases
5. **Aligned with reality**: How developers actually work

## Backwards Compatibility

- Existing API keys continue to work
- Usage logs preserved (just lose alias resolution)
- Receipts remain valid
- Projects get reframed but not deleted

## Success Criteria

- [ ] No alias storage in database
- [ ] No sync endpoints
- [ ] Usage tracking works with arbitrary alias names
- [ ] Projects clearly documented as usage contexts
- [ ] All tests updated to reflect new architecture

## Timeline Estimate

- Database migration: 2 days
- API refactoring: 3 days
- Testing and validation: 2 days
- Documentation: 1 day
- **Total: ~8 days**

## Notes

This refactoring aligns llmring-server with the core philosophy that **configuration is local** (lockfiles) while **usage is centralized** (server). This is how most development tools work - think of how npm packages are configured locally but registry usage is tracked centrally.

---

*Complies with source-of-truth v3.7*