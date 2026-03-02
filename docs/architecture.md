# Architecture - BotSalinha

This document describes the system architecture of BotSalinha, a Discord bot specialized in Brazilian law and public contest preparation.

**Last Updated:** 2026-03-01

---

## 1. Project Structure

BotSalinha follows a layered architecture with clear separation of concerns. The codebase is organized into functional modules that each handle a specific aspect of the application.

### 1.1 Root Directory Layout

```
BotSalinha/
├── bot.py                        # Entry point wrapper
├── pyproject.toml                # Project metadata and dependencies (uv)
├── config.yaml                   # Agent/model YAML configuration
├── docker-compose.yml            # Development Docker setup
├── docker-compose.prod.yml       # Production Docker setup
├── Dockerfile                    # Multi-stage Docker build
├── pytest.ini                    # Pytest configuration
├── mypy.ini                      # MyPy strict type checking
├── ruff.toml                     # Ruff linter/formatter (100-char lines)
├── .env.example                  # Environment variables template
├── .pre-commit-config.yaml       # Pre-commit hooks
│
├── src/                          # Main application source
├── tests/                        # Test suite (unit/integration/e2e)
├── migrations/                   # Alembic database migrations
├── scripts/                      # Utility scripts (backup, tests)
├── prompt/                       # System prompts (v1, v2, v3, v4_rag_first)
├── docs/                         # Documentation
├── .github/workflows/            # CI/CD pipelines
│
├── PRD.md                        # Product Requirements Document
├── CLAUDE.md                     # Developer guide (comprehensive)
├── AGENTS.md                     # Legacy agent conventions
└── README.md                     # Main documentation (Portuguese)
```

### 1.2 Source Code Organization (`src/`)

```
src/
├── main.py                       # CLI argument parsing and entry points
├── facade.py                     # Facade for external integrations
│
├── config/                       # Configuration layer
│   ├── settings.py               # Pydantic Settings (BOTSALINHA_* prefix)
│   ├── yaml_config.py            # YAML config loader with validation
│   ├── convex_config.py          # Convex backend configuration
│   └── mcp_config.py             # MCP tools configuration
│
├── core/                         # Core business logic
│   ├── agent.py                  # AgentWrapper — Agno + Gemini/OpenAI
│   ├── discord.py                # BotSalinhaBot — Discord commands/events
│   ├── lifecycle.py              # Startup/shutdown lifecycle
│   └── cli.py                    # CLI chat mode
│
├── models/                       # Data models
│   ├── conversation.py           # ConversationORM + Pydantic schemas
│   ├── message.py                # MessageORM + Pydantic schemas
│   └── rag_models.py             # RAG DocumentORM + ChunkORM
│
├── storage/                      # Data access layer
│   ├── repository.py             # Abstract repository interfaces
│   ├── sqlite_repository.py      # SQLite implementation (SQLAlchemy)
│   ├── convex_repository.py      # Convex cloud implementation
│   ├── supabase_repository.py    # Supabase implementation
│   ├── factory.py                # Repository factory
│   └── repository_factory.py     # Configured repository selector
│
├── middleware/                   # Cross-cutting concerns
│   └── rate_limiter.py           # Token bucket rate limiter
│
├── services/                     # Business services
│   └── conversation_service.py   # Conversation orchestration
│
├── rag/                          # Retrieval-Augmented Generation
│   ├── models.py                 # RAG data models
│   ├── config.py                 # RAG configuration
│   ├── parser/                   # Document parsers
│   │   ├── chunker.py            # Text chunking strategies
│   │   ├── code_chunker.py       # Python code chunking
│   │   ├── xml_parser.py         # XML parsing
│   │   └── docx_parser.py        # DOCX parsing
│   ├── services/                 # RAG services
│   │   ├── ingestion_service.py  # Document ingestion
│   │   ├── code_ingestion_service.py  # Codebase ingestion
│   │   ├── query_service.py      # RAG query/retrieval
│   │   ├── embedding_service.py  # Embedding generation
│   │   └── cached_embedding_service.py  # Cached embeddings
│   ├── storage/                  # RAG storage
│   │   ├── rag_repository.py     # RAG data access
│   │   └── vector_store.py       # Vector similarity search
│   └── utils/                    # RAG utilities
│       ├── confianca_calculator.py  # Confidence scoring
│       ├── metadata_extractor.py  # Document metadata
│       ├── code_metadata_extractor.py  # Code metadata
│       ├── normalizer.py         # Text normalization
│       └── retrieval_ranker.py   # Result ranking
│
├── tools/                        # External tools integration
│   └── mcp_manager.py            # MCP tools manager
│
└── utils/                        # Utilities
    ├── logger.py                 # structlog setup
    ├── errors.py                 # Custom exception hierarchy
    ├── retry.py                  # async_retry decorator
    ├── input_sanitizer.py        # Input sanitization
    ├── log_events.py             # Log event constants
    ├── log_correlation.py        # Request correlation
    ├── log_sanitization.py       # Sensitive data redaction
    ├── log_rotation.py           # Log rotation
    ├── message_splitter.py       # Discord message splitting
    └── ui_errors.py              # User-facing error messages
```

