# Changelog

All notable changes to llmring-server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- **Cryptographic receipts system**: Removed receipt generation, storage, and verification endpoints. The cryptographic signatures provided minimal security value as they don't prevent tampering by the service operator. Usage tracking and cost calculation remain fully functional.

## [0.1.2] - 2025-10-14

### Changed
- Updated pgdbm dependency from >=0.1.0 to >=0.2.0

## [0.1.1] - 2025-09-29

### Added
- Pre-commit hooks for automatic code formatting (black, isort)
- Tool configuration in pyproject.toml (black, isort, ruff, pytest)

### Changed
- Formatted all code with black and isort
- Fixed trailing whitespace and end of file issues across codebase

### Fixed
- Documentation: corrected all references from `X-Project-Key` to `X-API-Key`
- Removed outdated SaaS integration note from README

## [0.1.0] - 2025-09-29

### Added
- Initial release of llmring-server
- Usage tracking with `/api/v1/log` and `/api/v1/stats` endpoints
- Cryptographically signed receipts with Ed25519 over RFC 8785 JCS
- Registry proxy for public model registry from GitHub Pages
- Conversation management with message storage
- MCP integration for servers, tools, resources, and prompts
- Conversation templates for reusable workflows
- Dual-mode operation: standalone server or library mode
- Comprehensive database management CLI with test/dev/prod environments
- PostgreSQL schema migrations via pgdbm
- Redis caching support for registry and other data
- Project-scoped authentication via `X-API-Key` header
- Public key endpoints (PEM, JWK, JSON formats)
- CORS configuration for self-hosting
- Health check endpoint
- OpenAPI/Swagger documentation at `/docs`

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- Key-scoped data access (no cross-project data leakage)
- Ed25519 signature verification for receipts
- Header validation (length, whitespace checks)
- CORS configuration with origin restrictions

[0.1.2]: https://github.com/juanre/llmring/releases/tag/llmring-server-0.1.2
[0.1.1]: https://github.com/juanre/llmring/releases/tag/llmring-server-0.1.1
[0.1.0]: https://github.com/juanre/llmring/releases/tag/llmring-server-0.1.0
