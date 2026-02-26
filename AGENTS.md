# AGENTS.md

## Project Overview

BotSalinha is a Discord bot specialized in Brazilian law and public contests, powered by Agno and Google Gemini 2.5 Flash Lite.

## Build, Lint, and Test Commands

### Core Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run botsalinha
# Or: uv run bot.py

# Linting
uv run ruff check .
uv run ruff format .  # Auto-format

# Type checking
uv run mypy src

# Run all tests
uv run pytest
# Or use the script: scripts/run_tests.sh --all

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run a single test
uv run pytest tests/ -k test_name

# Run specific test suite
scripts/run_tests.sh --unit        # Unit tests only
scripts/run_tests.sh --integration # Integration tests only
scripts/run_tests.sh --e2e         # E2E tests only
scripts/run_tests.sh --all --parallel
```

### Test Markers

- `unit`: Isolated component tests
- `integration`: Component integration tests
- `e2e`: End-to-end system tests
- `slow`: Tests taking > 1 second
- `discord`: Tests requiring Discord API mocks
- `gemini`: Tests requiring Gemini API mocks
- `database`: Tests requiring database access

## Code Style Guidelines

### General Conventions

- **Python Version**: 3.12+
- **Line Length**: 100 characters (Ruff)
- **Docstrings**: Use triple-quoted strings with type hints
- **Comments**: Brief, explain why not what

### Naming Conventions

- **Classes**: PascalCase (`BotSalinhaBot`, `ConversationORM`)
- **Functions**: snake_case (`parse_args`, `run_discord_bot`)
- **Private Members**: Underscore prefix (`_ready_event`, `_initialized`)
- **Constants**: UPPER_SNAKE_CASE
- **Async Functions**: `async def function_name()`
- **Type Hints**: Always use, prefer built-in types (`str`, `int`, `list`)

### Import Organization (Ruff + isort)

1. Standard library imports first
2. Third-party imports second
3. Local project imports last
4. Relative imports use `.` prefix

**Example:**

```python
# Standard library
import asyncio
from typing import Any

# Third-party
import structlog
import discord
from discord.ext import commands

# Local
from .config.settings import settings
from .utils.logger import setup_logging
```

### Code Organization

- **src/core/**: Bot logic, Discord commands, agent integration
- **src/config/**: Configuration management and settings
- **src/models/**: SQLAlchemy ORM models and Pydantic schemas
- **src/storage/**: Database repositories and operations
- **src/utils/**: Shared utilities and helper functions
- **src/middleware/**: Request/response interceptors

### Type Checking (Mypy)

- Strict mode enabled
- Pydantic types supported via plugin
- Use TYPE_CHECKING for runtime-only imports
- Define mappings with `Mapped[Type]` syntax

### Error Handling

1. Create custom exceptions inheriting from `BotSalinhaError`
2. Include human-readable message and optional details dict
3. Use context managers (`with` statements) for cleanup
4. Log errors with structlog before raising
5. Catch specific exceptions rather than bare `except:`

**Example:**

```python
class MyError(BotSalinhaError):
    """Custom error with details."""
    pass

try:
    # operation
except SpecificError as e:
    log.error("operation_failed", error=str(e))
    raise
```

### Pydantic Models

- Use `BaseModel` for schemas
- Define relationships with `Field()`
- Model config for validation settings
- ORM models inherit from Base (not SQLAlchemy's declarative_base)

### Logging

- Use `structlog.get_logger()` for logging
- Bind context variables with `bind_request_context()`
- Log at appropriate levels (info, warning, error)
- Use structured logging with context

### Testing

- Test organization matches src structure
- Use pytest fixtures from `tests/conftest.py`
- Mock external dependencies (Discord, Gemini APIs)
- Test both happy paths and error conditions
- Run tests in parallel with `--numprocesses=auto`

### Pre-commit Hooks

Pre-commit is configured via `.pre-commit-config.yaml`:
- `ruff`: Lint and format code
- `mypy`: Type checking
- `pytest`: Run tests
- `pip-audit`: Security audit

Enable with: `uv run pre-commit install`

## Testing Strategy

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── fixtures/            # Additional fixtures
├── unit/                # Unit tests
├── integration/         # Integration tests
└── e2e/                 # E2E tests
```

### Testing Patterns

1. **Unit Tests**: Isolated function/class tests
2. **Integration Tests**: Multiple components together
3. **E2E Tests**: Full system workflows
4. **Fixtures**: Reusable test setup in `conftest.py`

## Development Workflow

1. **Pre-commit**: Enable hooks for automated checks

2. **Development**: Use `uv run` for all Python commands
3. **Testing**: Run tests frequently, verify coverage > 80%
4. **Linting**: Ensure code passes Ruff checks
5. **Type Checking**: Run mypy before committing

## Environment Configuration

- **Production**: Use `.env.production`
- **Testing**: Uses in-memory SQLite for speed
- **Development**: Uses local configuration

See `config.yaml` and `config.yaml.example` for structure.