### 1.3 Test Organization (`tests/`)

```
tests/
├── conftest.py                   # Shared fixtures (DB, settings, mocks)
├── unit/                         # Isolated component tests
│   ├── test_*.py                 # Per-module unit tests
│   └── rag/                      # RAG-specific unit tests
├── integration/                  # Multi-component tests
│   └── rag/                      # RAG integration tests
├── e2e/                          # Full system workflow tests
└── fixtures/                     # Test helpers and factories
```

### 1.4 Migrations (`migrations/`)

```
migrations/
├── alembic.ini                   # Alembic configuration
├── env.py                        # Migration environment
└── versions/                     # Migration scripts (YYYYMMDD_HHMM_description.py)
```

### 1.5 Layer Summary

| Layer | Directory | Purpose |
|-------|-----------|---------|
| **Presentation** | `src/core/discord.py` | Discord bot commands/events |
| **Service** | `src/services/`, `src/core/agent.py` | Business logic orchestration |
| **Data Access** | `src/storage/` | Repository pattern implementations |
| **Models** | `src/models/` | ORM models + Pydantic schemas |
| **Middleware** | `src/middleware/` | Rate limiting |
| **Utilities** | `src/utils/` | Logging, errors, retry |
| **RAG** | `src/rag/` | Retrieval-Augmented Generation |

---

## 2. High-Level System Diagram

BotSalinha follows a **layered architecture** with clear boundaries between layers. Requests flow from Discord through middleware to services, then to repositories and external APIs.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Discord Platform                                │
│                    User sends `!ask <pergunta>` in a channel                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Presentation Layer                                 │
│                         BotSalinhaBot (discord.py)                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  • on_message()        - Route incoming messages                     │   │
│  │  • ask_command()       - Handle !ask command                         │   │
│  │  • ping_command()      - Health check                                │   │
│  │  • ajuda_command()     - Show help                                   │   │
│  │  • limpar_command()    - Clear conversation history                  │   │
│  │  • info_command()      - Bot information                             │   │
│  │  • on_command_error()  - Global error handler                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Middleware Layer                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  RateLimiter (token bucket per-user/per-guild)                       │   │
│  │  • check_rate_limit()    - Enforce rate limits                       │   │
│  │  • TokenBucket           - Capacity + refill rate                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Service Layer                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  ConversationService                                                    │   │
│  │  • get_or_create_conversation() - Auto-create conversation context   │   │
│  │  • process_question()          - Orchestrate Q&A flow                │   │
│  │  • clear_conversation()         - Delete user history                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                        │
│                                      ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  AgentWrapper (Agno + Gemini/OpenAI)                                  │   │
│  │  • generate_response()        - Main AI response generation          │   │
│  │  • generate_response_with_rag() - RAG-enhanced generation            │   │
│  │  • _build_prompt()            - Assemble context + RAG               │   │
│  │  • save_message()             - Persist messages                     │   │
│  │  • run_cli()                  - Interactive CLI mode                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                                         │
                    ▼                                         ▼
