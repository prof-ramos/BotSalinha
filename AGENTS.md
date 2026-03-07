<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-03-06 | Updated: 2025-03-06 -->

# BotSalinha

## Purpose
Brazilian legal assistant Discord bot specializing in law and public contests (concursos públicos). Features multi-model AI support (OpenAI/Gemini), RAG (Retrieval-Augmented Generation) for legal documents and codebase, persistent conversation history, rate limiting, and comprehensive metrics/evaluation system.

## Key Files

| File | Description |
|------|-------------|
| `bot.py` | Minimal entry-point wrapper for CLI execution |
| `src/main.py` | Main entry point with Discord/CLI mode selection |
| `src/facade.py` | Simplified BotSalinha facade API for common operations |
| `src/core/agent.py` | Agno AgentWrapper - AI response generation with RAG |
| `src/core/discord.py` | BotSalinhaBot - Discord commands and event handlers |
| `src/core/lifecycle.py` | Startup/shutdown lifecycle and signal handling |
| `src/config/settings.py` | Pydantic Settings (env vars with BOTSALINHA_ prefix) |
| `src/config/yaml_config.py` | YAML config loader with Pydantic validation |
| `src/storage/factory.py` | Repository factory for dependency injection |
| `src/storage/repository.py` | Abstract repository interfaces |
| `src/storage/sqlite_repository.py` | SQLite implementation with async SQLAlchemy |
| `src/services/conversation_service.py` | Conversation and message processing logic |
| `src/middleware/rate_limiter.py` | Token bucket rate limiter (per-user/per-guild) |
| `src/utils/logger.py` | Structlog setup (JSON or text format) |
| `src/utils/errors.py` | Custom exception hierarchy (BotSalinhaError) |
| `src/utils/retry.py` | Async retry decorator with exponential backoff |
| `config.yaml` | Model provider selection, prompt file, agent behavior |
| `pyproject.toml` | Project metadata, dependencies, and tool configurations |
| `docker-compose.yml` | Development Docker orchestration |
| `docker-compose.prod.yml` | Production Docker orchestration |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | Main application source code (see `src/AGENTS.md`) |
| `src/config/` | Configuration management (settings, YAML, MCP, Convex) |
| `src/core/` | Core bot logic (agent, Discord bot, CLI, lifecycle) |
| `src/models/` | SQLAlchemy ORM models and Pydantic schemas |
| `src/storage/` | Database repositories and operations |
| `src/rag/` | RAG implementation (parsers, services, storage, utils) |
| `src/middleware/` | Request/response interceptors (rate limiting) |
| `src/services/` | Business logic services (conversation) |
| `src/tools/` | Integrations (MCP manager) |
| `src/utils/` | Shared utilities (logger, errors, retry, sanitization) |
| `src/metricas/` | Metrics CLI and HTML report generation |
| `tests/` | Test suite (unit, integration, e2e, fixtures) |
| `scripts/` | Utility scripts (backup, RAG ingestion, testing) |
| `docs/` | Comprehensive documentation (architecture, API, operations) |
| `prompt/` | System prompts (v1 simple, v2 few-shot, v3 chain-of-thought) |
| `migrations/` | Alembic database migrations |
| `metricas/` | RAG evaluation and metrics system (goldset, performance, quality) |
| `config/` | Configuration files (YAML examples) |
| `data/` | Runtime data (ChromaDB vector store) |
| `ingestion/` | Document ingestion pipelines |
| `examples/` | Usage examples |
| `plans/` | Planning documents and extraction scripts |

## For AI Agents

### Working In This Directory

**Primary Entry Points:**
- Use `src/facade.py` (BotSalinha class) for simplified programmatic access
- Use `src/main.py` for understanding CLI/Discord mode initialization
- Never instantiate repositories directly - use `src/storage/factory.py::create_repository()`
- Always use `get_settings()` from `src/config/settings.py` (singleton with @lru_cache)

**Key Architectural Patterns:**
1. **Repository Pattern with Factory**: `create_repository()` returns `SQLiteRepository` - always use this for DB access
2. **Pydantic Settings**: Settings singleton via `get_settings()` - never call `Settings()` directly
3. **YAML Config**: Agent/model settings in `config.yaml` parsed by `src/config/yaml_config.py`
4. **Facade Pattern**: `src/facade.py::BotSalinha` provides clean API hiding internal complexity
5. **Async Throughout**: All I/O operations use `async/await` - never call blocking functions from async context

