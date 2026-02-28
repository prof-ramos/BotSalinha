# CLAUDE.md — BotSalinha

## Project Overview

BotSalinha is a Discord bot specialized in **Brazilian law and public contest preparation (concursos públicos)**, powered by OpenAI gpt-4o-mini via the [Agno](https://github.com/agno-agi/agno) AI agent framework. It provides contextual conversations with persistent history, per-user rate limiting, and structured logging.

- **Language:** Python 3.12+
- **Framework:** discord.py + Agno
- **AI Backend:** OpenAI gpt-4o-mini (via `openai`)
- **Database:** SQLite via SQLAlchemy async ORM + Alembic migrations
- **Package Manager:** `uv`

---

## Repository Structure

```text
BotSalinha/
├── bot.py                        # Minimal entry-point wrapper
├── pyproject.toml                # Project metadata and all dependencies
├── config.yaml                   # Agent/model YAML configuration
├── docker-compose.yml            # Development Docker setup
├── docker-compose.prod.yml       # Production Docker setup
├── Dockerfile                    # Multi-stage Docker build
├── pytest.ini                    # Pytest configuration
├── mypy.ini                      # MyPy strict type checking
├── ruff.toml                     # Ruff linter/formatter (100-char lines)
├── .env.example                  # Required environment variables template
├── .pre-commit-config.yaml       # Pre-commit hooks (ruff, mypy, pytest)
│
├── src/                          # Main application source
│   ├── main.py                   # CLI argument parsing and entry points
│   ├── config/
│   │   ├── settings.py           # Pydantic Settings (standard env vars)
│   │   └── yaml_config.py        # YAML config loader with Pydantic validation
│   ├── core/
│   │   ├── agent.py              # Agno AgentWrapper — generates AI responses
│   │   ├── discord.py            # BotSalinhaBot — Discord commands and events
│   │   └── lifecycle.py          # Startup/shutdown lifecycle and signal handling
│   ├── models/
│   │   ├── conversation.py       # ConversationORM + Pydantic schemas
│   │   └── message.py            # MessageORM + Pydantic schemas
│   ├── storage/
│   │   ├── repository.py         # Abstract repository interfaces
│   │   └── sqlite_repository.py  # SQLite implementation (async SQLAlchemy)
│   ├── middleware/
│   │   └── rate_limiter.py       # Token bucket rate limiter (per-user/per-guild)
│   └── utils/
│       ├── logger.py             # structlog setup (JSON or text format)
│       ├── errors.py             # Custom exception hierarchy (BotSalinhaError)
│       └── retry.py              # async_retry decorator with exponential backoff
│
├── tests/
│   ├── conftest.py               # Shared fixtures (DB, settings, mocks)
│   ├── unit/                     # Isolated component tests
│   ├── integration/              # Multi-component tests
│   ├── e2e/                      # Full system workflow tests
│   └── fixtures/                 # Additional test helpers and factories
│
├── migrations/                   # Alembic database migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/                 # Migration scripts
│
├── scripts/
│   ├── backup.py                 # SQLite backup and restore
│   └── run_tests.sh              # Test runner helper script
│
├── prompt/
│   ├── prompt_v1.md              # Active system prompt (simple)
│   ├── prompt_v2.json            # Few-shot prompt with examples
│   └── prompt_v3.md              # Advanced chain-of-thought prompt
│
├── docs/
│   ├── DEVELOPER_GUIDE.md        # Comprehensive developer guide
│   ├── deployment.md             # Docker and deployment instructions
│   └── operations.md             # Runtime operations manual
│
├── .github/workflows/
│   └── test.yml                  # CI/CD: lint, type-check, test (unit/integration/e2e)
│
├── PRD.md                        # Product Requirements Document
├── AGENTS.md                     # Legacy agent conventions file
└── README.md                     # Main documentation (Portuguese)
```

---

## Essential Commands

### Install and Run

```bash
uv sync                # Install dependencies
uv run bot.py          # Run the bot locally
uv run pytest          # Run all tests
```

### Run CLI chat mode (for development/testing without Discord)

```bash
uv run bot.py --chat
```

### Linting and Type Checking

```bash
# Lint check (non-destructive)
uv run ruff check src/

# Auto-format code
uv run ruff format src/

# Type checking (strict mode)
uv run mypy src/
```

### Testing

```bash
# Run all tests
uv run pytest

# Run a single test by name
uv run pytest tests/ -k test_name

# Run specific test suite
uv run pytest tests/unit -v
uv run pytest tests/integration -v
uv run pytest tests/e2e -v

# Run with coverage report
uv run pytest --cov=src --cov-report=html

# Run in parallel
uv run pytest --numprocesses=auto

# Using the helper script
scripts/run_tests.sh --unit
scripts/run_tests.sh --integration
scripts/run_tests.sh --e2e
scripts/run_tests.sh --all --parallel
```

**Minimum coverage required:** 70% (enforced in CI)

### Database Migrations

```bash
# Create a new migration (after modifying ORM models)
uv run alembic revision --autogenerate -m "description"

# Apply all pending migrations
uv run alembic upgrade head

# Revert the last migration
uv run alembic downgrade -1
```

### Database Backup

```bash
uv run python scripts/backup.py backup           # Create backup
uv run python scripts/backup.py list             # List backups
uv run python scripts/backup.py restore --restore-from <file>
```

### Docker

```bash
# Development
docker-compose up -d
docker-compose logs -f
docker-compose down

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Pre-commit Hooks

```bash
# Install hooks (run once after cloning)
uv run pre-commit install

# Manually run all hooks
uv run pre-commit run --all-files
```

---

## Environment Configuration

Copy `.env.example` to `.env` and fill in the required values:

| Variable                        | Default                        | Required | Description                   |
| -------------------------------- | ------------------------------ | -------- | ----------------------------- |
| `DISCORD_BOT_TOKEN`             | —                              | **Yes**  | Discord bot token             |
| `DISCORD_MESSAGE_CONTENT_INTENT`| `true`                         | No       | Enable message content intent |
| `COMMAND_PREFIX`                | `!`                            | No       | Command prefix                |
| `DISCORD__CANAL_IA_ID`          | None                           | No       | ID do canal dedicado IA (opcional) |
| `OPENAI_API_KEY`                | —                              | **Yes**  | OpenAI API key               |
| `GOOGLE_API_KEY`                | —                              | No       | Google API key                |
| `HISTORY_RUNS`                  | `3`                            | No       | Conversation history pairs    |
| `RATE_LIMIT_REQUESTS`           | `10`                           | No       | Max requests per window       |
| `RATE_LIMIT_WINDOW_SECONDS`     | `60`                           | No       | Rate limit time window        |
| `DATABASE_URL`                  | `sqlite:///data/botsalinha.db` | No       | SQLite database path          |
| `LOG_LEVEL`                     | `INFO`                         | No       | Log level                     |
| `LOG_FORMAT`                    | `json`                         | No       | `json` or `text`             |
| `APP_ENV`                       | `development`                  | No       | Environment                   |
| `DEBUG`                         | `false`                        | No       | Debug mode                    |
| `MAX_RETRIES`                   | `3`                            | No       | Max retries                  |
| `RETRY_DELAY_SECONDS`           | `1`                            | No       | Retry delay                  |
| `RETRY_MAX_DELAY_SECONDS`       | `60`                           | No       | Max retry delay              |

**Nota:** O projeto suporta tanto nomes flat (ex: `DATABASE_URL`) quanto nomes aninhados com underscores duplos (ex: `DATABASE__URL`). O formato aninhado tem prioridade sobre o formato flat quando ambos estão presentes.

---

## Architecture

### Layered Architecture

```text
Discord (discord.py Commands)
         ↓
Middleware (RateLimiter — token bucket per user/guild)
         ↓
Service Layer (AgentWrapper — Agno + OpenAI)
         ↓
Data Access Layer (Repository Pattern — abstract interfaces)
         ↓
Storage Layer (SQLite + SQLAlchemy Async)
```

### Key Design Patterns

- **Repository Pattern:** `ConversationRepository` and `MessageRepository` are abstract interfaces in `src/storage/repository.py`. The only concrete implementation is `SQLiteRepository` in `src/storage/sqlite_repository.py`. Tests use an in-memory SQLite database.
- **Pydantic Settings:** `src/config/settings.py` uses `pydantic-settings` with `@lru_cache` for a singleton. Never call `Settings()` directly; use `get_settings()`.
- **YAML Config:** Agent and model settings live in `config.yaml`, parsed by `src/config/yaml_config.py` with Pydantic validation. The active prompt file is specified here (`prompt_v1.md` by default).
- **Async Throughout:** All I/O-bound operations use `async/await`. Never call blocking functions from async context.
- **Dependency Injection:** The repository is instantiated at startup and injected into `AgentWrapper` and `BotSalinhaBot`.

---

## Code Conventions

### Naming

| Item              | Convention           | Example                               |
| ----------------- | -------------------- | ------------------------------------- |
| Classes           | PascalCase           | `BotSalinhaBot`, `ConversationORM`    |
| Functions/Methods | snake_case           | `run_discord_bot`, `check_rate_limit` |
| Private members   | `_underscore` prefix | `_ready_event`, `_initialized`        |
| Constants         | UPPER_SNAKE_CASE     | `MAX_RETRIES`                         |
| Async functions   | `async def`          | `async def generate_response()`       |
| Type hints        | Always present       | `str \| None` (not `Optional[str]`)   |

### Import Order (enforced by Ruff/isort)

```python
# 1. Standard library
import asyncio
from typing import Any

# 2. Third-party
import structlog
import discord
from discord.ext import commands

# 3. Local (relative)
from .config.settings import get_settings
from .utils.logger import setup_logging
```

### Error Handling

- All custom exceptions inherit from `BotSalinhaError` (`src/utils/errors.py`).
- Catch specific exceptions — never bare `except:`.
- Log with structlog before raising.
- Include a human-readable message and optional `details: dict`.

```python
from src.utils.errors import BotSalinhaError

class MyError(BotSalinhaError):
    """Describe what went wrong."""
    pass

try:
    await some_operation()
except SpecificError as e:
    log.error("operation_failed", error=str(e), context=ctx)
    raise MyError("Human-readable message", details={"key": "value"}) from e
```

Exception types:

- `APIError` — External API failures
- `RateLimitError` — Rate limit exceeded
- `ValidationError` — Input validation failures
- `DatabaseError` — Database operation failures
- `ConfigurationError` — Configuration issues
- `RetryExhaustedError` — All retry attempts failed

### Logging

```python
import structlog
log = structlog.get_logger(__name__)

# Structured logging — always use keyword args for context
log.info("event_name", user_id=user_id, guild_id=guild_id)
log.error("operation_failed", error=str(e), detail=extra)
```

Use `bind_request_context()` from `src/utils/logger.py` to attach correlation IDs for tracing across async operations.

### Async Retry

```python
from src.utils.retry import async_retry, AsyncRetryConfig

@async_retry(AsyncRetryConfig(max_attempts=3, base_delay=1.0))
async def call_external_api() -> str:
    ...
```

### Pydantic Models

- Data schemas inherit from `BaseModel`.
- SQLAlchemy ORM models use `Mapped[Type]` column annotations.
- Use `Field()` for metadata, defaults, and validation constraints.
- ORM models inherit from `Base` (SQLAlchemy declarative base), not from `BaseModel`.

---

## Testing Strategy

### Test Markers

```python
@pytest.mark.unit          # Isolated component test (no I/O)
@pytest.mark.integration   # Multiple components together
@pytest.mark.e2e           # Full system workflow
@pytest.mark.slow          # Takes > 1 second
@pytest.mark.discord       # Requires Discord API mock
@pytest.mark.gemini        # Requires AI API mock (previously gemini-only)
@pytest.mark.database      # Requires database access
```

### Key Fixtures (from `tests/conftest.py`)

| Fixture           | Description                                       |
| ----------------- | ------------------------------------------------- |
| `test_settings`   | Pydantic settings configured for test environment |
| `test_engine`     | Async SQLAlchemy engine (in-memory SQLite)        |
| `test_session`    | Scoped async database session                     |
| `test_repository` | In-memory `SQLiteRepository` instance             |
| `rate_limiter`    | `RateLimiter` instance                            |

### Testing Patterns

- Use in-memory SQLite (`sqlite+aiosqlite:///:memory:`) for database tests.
- Mock Discord API with `pytest-mock` — never make real Discord calls in tests.
- Mock OpenAI API — never make real API calls in tests.
- Use `faker` with `pt_BR` locale for realistic Brazilian test data.
- Use `freezegun` for time-dependent tests.

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/test.yml`) runs on push to `main`/`develop` and on pull requests:

| Job                   | What it does                                       |
| --------------------- | -------------------------------------------------- |
| **Lint**              | `ruff check`, `ruff format --check`, `mypy src/`   |
| **Unit Tests**        | `pytest tests/unit` with coverage upload           |
| **Integration Tests** | `pytest tests/integration`                         |
| **E2E Tests**         | `pytest tests/e2e` (needs Discord/OpenAI secrets)  |
| **All Tests**         | Full parallel run, enforces 70% coverage threshold |

---

## Prompt Management

System prompts live in `prompt/`. The active prompt is configured in `config.yaml`:

| File             | Style                     | Status               |
| ---------------- | ------------------------- | -------------------- |
| `prompt_v1.md`   | Simple, direct            | **Active (default)** |
| `prompt_v2.json` | Few-shot with examples    | Available            |
| `prompt_v3.md`   | Advanced chain-of-thought | Available            |

To switch prompts, update `config.yaml` → `prompt.file`.

---

## Discord Bot Commands

| Command           | Description                                           |
| ----------------- | ----------------------------------------------------- |
| `!ask <question>` | Ask the AI a question about Brazilian law or contests |
| `!ping`           | Health check                                          |
| `!ajuda`          | Show help message                                     |
| `!info`           | Show bot information                                  |
| `!limpar`         | Clear conversation history for the user               |

### Modos de Chat

| Mode             | Description                                             | Configuration Required |
| ---------------- | ------------------------------------------------------- | --------------------- |
| **Channel IA**   | Automatic response in dedicated channel                  | `DISCORD__CANAL_IA_ID` |
| **DM**           | Automatic response to direct messages                   | None (always enabled)  |

---

## Common Development Tasks

### Adding a New Discord Command

1. Open `src/core/discord.py`.
2. Add a new method decorated with `@commands.command(name="mycommand")`.
3. Apply rate limiting via the existing `rate_limiter` check pattern.
4. Add corresponding unit tests in `tests/unit/`.

### Adding a New Configuration Option

1. Add the field to the appropriate nested config class in `src/config/settings.py`.
2. Add the env variable to `.env.example` with a description and default.
3. Update this CLAUDE.md environment table if needed.

### Adding a New Database Model

1. Create the ORM model (inheriting from `Base`) and Pydantic schemas in `src/models/`.
2. Add abstract methods to `src/storage/repository.py`.
3. Implement the methods in `src/storage/sqlite_repository.py`.
4. Generate a migration: `uv run alembic revision --autogenerate -m "add_my_model"`.
5. Apply: `uv run alembic upgrade head`.

### Configuring Channel IA Mode

1. Add to `.env`:
```env
DISCORD__CANAL_IA_ID=123456789012345678
```

2. Restart the bot:
```bash
uv run bot.py  # or docker-compose restart
```

### Running the Bot Locally (without Discord)

```bash
cp .env.example .env
# Edit .env with your GOOGLE API key (DISCORD token not needed for CLI mode)
uv sync
uv run bot.py --chat
```

---

## Important Files to Know

| File                               | Why it matters                                             |
| ---------------------------------- | ---------------------------------------------------------- |
| `src/config/settings.py`           | All configuration with defaults and validation             |
| `src/core/discord.py`              | All bot commands and Discord event handlers, including `on_message` |
| `src/core/agent.py`                | AI response generation and conversation history            |
| `src/storage/sqlite_repository.py` | All database operations                                    |
| `src/utils/errors.py`              | Exception hierarchy — use these, don't use bare exceptions |
| `config.yaml`                      | Model provider, prompt file, agent behavior flags          |
| `tests/conftest.py`                | All shared test fixtures                                   |
| `.env.example`                     | Canonical list of all supported environment variables      |
