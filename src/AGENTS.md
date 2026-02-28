# AGENTS.md — BotSalinha Source Code

<!-- PARENT: ../AGENTS.md -->
<!-- GENERATED: 2026-02-27 -->
<!-- UPDATED: 2026-02-27 -->

## Purpose

This document describes the BotSalinha source code organization, architecture patterns, and development guidelines for AI agents working on this codebase. It provides context for understanding the layered architecture, key design patterns, and code conventions used throughout the application.

---

## Key Files by Layer

| Category | Files | Purpose |
|----------|------|---------|
| **Configuration** | `config/settings.py` | Pydantic Settings with validation and caching |
| | `config/yaml_config.py` | YAML config loader with Pydantic validation |
| **Core Logic** | `core/agent.py` | Agno AgentWrapper for AI response generation |
| | `core/discord.py` | Discord bot commands and event handlers |
| | `core/cli.py` | CLI argument parsing and chat mode |
| | `core/lifecycle.py` | Application startup/shutdown and signal handling |
| **Models** | `models/conversation.py` | Conversation ORM and Pydantic schemas |
| | `models/message.py` | Message ORM and Pydantic schemas |
| **Storage** | `storage/repository.py` | Abstract repository interfaces |
| | `storage/factory.py` | Repository factory with dependency injection |
| | `storage/sqlite_repository.py` | SQLite implementation with async SQLAlchemy |
| **Middleware** | `middleware/rate_limiter.py` | Token bucket rate limiter per user/guild |
| **Tools** | `tools/` | MCP tools integration directory |
| **Utilities** | `utils/logger.py` | structlog setup with correlation IDs |
| | `utils/errors.py` | Custom exception hierarchy |
| | `utils/retry.py` | Async retry with exponential backoff |

---

## Source Code Organization

### Configuration Layer (`config/`)

- **`settings.py`**: Centralized configuration using Pydantic Settings
  - Singleton pattern via `@lru_cache`
  - Supports both flat and nested environment variables (with `__` delimiter)
  - Always use `get_settings()` instead of direct instantiation
- **`yaml_config.py`**: Agent and model configuration loader
  - Validates against Pydantic schemas
  - Loads prompt files specified in config.yaml

### Core Layer (`core/`)

- **`agent.py`**: Agno AgentWrapper implementation
  - Manages conversation history with persistent storage
  - Handles AI response generation with context
  - Integrates with repository for data persistence
- **`discord.py`**: Main bot implementation
  - Discord.py commands and event handlers
  - Rate limiting middleware integration
  - CLI chat mode for development/testing
- **`cli.py`**: Command-line interface
  - Argument parsing and validation
  - Chat mode execution without Discord
  - Health check and diagnostic commands
- **`lifecycle.py`**: Application lifecycle management
  - Signal handling for graceful shutdown
  - Resource cleanup and async context management

### Data Layer (`models/`, `storage/`)

- **Models**: SQLAlchemy ORM with Pydantic schemas
  - Separate ORM models and data schemas
  - Type-safe database operations
  - Migrations via Alembic
- **Storage**: Repository pattern with dependency injection
  - Abstract interfaces for testability
  - SQLite implementation with async SQLAlchemy
  - Factory pattern for dependency injection

---

## AI Agent Instructions

### Working with BotSalinha Codebase

1. **Understand the Architecture**:
   - Layered design: Discord → Middleware → Service → Data Access → Storage
   - Repository pattern for database operations
   - Dependency injection via factory pattern
   - Async throughout with proper error handling

2. **Follow Code Conventions**:
   - Naming: PascalCase for classes, snake_case for functions/methods
   - Imports: Standard library → Third-party → Local (relative)
   - Error handling: Custom exceptions from `BotSalinhaError`
   - Logging: Use structlog with structured context

3. **Key Patterns to Follow**:
   - Always use `get_settings()` for configuration
   - Use `async with create_repository() as repo:` for database operations
   - Apply rate limiting to all bot commands
   - Use `@async_retry` for external API calls
   - Log all operations with proper context

### Testing Requirements

When creating new features or fixing bugs:

1. **Unit Tests**: Test individual components in isolation
   - Mock external dependencies (Discord, OpenAI, database)
   - Use fixtures from `tests/conftest.py`
   - Follow the test marker convention (`@pytest.mark.unit`)

2. **Integration Tests**: Test component interactions
   - Test repository implementations
   - Test middleware behavior
   - Mock external APIs but use real database

3. **E2E Tests**: Test complete workflows
   - Test full Discord bot interactions
   - Test CLI chat mode
   - Include database persistence checks

### Common Development Tasks

#### Adding New Features

1. **Configuration**: Add to `settings.py` and `.env.example`
2. **Business Logic**: Implement in appropriate `core/` module
3. **Data Storage**: Add models and repository methods
4. **Tests**: Create unit, integration, and e2e tests
5. **Documentation**: Update this AGENTS.md if needed

#### Working with Database

- Use `create_repository()` factory for dependency injection
- Follow the repository pattern: abstract interfaces in `repository.py`
- Generate migrations: `uv run alembic revision --autogenerate -m "description"`
- Apply migrations: `uv run alembic upgrade head`

#### Handling Errors

- Use custom exceptions from `utils/errors.py`
- Include human-readable messages and context
- Log with structlog before raising exceptions
- Implement retry logic for external API calls

---

## Dependencies and Dependencies

### External Dependencies

| Category | Dependencies | Purpose |
|----------|-------------|---------|
| **AI/ML** | `agno`, `openai` | AI agent framework and OpenAI API |
| **Discord** | `discord.py` | Discord bot framework |
| **Database** | `sqlalchemy[asyncio]`, `alembic` | Async ORM and migrations |
| **Configuration** | `pydantic`, `pydantic-settings`, `pyyaml` | Configuration management |
| **CLI/Tools** | `uv`, `structlog`, `faker`, `freezegun` | Development tools |
| **Testing** | `pytest`, `pytest-asyncio`, `pytest-mock` | Testing framework |

### Internal Dependencies

- Core modules depend on config and utils
- Storage layer depends on models
- All async operations follow proper patterns
- Dependency injection via factory pattern

---

## Migration Notes

### v2.0: Transition to Dependency Injection

- **New**: Use `create_repository()` factory for repository instances
- **Legacy**: `get_repository()` is deprecated (removal in v2.1)
- **Pattern**:
  ```python
  from src.storage.factory import create_repository

  async def my_function():
      async with create_repository() as repo:
          await repo.some_operation()
  ```

### Testing Infrastructure

- Comprehensive test suite with multiple markers
- Mock external APIs in tests
- Use in-memory SQLite for database tests
- Coverage requirement: 70% minimum

---

## Quality Standards

### Code Quality

- Linting: `ruff check` and `ruff format`
- Type checking: `mypy src/` (strict mode)
- Pre-commit hooks for automatic quality checks
- Documentation in CLAUDE.md and AGENTS.md

### Security

- Rate limiting per user/guild
- Environment variable validation
- Secure handling of API keys
- Proper error handling to avoid information leaks

### Performance

- Async throughout for I/O operations
- Connection pooling for database
- Proper resource cleanup
- Efficient conversation history management