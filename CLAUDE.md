# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BotSalinha is a Discord bot specialized in **Brazilian law and public contest preparation (concursos públicos)**. It provides contextual conversations with persistent history, per-user rate limiting, RAG (Retrieval-Augmented Generation), and structured logging.

- **Language:** Python 3.12+
- **Framework:** discord.py + [Agno](https://github.com/agno-agi/agno) AI agent framework
- **AI Backend:** Multi-model support (OpenAI default, Google Gemini alternative)
- **Database:** SQLite via SQLAlchemy async ORM (Supabase optional)
- **RAG:** Document + codebase ingestion with vector search
- **Package Manager:** `uv`

---

## Repository Structure

```
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
│   │   ├── settings.py           # Pydantic Settings (env vars with BOTSALINHA_ prefix)
│   │   └── yaml_config.py        # YAML config loader with Pydantic validation
│   ├── core/
│   │   ├── agent.py              # Agno AgentWrapper — generates AI responses with RAG
│   │   ├── cli.py                # Interactive CLI chat mode
│   │   ├── discord.py            # BotSalinhaBot — Discord commands and events
│   │   └── lifecycle.py          # Startup/shutdown lifecycle and signal handling
│   ├── models/
│   │   ├── conversation.py       # ConversationORM + Pydantic schemas
│   │   ├── message.py            # MessageORM + Pydantic schemas
│   │   └── rag_models.py         # RAG DocumentORM, ChunkORM models
│   ├── rag/                      # RAG (Retrieval-Augmented Generation) module
│   │   ├── parser/               # Document parsers (DOCX, XML, code chunking)
│   │   ├── services/             # RAG services (query, ingestion, embeddings)
│   │   ├── storage/              # Vector store and RAG repository
│   │   └── utils/                # RAG utilities (confidence, metadata, ranking)
│   ├── storage/
│   │   ├── factory.py            # Repository factory (DI pattern)
│   │   ├── repository.py         # Abstract repository interfaces
│   │   ├── sqlite_repository.py  # SQLite implementation (default)
│   │   └── supabase_repository.py # Supabase implementation (optional)
│   ├── tools/                    # Integrations (MCP manager, etc.)
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
# Install dependencies
uv sync

# Run the Discord bot
uv run botsalinha
# or: uv run bot.py

# Run CLI chat mode (for development/testing without Discord)
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

### RAG (Retrieval-Augmented Generation)

```bash
# Ingest single document
uv run python scripts/ingest_rag.py data/documents/doc.docx --replace

# Ingest entire codebase (requires Repomix XML output)
uv run python scripts/ingest_codebase_rag.py repomix_output.xml --replace

# Ingest all documents from data/documents/
uv run python scripts/ingest_all_rag.py --replace

# Test RAG query
uv run python scripts/test_rag_query.py "pergunta sobre direito"

# Analyze RAG quality
uv run python scripts/analizar_qualidade_rag.py
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

### RAG Scripts (scripts/)

```bash
# Document ingestion
uv run python scripts/ingest_rag.py <file.docx> --replace
uv run python scripts/ingest_all_rag.py --replace

# Codebase ingestion (requires Repomix XML)
uv run python scripts/ingest_codebase_rag.py <repomix.xml> --replace

# Testing and analysis
uv run python scripts/test_rag_query.py "query text"
uv run python scripts/analizar_qualidade_rag.py
uv run python scripts/gerar_relatorio_rag.py
```

---

## Environment Configuration

Copy `.env.example` to `.env` and fill in the required values:

| Variable | Default | Required | Description |
|---|---|---|---|
| `BOTSALINHA_DISCORD__TOKEN` | — | **Yes** | Discord bot token |
| `BOTSALINHA_DISCORD__MESSAGE_CONTENT_INTENT` | `true` | No | Enable message content intent |
| `BOTSALINHA_GOOGLE__API_KEY` | — | **Yes** | Google Gemini API key |
| `BOTSALINHA_GOOGLE__MODEL_ID` | `gemini-2.5-flash-lite` | No | Gemini model to use |
| `BOTSALINHA_HISTORY__RUNS` | `3` | No | Conversation history pairs |
| `BOTSALINHA_RATE_LIMIT__REQUESTS` | `10` | No | Max requests per window |
| `BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS` | `60` | No | Rate limit time window |
| `BOTSALINHA_DATABASE__URL` | `sqlite:///data/botsalinha.db` | No | SQLite database path |
| `BOTSALINHA_LOG_LEVEL` | `INFO` | No | Log level |
| `BOTSALINHA_LOG_FORMAT` | `json` | No | `json` or `text` |

All env vars use the `BOTSALINHA_` prefix. Nested configs use double underscores (e.g., `BOTSALINHA_DISCORD__TOKEN`).

---

## Architecture

### Multi-Model AI Support

BotSalinha supports multiple AI providers via Agno framework. Provider selection is configured in `config.yaml`:

```yaml
model:
  provider: openai  # Options: openai (default), google
  id: gpt-4o-mini     # OpenAI: gpt-4o-mini, Google: gemini-2.5-flash-lite
```

Environment variables (`.env`):
- `BOTSALINHA_OPENAI__API_KEY` - Required for OpenAI provider
- `BOTSALINHA_GOOGLE__API_KEY` - Required for Google provider

The `AgentWrapper` (`src/core/agent.py`) dynamically instantiates the appropriate model class based on `config.yaml`.

### Layered Architecture

```
Discord Commands (BotSalinhaBot)
         ↓
Middleware (RateLimiter — token bucket per user/guild)
         ↓
Service Layer (AgentWrapper — Agno + Multi-model AI + RAG)
         ↓
RAG Layer (QueryService → EmbeddingService → VectorStore)
         ↓
Data Access Layer (Repository Pattern — abstract interfaces)
         ↓
Database Layer (SQLite default, Supabase optional)
```

### RAG (Retrieval-Augmented Generation)

BotSalinha implements a complete RAG pipeline in `src/rag/`:

**Components:**
- **Parsers** (`src/rag/parser/`): DOCX, XML (Repomix), code chunking
- **Services** (`src/rag/services/`): Query, Ingestion (documents + codebase), Embeddings (OpenAI)
- **Storage** (`src/rag/storage/`): Vector store with cosine similarity
- **Utils** (`src/rag/utils/`): Confidence calculator, metadata extraction, retrieval ranking

**Flow:**
1. Document ingestion → Chunking → Embedding → SQLite storage
2. Query → Embedding → Vector search → Context injection → AI response

**Confidence Levels:** `ALTA`, `MEDIA`, `BAIXA`, `SEM_RAG` (based on similarity scores)

### Key Design Patterns

- **Repository Pattern with Factory:** `src/storage/factory.py` provides `create_repository()` context manager that returns `SQLiteRepository` or `SupabaseRepository` based on settings. **Always use this pattern** for database access — never instantiate repositories directly.
- **Pydantic Settings:** `src/config/settings.py` uses `pydantic-settings` with `@lru_cache` for a singleton. Never call `Settings()` directly; use `get_settings()` or the `settings` instance.
- **YAML Config:** Agent and model settings live in `config.yaml`, parsed by `src/config/yaml_config.py` with Pydantic validation. The active prompt file is specified here (`prompt_v1.md` by default).
- **Async Throughout:** All I/O-bound operations use `async/await`. Never call blocking functions from async context.
- **Dependency Injection:** Use `create_repository()` factory for database access. The repository is injected into `AgentWrapper` and `BotSalinhaBot`.

---

## Code Conventions

### Naming

| Item | Convention | Example |
|---|---|---|
| Classes | PascalCase | `BotSalinhaBot`, `ConversationORM` |
| Functions/Methods | snake_case | `run_discord_bot`, `check_rate_limit` |
| Private members | `_underscore` prefix | `_ready_event`, `_initialized` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Async functions | `async def` | `async def generate_response()` |
| Type hints | Always present | `str | None` (not `Optional[str]`) |

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
@pytest.mark.gemini        # Requires Gemini API mock
@pytest.mark.database      # Requires database access
```

### Key Fixtures (from `tests/conftest.py`)

| Fixture | Description |
|---|---|
| `test_settings` | Pydantic settings configured for test environment |
| `test_engine` | Async SQLAlchemy engine (in-memory SQLite) |
| `test_session` | Scoped async database session |
| `test_repository` | In-memory `SQLiteRepository` instance |
| `rate_limiter` | `RateLimiter` instance |

### Testing Patterns

- Use in-memory SQLite (`sqlite+aiosqlite:///:memory:`) for database tests.
- Mock Discord API with `pytest-mock` — never make real Discord calls in tests.
- Mock Gemini/Google API — never make real API calls in tests.
- Use `faker` with `pt_BR` locale for realistic Brazilian test data.
- Use `freezegun` for time-dependent tests.

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/test.yml`) runs on push to `main`/`develop` and on pull requests:

| Job | What it does |
|---|---|
| **Lint** | `ruff check`, `ruff format --check`, `mypy src/` |
| **Unit Tests** | `pytest tests/unit` with coverage upload |
| **Integration Tests** | `pytest tests/integration` |
| **E2E Tests** | `pytest tests/e2e` (needs Discord/Gemini secrets) |
| **All Tests** | Full parallel run, enforces 70% coverage threshold |

---

## Prompt Management

System prompts live in `prompt/`. The active prompt is configured in `config.yaml`:

| File | Style | Status |
|---|---|---|
| `prompt_v1.md` | Simple, direct | **Active (default)** |
| `prompt_v2.json` | Few-shot with examples | Available |
| `prompt_v3.md` | Advanced chain-of-thought | Available |

To switch prompts, update `config.yaml` → `prompt.file`.

---

## Discord Bot Commands

| Command | Description |
|---|---|
| `!ask <question>` | Ask the AI a question about Brazilian law or contests |
| `!ping` | Health check |
| `!ajuda` | Show help message |
| `!info` | Show bot information |
| `!limpar` | Clear conversation history for the user |

---

## Important Files to Know

| File | Why it matters |
|---|---|
| `src/config/settings.py` | All configuration with defaults and validation (Pydantic Settings singleton) |
| `src/config/yaml_config.py` | Agent/model configuration (provider selection, prompt file, parameters) |
| `src/core/agent.py` | AI response generation with RAG integration and multi-model support |
| `src/core/discord.py` | All bot commands and Discord event handlers |
| `src/rag/` | Complete RAG implementation (parsers, services, storage, utils) |
| `src/storage/factory.py` | Repository factory for DI pattern — **use this for database access** |
| `src/storage/repository.py` | Abstract repository interfaces |
| `src/storage/sqlite_repository.py` | SQLite implementation (default database) |
| `src/utils/errors.py` | Exception hierarchy — use these, don't use bare exceptions |
| `config.yaml` | Model provider selection (openai/google), prompt file, agent behavior |
| `.env.example` | Canonical list of all supported environment variables |
| `docs/architecture.md` | Comprehensive system architecture documentation |
| `docs/CODE_DOCUMENTATION.md` | Detailed module-by-module technical documentation |
