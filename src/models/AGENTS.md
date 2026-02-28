# AGENTS.md — src/models/ Database Models

```<parent="../../AGENTS.md">```

**Generated:** 2026-02-27
**Updated:** 2026-02-27
**Scope:** Database ORM models and Pydantic schemas for BotSalinha conversation storage

---

## Purpose

This directory contains all database models and data validation schemas for BotSalinha's conversation storage system. The models implement the repository pattern with abstract interfaces and concrete SQLite implementations using SQLAlchemy async ORM.

Key responsibilities:
- Store user conversations with the AI agent
- Manage message history with role tracking
- Provide data validation through Pydantic schemas
- Support async database operations throughout the application

---

## Key Files

| File | Description | Key Classes/Enums |
|------|-------------|------------------|
| `conversation.py` | Conversation ORM model and Pydantic schemas | `ConversationORM`, `ConversationCreate`, `ConversationUpdate` |
| `message.py` | Message ORM model and Pydantic schemas | `MessageORM`, `MessageCreate`, `MessageRole` enum |

---

## Database Models

### ConversationORM
**Location:** `conversation.py`

```python
class ConversationORM(Base):
    """Database model for storing conversation sessions."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    guild_id: Mapped[str] = mapped_column(String(255), index=True, nullable=True)
    channel_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    meta_data: Mapped[str | None] = mapped_column(Text, name="meta_data")
```

**Key Features:**
- Uses UUID string IDs with auto-generation
- Tracks conversation owner (`user_id`), server context (`guild_id`), and channel (`channel_id`)
- Automatic timestamp management with timezone-aware UTC
- Optional metadata field for JSON storage
- Indexes on frequently queried fields (user_id, guild_id, channel_id)
- No direct relationship defined - messages queried through repository

### MessageORM
**Location:** `message.py`

**Note:** MessageORM is defined dynamically to avoid circular imports. The actual class is created by `create_message_orm()` function.

```python
# From create_message_orm() function:
class MessageORM(Base):
    """Database model for storing individual messages."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    discord_message_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    meta_data: Mapped[str | None] = mapped_column(Text, name="meta_data")
```

**Key Features:**
- UUID string IDs with auto-generation
- Role-based message tracking (`user`, `assistant`, `system`)
- Content storage with full conversation context
- Optional Discord message ID reference for real Discord integration
- Automatic creation timestamp with timezone-aware UTC
- Cascading delete from conversations to messages
- Index on conversation_id and discord_message_id

### MessageRole Enum
**Location:** `message.py` (uses StrEnum for better type safety)

```python
class MessageRole(StrEnum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
```

**Purpose:** Standardizes message roles for conversation history tracking and AI prompt context. Uses Python 3.11+ `StrEnum` for better type safety.

---

## Pydantic Schemas

### Conversation Schemas
**Location:** `conversation.py`

#### ConversationBase
- Base schema with common fields
- Required: `user_id`, `channel_id`
- Optional: `guild_id`, `meta_data` (JSON string)

#### ConversationCreate
- Inherits from ConversationBase
- Used for creating new conversation records
- Auto-generates timestamps in ORM layer

#### ConversationUpdate
- Schema for partial conversation updates
- Optional field: `meta_data` only (other fields immutable)
- Allows partial updates without affecting timestamps

#### Conversation
- Complete conversation response schema
- Includes all fields plus `id`, `created_at`, `updated_at`, `message_count`
- Uses `from_attributes=True` for ORM conversion

#### ConversationWithMessages
- Conversation with embedded messages list
- Used when retrieving full conversation context

### Message Schemas
**Location:** `message.py`

#### MessageBase
- Base schema with common fields
- Required: `role`, `content`
- Optional: `meta_data` (JSON string)

#### MessageCreate
- Inherits from MessageBase
- Required additional field: `conversation_id`
- Optional: `discord_message_id`
- Used for creating new message records

#### MessageUpdate
- Schema for partial message updates
- Optional fields: `content`, `meta_data`
- Role and conversation_id are immutable

#### Message
- Complete message response schema
- Includes all fields plus `id`, `conversation_id`, `created_at`
- Optional `conversation` reference

#### MessageWithConversation
- Message with embedded conversation object
- Used when retrieving full message context

---

## Design Patterns

### Repository Pattern Implementation
- **Abstract interfaces:** Defined in `src/storage/repository.py`
- **Concrete implementation:** `SQLiteRepository` in `src/storage/sqlite_repository.py`
- **Dependency injection:** Repository instance injected at startup
- **Dynamic ORM creation:** MessageORM created dynamically to avoid circular imports

### SQLAlchemy Async Patterns
- All operations use `async/await`
- Async engine and session management
- Automatic connection handling through async context managers
- In-memory SQLite for testing (`sqlite+aiosqlite:///:memory:`)
- UUID-based string IDs instead of auto-incrementing integers
- Timezone-aware datetime fields using UTC

### Relationship Management
- One-to-many relationship: `ConversationORM -> MessageORM` (through repository, not ORM relationships)
- Cascading delete from conversations to messages via foreign key constraint
- No bidirectional ORM relationships to avoid complexity and circular imports
- Repository handles loading related data as needed

---

## AI Agent Integration

The models are designed to support BotSalinha's AI conversation features:

1. **Context Persistence:** Complete conversation history stored for context-aware responses
2. **Rate Limiting:** User/guild-based rate limiting using conversation metadata
3. **Multi-turn Conversations:** Message role tracking enables proper AI prompt construction
4. **Discord Context:** Guild ID support for server-specific behavior

---

## Dependencies

### Internal Dependencies
```python
# Database layer
from sqlalchemy import Base, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

# Configuration
from src.config.settings import get_settings

# Utilities
from src.utils.logger import setup_logging

# Type hints
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4
```

### External Dependencies
- `SQLAlchemy` - Async ORM for database operations
- `Pydantic` - Data validation and serialization
- `Alembic` - Database migrations (handled by scripts)
- `structlog` - Structured logging
- Python 3.11+ - For `StrEnum` support and modern Python features

---

## Migration Notes

Database schema changes require:
1. Update ORM models in files
2. Generate migration: `uv run alembic revision --autogenerate -m "description"`
3. Apply: `uv run alembic upgrade head`

**Important:** Never modify the database directly - always use Alembic migrations.