┌───────────────────────────────┐           ┌──────────────────────────────────┐
│    Data Access Layer          │           │      External APIs               │
│  (Repository Pattern)          │           │                                  │
│  ┌─────────────────────────┐   │           │  ┌────────────────────────────┐ │
│  │ ConversationRepository   │   │           │  │ Google Gemini API          │ │
│  │ MessageRepository        │   │           │  │ • gemini-2.5-flash-lite    │ │
│  └─────────────────────────┘   │           │  │ • OpenAI models (alt)      │ │
│           │                     │           │  └────────────────────────────┘ │
│           ▼                     │           │                                  │
│  ┌─────────────────────────┐   │           │  ┌────────────────────────────┐ │
│  │ SQLiteRepository        │   │           │  │ Embedding Service          │ │
│  │ ConvexRepository        │   │           │  │ • text-embedding-004      │ │
│  │ SupabaseRepository      │   │           │  └────────────────────────────┘ │
│  └─────────────────────────┘   │           │                                  │
│           │                     │           └──────────────────────────────────┘
│           ▼                     │
│  ┌─────────────────────────┐   │           ┌──────────────────────────────────┐
│  │ SQLAlchemy Async ORM    │   │           │      RAG Pipeline (Optional)     │
│  └─────────────────────────┘   │           │  ┌────────────────────────────┐ │
└───────────────────────────────┘           │  │ QueryService               │ │
                                           │  │ • query()                  │ │
                                           │  │ • should_augment_prompt()  │ │
                                           │  └────────────────────────────┘ │
                                           │                │                   │
                                           │                ▼                   │
                                           │  ┌────────────────────────────┐ │
                                           │  │ VectorStore                │ │
                                           │  │ • similarity_search()      │ │
                                           │  └────────────────────────────┘ │
                                           │                │                   │
                                           │                ▼                   │
                                           │  ┌────────────────────────────┐ │
                                           │  │ EmbeddingService           │ │
                                           │  │ • generate_embedding()     │ │
                                           │  └────────────────────────────┘ │
                                           └──────────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Stores                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  SQLite Database (default) or Convex Cloud (optional)                │   │
│  │  Tables:                                                              │   │
│  │  • conversations  - User conversation contexts                        │   │
│  │  • messages       - Message history (user/assistant/system)           │   │
│  │  • rag_documents  - Ingested documents for RAG                        │   │
│  │  • rag_chunks     - Text chunks with embeddings                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           Cross-Cutting Concerns                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  structlog (JSON/text logging)                                        │   │
│  │  • bind_request_context()   - Correlation IDs                         │   │
│  │  • log_events.py            - Event constants                         │   │
│  │  • log_sanitization.py      - PII redaction                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Error Handling                                                        │   │
│  │  • BotSalinhaError            - Base exception                        │   │
│  │  • APIError, RateLimitError    - Specific errors                      │   │
│  │  • async_retry                - Exponential backoff                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Request Flow Example

**User asks:** `!ask Qual é o prazo para recurso administrativo?`

1. **Discord** → `BotSalinhaBot.on_message()` receives the message
2. **Presentation** → `ask_command()` extracts the question text
3. **Middleware** → `RateLimiter.check_rate_limit()` verifies user hasn't exceeded limits
4. **Service** → `ConversationService.get_or_create_conversation()` gets/creates context
5. **Service** → `ConversationService.process_question()` orchestrates the flow:
   - `AgentWrapper.generate_response_with_rag()`:
     - Loads conversation history from `MessageRepository`
     - **RAG path (if enabled):**
       - `QueryService.query()` searches `rag_chunks` via `VectorStore`
       - `EmbeddingService.generate_embedding()` creates query vector
       - Returns relevant chunks with confidence scores
     - `AgentWrapper._build_prompt()` combines: history + RAG context + user question
     - `Agent.arun()` calls **Gemini API** with the full prompt
     - Returns AI response text
   - Saves user message + AI response via `MessageRepository`
6. **Presentation** → Splits response if >2000 chars (Discord limit) via `MessageSplitter`
7. **Discord** → Bot sends response chunks to the channel
8. **Logging** → All steps logged with structlog (correlation ID, user/guild IDs)

---

## 3. Core Components

### 3.1 BotSalinhaBot (`src/core/discord.py`)

The main Discord bot class built on `discord.py`. Implements all bot commands and event handlers.

**Key Responsibilities:**
- Discord command registration (`!ask`, `!ping`, `!ajuda`, `!limpar`, `!info`)
- Rate limiting per-user/per-guild via `@commands.cooldown` decorator
- Error handling with user-friendly messages
- Message splitting for Discord's 2000-character limit
- Integration with `ConversationService` for business logic

**Key Methods:**
```python
async def setup_hook() -> None
    # Initialize database (SQLite) or skip (Convex)

async def on_ready() -> None
    # Log bot connection status, guild/user counts

async def on_message(message: discord.Message) -> None
    # Route incoming messages, bind request context for logging

async def ask_command(ctx: commands.Context, question: str) -> None
    # Main Q&A command, delegates to ConversationService

async def on_command_error(ctx: commands.Context, error: Exception) -> None
    # Global error handler, maps exceptions to user messages
```

**Design Decisions:**
- Uses `commands.Bot` with custom prefix (`!` by default)
- Intents: `default() + message_content + guilds + dm_messages`
- No help command (custom `!ajuda` implementation)
- Cooldown: 1 request per 60 seconds per user (Discord-native)