**Configuration Hierarchy:**
1. Environment variables (`.env`) - `BOTSALINHA_*` prefix required
2. YAML config (`config.yaml`) - model provider, prompts, agent behavior
3. Pydantic Settings (`src/config/settings.py`) - validation and defaults

**Testing Requirements:**
- Run tests with `uv run pytest` (minimum 70% coverage enforced in CI)
- Use in-memory SQLite for database tests (`sqlite+aiosqlite:///:memory:`)
- Mock Discord API with `pytest-mock` - never make real Discord calls in tests
- Mock Gemini/Google API - never make real API calls in tests
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`

### Common Patterns

**Repository Access:**
```python
from src.storage.factory import create_repository

async with create_repository() as repo:
    conversation = await repo.get_conversation(user_id, guild_id, channel_id)
```

**Configuration Access:**
```python
from src.config.settings import settings
# OR
from src.config.settings import get_settings

settings = get_settings()
api_key = settings.google.api_key
```

**Error Handling:**
```python
from src.utils.errors import BotSalinhaError, APIError

try:
    await operation()
except SpecificError as e:
    log.error("operation_failed", error=str(e))
    raise APIError("Human-readable message", details={"key": "value"}) from e
```

**Logging:**
```python
import structlog
log = structlog.get_logger(__name__)

log.info("event_name", user_id=user_id, guild_id=guild_id)
```

**Async Retry:**
```python
from src.utils.retry import async_retry, AsyncRetryConfig

@async_retry(AsyncRetryConfig(max_attempts=3, base_delay=1.0))
async def call_external_api() -> str:
    ...
```

## Dependencies

### Internal
- `src/config/` - Configuration management (settings, YAML, MCP)
- `src/core/` - Bot logic and agent orchestration
- `src/models/` - ORM models and schemas
- `src/storage/` - Database access layer
- `src/rag/` - RAG pipeline (parsers, services, vector store)
- `src/middleware/` - Rate limiting
- `src/services/` - Business logic
- `src/utils/` - Shared utilities

### External
**Core Framework:**
- `agno>=2.5.5,<3.0.0` - AI agent orchestration framework
- `discord.py>=2.6.0,<3.0.0` - Discord API wrapper
- `python-dotenv>=1.0.1,<2.0.0` - Environment variable loading

**Configuration:**
- `pydantic>=2.10.0,<3.0.0` - Data validation and settings
- `pydantic-settings>=2.7.1,<3.0.0` - Settings management

**Database:**
- `sqlalchemy>=2.0.35,<2.1.0` - Async ORM
- `alembic>=1.14.0,<2.0.0` - Database migrations
- `aiosqlite>=0.22.1,<1.0.0` - Async SQLite driver
- `convex>=0.7.0,<1.0.0` - Cloud backend (optional)

**AI Providers:**
- `google-genai>=1.64.0,<2.0.0` - Google Gemini API
- `openai>=1.0.0,<2.0.0` - OpenAI API (multi-model support)

**RAG/Vector Store:**
- `chromadb>=0.6.0,<1.0.0` - Vector database with hybrid search
- `python-docx>=1.1.2,<2.0.0` - DOCX document parsing
- `numpy>=2.2.0,<3.0.0` - Numerical operations
- `tiktoken>=0.8.0,<0.9.0` - Token counting

**Logging & Monitoring:**
- `structlog>=24.4.0,<25.0.0` - Structured logging
- `click>=8.1.0` - CLI metrics
- `colorama>=0.4.6` - Terminal colors

**Utilities:**
- `pyyaml>=6.0.2,<7.0.0` - YAML parsing
- `aiofiles>=24.1.0,<25.0.0` - Async file operations
- `cachetools>=7.0.1` - Caching utilities
- `typer>=0.24.1` - CLI framework
- `rich>=14.3.3` - Terminal formatting
- `questionary>=2.1.1` - Interactive prompts
- `tenacity>=9.0.0,<10.0.0` - Retry logic

**Development:**
- `pytest>=9.0.2` - Testing framework
- `pytest-asyncio>=0.25.0` - Async test support
- `pytest-cov>=6.0.0` - Coverage reporting
- `pytest-mock>=3.14.0` - Mocking support
- `pytest-xdist>=3.6.1` - Parallel test execution
- `faker>=25.1.0` - Test data generation
- `freezegun>=1.5.1` - Time mocking
- `ruff>=0.15.0` - Linter and formatter
- `mypy>=1.15.0` - Type checker
- `pre-commit>=4.1.0` - Pre-commit hooks

## Development Commands

```bash
# Install dependencies
uv sync