---

### 3.2 AgentWrapper (`src/core/agent.py`)

Wraps the [Agno](https://github.com/agno-agi/agno) Agent class with conversation history management and RAG integration.

**Key Responsibilities:**
- AI response generation via Agno + Gemini/OpenAI
- Conversation history loading from repository
- RAG query augmentation (optional, when enabled)
- Prompt assembly (history + RAG context + user message)
- Message persistence (user + assistant)
- CLI chat mode (`run_cli()`)

**Key Methods:**
```python
async def generate_response(
    prompt: str,
    conversation_id: str,
    user_id: str,
    guild_id: str | None = None
) -> str
    # Generate AI response with conversation history

async def generate_response_with_rag(
    prompt: str,
    conversation_id: str,
    user_id: str,
    guild_id: str | None = None
) -> tuple[str, RAGContext | None]
    # Generate AI response with RAG context, returns (response, rag_context)

async def _generate_with_retry(
    prompt: str,
    history: list[dict[str, Any]],
    rag_context: RAGContext | None = None
) -> str
    # Internal generation with exponential backoff retry

def _build_prompt(
    user_prompt: str,
    history: list[dict[str, Any]],
    rag_context: RAGContext | None = None
) -> str
    # Assemble full prompt: history + RAG block + user message

def _build_rag_augmentation(rag_context: RAGContext) -> str
    # Format RAG chunks as structured text block for LLM

async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    discord_message_id: str | None = None
) -> None
    # Persist message to repository

async def run_cli(session_id: str = "cli_session") -> None
    # Interactive CLI chat mode using Agno's acli_app
```

**RAG Integration:**
- When `enable_rag=True` and db_session provided:
  - Initializes `QueryService` with `EmbeddingService`
  - Calls `query_service.query()` before generation
  - Augments prompt with retrieved chunks if `should_augment_prompt()` returns true
  - Injects confidence level instructions (alta/média/baixa/sem_rag)
- Falls back to normal generation if RAG search fails

**Model Selection:**
- Supports `google` (Gemini) and `openai` (GPT) providers
- Configured via `config.yaml`:
  ```yaml
  model:
    provider: google  # or openai
    model_id: gemini-2.5-flash-lite
    temperature: 0.7
  ```

---

### 3.3 Repositories (`src/storage/`)

BotSalinha uses the **Repository Pattern** with abstract interfaces in `repository.py` and multiple implementations.

#### Abstract Interfaces (`repository.py`)

```python
class ConversationRepository(ABC):
    async def create_conversation(conversation: ConversationCreate) -> Conversation
    async def get_conversation_by_id(conversation_id: str) -> Conversation | None
    async def get_by_user_and_guild(user_id: str, guild_id: str | None) -> list[Conversation]
    async def get_or_create_conversation(user_id: str, guild_id: str | None, channel_id: str) -> Conversation
    async def update_conversation(conversation_id: str, updates: ConversationUpdate) -> Conversation | None
    async def delete_conversation(conversation_id: str) -> bool
    async def cleanup_old_conversations(days: int = 30) -> int

class MessageRepository(ABC):
    async def create_message(message: MessageCreate) -> Message
    async def get_message_by_id(message_id: str) -> Message | None
    async def get_conversation_messages(conversation_id: str, limit: int | None = None, role: MessageRole | None = None) -> list[Message]
    async def get_conversation_history(conversation_id: str, max_runs: int = 3) -> list[dict[str, Any]]
    async def update_message(message_id: str, updates: MessageUpdate) -> Message | None
    async def delete_message(message_id: str) -> bool
    async def delete_conversation_messages(conversation_id: str) -> int
```

#### SQLite Implementation (`sqlite_repository.py`)

**Default backend.** Uses SQLAlchemy async ORM with aiosqlite driver.

**Key Features:**
- Async session management with `sessionmaker`
- WAL mode enabled for better concurrency
- Connection pooling optimization
- `get_or_create_conversation()` for automatic conversation creation
- `get_conversation_history()` formats messages for LLM context (returns last N user/assistant pairs)

**Configuration:**
```python
# settings.py
database_url = "sqlite:///data/botsalinha.db"  # Converted to sqlite+aiosqlite:///
```

**Pragmas:**
```python
PRAGMA journal_mode=WAL      # Write-Ahead Logging
PRAGMA synchronous=NORMAL     # Balanced safety/performance
PRAGMA cache_size=-64000      # 64MB cache
PRAGMA temp_store=memory      # In-memory temp tables
```

#### Convex Implementation (`convex_repository.py`)

**Cloud backend (optional).** Uses Convex for serverless data storage.

**Trade-offs:**
- ✅ No database migration management
- ✅ Automatic scaling
- ❌ External dependency
- ❌ Network latency vs local SQLite

#### Repository Factory (`repository_factory.py`)

```python
def get_configured_repository() -> ConversationRepository | MessageRepository:
    """Return SQLite or Convex repository based on settings."""
```

---

### 3.4 Rate Limiter (`src/middleware/rate_limiter.py`)

Implements **token bucket algorithm** for per-user rate limiting.

**Key Classes:**

```python
@dataclass
class TokenBucket:
    capacity: int              # Maximum tokens
    refill_rate: float         # Tokens per second
    tokens: float              # Current tokens
    last_update: float         # Last refill timestamp

    def consume(self, tokens: int = 1) -> bool
        # Try to consume tokens, refill based on elapsed time

    @property
    def wait_time(self) -> float
        # Seconds until next token available

@dataclass
class UserBucket:
    bucket: TokenBucket
    limited_until: float       # Unix timestamp

    @property
    def is_rate_limited(self) -> bool

class RateLimiter:
    def __init__(
        requests: int | None = None,
        window_seconds: int | None = None,
        cleanup_interval: float = 300.0
    )

    async def check_rate_limit(
        user_id: int | str,
        guild_id: int | str | None = None
    ) -> None
        # Raises RateLimitError if exceeded

    def check_decorator() -> Callable
        # Decorator for Discord commands

    def reset_user(user_id: int | str, guild_id: int | str | None = None) -> None
    def reset_all() -> None
```

**Algorithm:**
- Each user/guild combination has a bucket
- Bucket refills at constant rate: `requests / window_seconds` tokens/sec
- Each request consumes 1 token
- If bucket empty, user is rate limited for `wait_time` seconds
- Automatic cleanup of stale entries every 5 minutes

**Configuration:**
```python
# settings.py (defaults)
rate_limit:
  requests: 10
  window_seconds: 60
```

**Discord Integration:**
- Uses `@commands.cooldown` decorator (Discord-native)
- Plus custom `RateLimiter` for additional control
- Composite key: `f"{user_id}:{guild_id or 'dm'}"`

---

## 4. Data Stores

BotSalinha supports multiple database backends. The default is SQLite (local file), with optional Convex (cloud) and Supabase (PostgreSQL) backends.

### 4.1 SQLite (Default)

**File:** `data/botsalinha.db` (configurable via `BOTSALINHA_DATABASE_URL`)

**Advantages:**
- Zero configuration, single-file database
- No external dependencies
- Fast for read-heavy workloads
- Suitable for Discord bot scale (thousands of users)

**Connection String:**
```bash
BOTSALINHA_DATABASE_URL=sqlite:///data/botsalinha.db
# Internally converted to: sqlite+aiosqlite:///data/botsalinha.db
```

**Optimizations:**
- WAL mode for concurrent reads/writes
- 64MB cache size
- In-memory temp tables

---

### 4.2 Database Schema

#### 4.2.1 `conversations` Table

Stores conversation contexts (one per user per channel).

```sql
CREATE TABLE conversations (
    id          VARCHAR(36) PRIMARY KEY,  -- UUID
    user_id     VARCHAR(255) NOT NULL,    -- Discord user ID
    guild_id    VARCHAR(255),              -- Discord guild ID (NULL for DMs)
    channel_id  VARCHAR(255) NOT NULL,    -- Discord channel ID
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data   TEXT                       -- JSON metadata
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_guild_id ON conversations(guild_id);
CREATE INDEX idx_conversations_channel_id ON conversations(channel_id);
```

**ORM Model:** `ConversationORM` in `src/models/conversation.py`

**Pydantic Schemas:**
- `ConversationCreate` - For creating new conversations
- `ConversationUpdate` - For updating metadata
- `Conversation` - Response schema (includes `message_count`)

---

#### 4.2.2 `messages` Table

Stores individual messages within conversations.

```sql
CREATE TABLE messages (
    id                  VARCHAR(36) PRIMARY KEY,  -- UUID
    conversation_id     VARCHAR(36) NOT NULL,    -- Foreign key to conversations
    role                VARCHAR(20) NOT NULL,     -- 'user' | 'assistant' | 'system'
    content             TEXT NOT NULL,            -- Message text
    discord_message_id  VARCHAR(255),             -- Discord message ID (if applicable)
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data           TEXT,                     -- JSON metadata
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_discord_message_id ON messages(discord_message_id);
```

**ORM Model:** `MessageORM` in `src/models/message.py` (created dynamically via `create_message_orm()`)

**Pydantic Schemas:**
- `MessageCreate` - For creating messages
- `MessageUpdate` - For updating content/metadata
- `Message` - Response schema

**Relationships:**
- Each message belongs to one conversation
- Cascading delete: deleting a conversation deletes all its messages

---

#### 4.2.3 `rag_documents` Table

Stores ingested documents for RAG functionality.

```sql
CREATE TABLE rag_documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          VARCHAR(255) NOT NULL,      -- Document name
    arquivo_origem VARCHAR(500) NOT NULL,     -- Source file path
    content_hash  VARCHAR(64) UNIQUE,         -- SHA-256 hash (for deduplication)
    chunk_count   INTEGER NOT NULL DEFAULT 0, -- Number of chunks
    token_count   INTEGER NOT NULL DEFAULT 0, -- Total tokens
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rag_documents_nome ON rag_documents(nome);
CREATE INDEX idx_rag_documents_content_hash ON rag_documents(content_hash);
```

**ORM Model:** `DocumentORM` in `src/models/rag_models.py`

**Purpose:** Track ingested documents, prevent duplicate ingestion via `content_hash`.

---

#### 4.2.4 `rag_chunks` Table

Stores text chunks with embeddings for semantic search.

```sql
CREATE TABLE rag_chunks (
    id            VARCHAR(255) PRIMARY KEY,    -- Chunk ID (typically UUID)
    documento_id  INTEGER NOT NULL,            -- Foreign key to rag_documents
    texto         TEXT NOT NULL,               -- Chunk text content
    metadados     TEXT NOT NULL,               -- JSON metadata (source, page, etc.)
    token_count   INTEGER NOT NULL,            -- Tokens in chunk
    embedding     BLOB,                        -- Serialized embedding (float32 array)
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (documento_id) REFERENCES rag_documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_rag_chunks_documento_id ON rag_chunks(documento_id);
```

**ORM Model:** `ChunkORM` in `src/models/rag_models.py`

**Purpose:**
- Store semantically meaningful chunks of text
- Enable vector similarity search via `VectorStore`
- Support RAG query augmentation

**Embedding Storage:**
- Stored as `BLOB` (serialized `numpy.ndarray` of `float32`)
- Generated by `EmbeddingService` (uses `text-embedding-004` model)
- Used by `VectorStore.similarity_search()` for retrieval

---

### 4.3 Entity Relationship Diagram (ERD)

```
┌──────────────────────┐
│   conversations      │
│ ─────────────────────│
│ id (PK)              │
│ user_id              │
│ guild_id             │
│ channel_id           │
│ created_at           │
│ updated_at           │
│ meta_data            │
└──────────────────────┘
          │ 1
          │
          │ N
┌──────────────────────┐
│      messages        │
│ ─────────────────────│
│ id (PK)              │
│ conversation_id (FK) │───┐
│ role                 │
│ content              │
│ discord_message_id   │
│ created_at           │
│ meta_data            │
└──────────────────────┘

┌──────────────────────┐       ┌──────────────────────┐
│   rag_documents      │ 1   N │     rag_chunks       │
│ ─────────────────────│───────│──────────────────────│
│ id (PK)              │       │ id (PK)              │
│ nome                 │       │ documento_id (FK)    │
│ arquivo_origem       │       │ texto                │
│ content_hash         │       │ metadados            │
│ chunk_count          │       │ token_count          │
│ token_count          │       │ embedding (BLOB)     │
│ created_at           │       │ created_at           │
└──────────────────────┘       └──────────────────────┘
```

---

### 4.4 Alternative Backends

#### Convex Cloud (`convex_repository.py`)

**Configuration:**
```bash
BOTSALINHA_CONVEX__DEPLOYMENT_URL=https://your-convex-app.convex.cloud
BOTSALINHA_CONVEX__ADMIN_KEY=your_admin_key
```

**Features:**
- Serverless, auto-scaling
- No migrations needed
- Real-time subscriptions (future potential)

---

#### Supabase PostgreSQL (`supabase_repository.py`)

**Configuration:**
```bash
BOTSALINHA_SUPABASE__URL=https://your-project.supabase.co
BOTSALINHA_SUPABASE__KEY=your_anon_key
```

**Features:**
- PostgreSQL database with full SQL capabilities
- Built-in authentication and real-time features
- Suitable for production deployments

---

### 4.5 Database Migration Management

**Tool:** [Alembic](https://alembic.sqlalchemy.org/)

**Workflow:**

```bash
# After modifying ORM models
uv run alembic revision --autogenerate -m "description"

# Review generated migration script in migrations/versions/

# Apply migrations
uv run alembic upgrade head

# Revert last migration
uv run alembic downgrade -1
```

**Migration Scripts Location:**
- `migrations/versions/YYYYMMDD_HHMM_description.py`

**Example:**
```python
# migrations/versions/20260301_1200_add_content_hash_to_rag_documents.py
"""add content_hash to rag_documents

Revision ID: 001
Revises:
Create Date: 2026-03-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('rag_documents', sa.Column('content_hash', sa.String(64), nullable=True))
    op.create_index('idx_rag_documents_content_hash', 'rag_documents', ['content_hash'], unique=True)

def downgrade():
    op.drop_index('idx_rag_documents_content_hash', 'rag_documents')
    op.drop_column('rag_documents', 'content_hash')
```

---

## 9. Future Considerations / Roadmap

This section outlines planned features and enhancements for the BotSalinha project.

### 9.1 Implemented Features

- **RAG para Código (Codebase RAG):** Fully implemented retrieval-augmented generation for code documentation
  - `CodeIngestionService` ingests Python codebase with AST-based chunking
  - `CodeMetadataExtractor` captures symbols, docstrings, and dependencies
  - Hybrid search (semantic + keyword) via `RetrievalRanker`
  - Confidence scoring system with threshold-based augmentation
  - See `src/rag/` for complete implementation

### 9.2 Planned Enhancements

#### Multi-Model Support
- **Current:** Google Gemini 2.5 Flash Lite (primary), OpenAI models (alternative)
- **Planned:**
  - Anthropic Claude API integration
  - Local model support via Ollama or LM Studio
  - Model routing based on query complexity
  - Fallback chains for reliability

#### Multi-Language Support
- **Current:** Portuguese (Brazilian law focus)
- **Planned:**
  - English language toggle
  - Spanish language support (for broader Latin American legal context)
  - Locale-aware prompts in `prompt/` directory
  - Automatic language detection from user queries

#### Enhanced RAG Capabilities
- **Hybrid Search Optimization:**
  - Learned embeddings (ColBERT, SPLADE)
  - Query expansion with LLM-generated synonyms
  - Re-ranking with cross-encoders
- **Multi-Modal RAG:**
  - Image ingestion (diagrams, flowcharts)
  - PDF table extraction
  - Audio/video transcription integration
- **Knowledge Graph:**
  - Entity extraction from legal documents
  - Relationship mapping between concepts
  - Graph-based reasoning for complex queries

#### Conversation Features
- **Thread Support:** Discord thread-based conversations for better context isolation
- **Conversation Export:** Allow users to export conversation history (PDF/Markdown)
- **Mention Notifications:** Notify users when referenced in conversations
- **Analytics Dashboard:** Admin panel for usage statistics and popular queries

#### Infrastructure Improvements
- **Horizontal Scaling:** Support for multiple bot instances with shared state
- **Message Queue:** Redis/Celery for async task processing
- **Caching Layer:** Redis for frequent queries and embeddings
- **Observability:** OpenTelemetry integration for distributed tracing
- **Testing:** Increase coverage to 80%+ with more E2E scenarios

### 9.3 Technology Radar

**Adopt:**
- uv (package manager) - ✅ Already adopted
- Agno framework - ✅ Already adopted
- SQLAlchemy async ORM - ✅ Already adopted

**Trial:**
- Qdrant/Milvus for vector storage (alternative to current implementation)
- LangChain for LLM orchestration (potential replacement/addition to Agno)
- FastAPI for REST API endpoints

**Assess:**
- Kafka/RabbitMQ for event streaming
- PostgreSQL as primary database (migration from SQLite)
- Kubernetes for container orchestration

**Hold:**
- Discord.py alternatives (discord.py remains stable and well-maintained)

---

## 10. Project Identification

| Field | Value |
|-------|-------|
| **Project Name** | BotSalinha |
| **Description** | Discord bot specialized in Brazilian law and public contest preparation (concursos públicos) |
| **Repository URL** | https://github.com/prof-ramos/BotSalinha |
| **Primary Contact** | gabrielramos (prof-ramos) |
| **Documentation Date** | 2026-03-02 |
| **Last Updated** | 2026-03-02 |
| **Version** | 1.0.0 |
| **License** | MIT (verify in LICENSE file) |
| **Language** | Python 3.12+ |
| **Framework** | discord.py + Agno AI Framework |
| **AI Backend** | Google Gemini 2.5 Flash Lite |
| **Database** | SQLite (default), Convex/Supabase (optional) |
| **Deployment** | Docker (multi-stage build) |

---

## 11. Glossary / Acronyms

### Acronyms

| Acronym | Full Name | Definition |
|---------|-----------|------------|
| **RAG** | Retrieval-Augmented Generation | AI technique that enhances LLM responses by retrieving relevant context from a knowledge base before generation |
| **ORM** | Object-Relational Mapping | Technique for converting data between incompatible type systems (Python objects ↔ SQL tables) using SQLAlchemy |
| **AST** | Abstract Syntax Tree | Tree representation of code structure used by `CodeChunker` for intelligent code splitting |
| **WAL** | Write-Ahead Logging | SQLite journal mode for better concurrent read/write performance |
| **API** | Application Programming Interface | Set of protocols for building and integrating application software |
| **CRUD** | Create, Read, Update, Delete | Basic operations for data persistence in repositories |
| **DTO** | Data Transfer Object | Pydantic schemas for structured data validation (`ConversationCreate`, `Message`, etc.) |
| **LLM** | Large Language Model | AI model (Gemini, GPT) that generates human-like text |
| **CLI** | Command Line Interface | Interactive terminal mode via `bot.py --chat` |
| **ERD** | Entity Relationship Diagram | Visual representation of database tables and relationships |

### Technical Terms

| Term | Definition |
|------|------------|
| **Agno** | AI agent framework (https://github.com/agno-agi/agno) used for LLM orchestration, prompt management, and tool integration |
| **discord.py** | Python library for building Discord bots with async/await support |
| **Pydantic** | Data validation library using Python type annotations, used for settings and schemas |
| **SQLAlchemy** | Python SQL toolkit and ORM, providing async session management |
| **Alembic** | Database migration tool for SQLAlchemy, handles schema versioning |
| **structlog** | Structured logging library for Python with JSON/text output |
| **Token Bucket** | Rate limiting algorithm that refills tokens at a constant rate; each request consumes tokens |
| **Vector Embedding** | Numerical representation of text capturing semantic meaning, used for similarity search |
| **Cosine Similarity** | Metric for measuring vector similarity, used in `VectorStore` for RAG retrieval |
| **Confidence Score** | Value (0-1) indicating RAG result quality; determines if augmentation should be applied |
| **Chunking** | Process of splitting large documents into smaller, semantically meaningful pieces |
| **Hybrid Search** | Combination of semantic search (embeddings) and keyword search (BM25) for better retrieval |
| **Re-ranking** | Post-processing step to reorder search results by relevance using cross-encoders |
| **Content Hash** | SHA-256 hash of document content used for deduplication in RAG ingestion |
| **Correlation ID** | Unique identifier attached to logs for tracing requests across async operations |

### Domain-Specific Terms

| Term | Definition |
|------|------------|
| **Concursos Públicos** | Brazilian public civil service examinations for government positions |
| **Lei Seca** | Brazilian federal traffic law (Lei 12.760/2012) regarding zero-tolerance for drunk driving |
| **Discord Intent** | Permission system defining which events a bot can subscribe to (`message_content`, `guilds`, etc.) |
| **Discord Guild** | Discord server/community where the bot operates |
| **Rate Limiting** | Mechanism to prevent API abuse by limiting request frequency per user |
| **Message Content Intent** | Discord permission required to read message content (deprecated but still needed) |

### BotSalinha-Specific Terms

| Term | Definition |
|------|------------|
| **BotSalinhaBot** | Main Discord bot class in `src/core/discord.py` |
| **AgentWrapper** | Wrapper around Agno Agent in `src/core/agent.py` for response generation |
| **ConversationService** | Orchestrator for Q&A flow in `src/services/conversation_service.py` |
| **RateLimiter** | Token bucket rate limiter in `src/middleware/rate_limiter.py` |
| **SQLiteRepository** | Default repository implementation in `src/storage/sqlite_repository.py` |
| **QueryService** | RAG query service in `src/rag/services/query_service.py` |
| **EmbeddingService** | Google embedding generation in `src/rag/services/embedding_service.py` |
| **VectorStore** | Semantic similarity search in `src/rag/storage/vector_store.py` |
| **CodeIngestionService** | Codebase RAG ingestion in `src/rag/services/code_ingestion_service.py` |
| **ConfiancaCalculator** | Confidence scoring in `src/rag/utils/confianca_calculator.py` |

---

**END OF ARCHITECTURE DOCUMENTATION**