# Run Discord bot
uv run botsalinha

# Run CLI chat mode
uv run bot.py --chat

# Linting and formatting
uv run ruff check src/
uv run ruff format src/

# Type checking
uv run mypy src/

# Run tests
uv run pytest
uv run pytest tests/unit
uv run pytest --cov=src --cov-report=html

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1

# Backup
uv run python scripts/backup.py backup
uv run python scripts/backup.py list
uv run python scripts/backup.py restore --restore-from <file>

# RAG ingestion
uv run python scripts/ingest_rag.py <file.docx> --replace
uv run python scripts/ingest_codebase_rag.py <repomix.xml> --replace
uv run python scripts/ingest_all_rag.py --replace

# RAG testing
uv run python scripts/test_rag_query.py "query text"
uv run python scripts/analizar_qualidade_rag.py

# Metrics/evaluation
uv run metricas

# Docker
docker-compose up -d
docker-compose logs -f
docker-compose -f docker-compose.prod.yml up -d
```

## Performance Characteristics

**Semantic Cache (RAG):**
- Cache hit latency: ~1ms (11,583x speedup)
- Cache miss latency: ~16s
- TTL: 24 hours
- LRU eviction by memory (50MB default)

**Rate Limiting:**
- Token bucket algorithm (per-user/per-guild)
- Default: 10 requests per 60 seconds
- Configurable via environment variables

**Database:**
- SQLite with WAL mode enabled
- Async operations via aiosqlite
- Connection pooling via SQLAlchemy

## Discord Commands

| Command | Description |
|---------|-------------|
| `!ask <question>` | Ask AI about Brazilian law or contests |
| `!ping` | Health check |
| `!ajuda` | Show help message |
| `!info` | Show bot information |
| `!limpar` | Clear conversation history |

## Key Environment Variables

All variables use `BOTSALINHA_` prefix with double underscore nesting:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOTSALINHA_DISCORD__TOKEN` | Yes | - | Discord bot token |
| `BOTSALINHA_GOOGLE__API_KEY` | Yes* | - | Google Gemini API key (*or OpenAI) |
| `BOTSALINHA_OPENAI__API_KEY` | Yes* | - | OpenAI API key (*or Google) |
| `BOTSALINHA_DATABASE__URL` | No | `sqlite:///data/botsalinha.db` | Database path |
| `BOTSALINHA_HISTORY__RUNS` | No | `3` | Conversation history pairs |
| `BOTSALINHA_RATE_LIMIT__REQUESTS` | No | `10` | Max requests per window |
| `BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS` | No | `60` | Rate limit window |
| `BOTSALINHA_LOG_LEVEL` | No | `INFO` | Log level |
| `BOTSALINHA_LOG_FORMAT` | No | `json` | Log format (json/text) |

See `.env.example` for complete list.

## Documentation

- `README.md` - Project overview (Portuguese)
- `CLAUDE.md` - Comprehensive development guide
- `PRD.md` - Product Requirements Document
- `docs/architecture.md` - System architecture
- `docs/CODE_DOCUMENTATION.md` - Detailed technical documentation
- `docs/DEVELOPER_GUIDE.md` - Developer setup and workflows
- `docs/deployment.md` - Docker and deployment instructions
- `docs/operations.md` - Runtime operations manual
- `docs/features/rag.md` - RAG feature documentation
- `docs/api.md` - API reference

## Code Statistics

- **Total Python Lines:** ~17,000
- **Test Files:** 30+ across unit/integration/e2e
- **Documentation Files:** 25+ markdown files
- **Scripts:** 15+ utility scripts
- **Dependencies:** 45+ production, 15+ development

## Licensing

This project is licensed under the terms specified in the `LICENSE` file.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
