"""
SQLite repository implementation.

Implements conversation and message repositories using SQLAlchemy with SQLite.
Uses async patterns and proper connection management.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..config.settings import settings
from ..models.conversation import (
    Base,
    Conversation,
    ConversationCreate,
    ConversationORM,
    ConversationUpdate,
)
from ..models.message import (
    Message,
    MessageCreate,
    MessageRole,
    MessageUpdate,
    create_message_orm,
)
from .repository import ConversationRepository, MessageRepository

log = structlog.get_logger()

# Create MessageORM with the correct base
MessageORM = create_message_orm(Base)


class SQLiteRepository(ConversationRepository, MessageRepository):
    """
    SQLite repository implementation.

    Handles all database operations using SQLAlchemy with async support.
    Uses WAL mode for better concurrency.
    """

    def __init__(self, database_url: str | None = None) -> None:
        """
        Initialize the SQLite repository.

        Args:
            database_url: Database URL (defaults to settings)
        """
        self.database_url = database_url or settings.database.url

        # Convert sqlite:// to sqlite+aiosqlite:// for async support
        if self.database_url.startswith("sqlite:///"):
            self.database_url = self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

        # Create async engine with optimized settings for SQLite
        self.engine = create_async_engine(
            self.database_url,
            echo=settings.database.echo,
            connect_args={
                "check_same_thread": False,  # Needed for SQLite
            },
        )

        # Create session factory
        self.async_session_maker = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        log.info(
            "sqlite_repository_initialized",
            database_url=self.database_url.replace("+aiosqlite", ""),  # Hide in logs
        )

    async def initialize_database(self) -> None:
        """
        Initialize the database schema and enable WAL mode.

        Should be called on application startup.
        """
        async with self.engine.begin() as conn:
            # Enable WAL mode for better concurrency
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB cache
            await conn.execute(text("PRAGMA temp_store=memory"))

            log.info("sqlite_wal_mode_enabled")

    async def create_tables(self) -> None:
        """Create all tables in the database."""
        async with self.engine.begin() as conn:
            await conn.run_sync(ConversationORM.metadata.create_all)
            log.info("database_tables_created")

    async def close(self) -> None:
        """Close the database connection."""
        await self.engine.dispose()
        log.info("sqlite_repository_closed")

    # Conversation Repository Methods

    async def create_conversation(self, conversation: ConversationCreate) -> Conversation:
        async with self.async_session_maker() as session:
            orm = ConversationORM(
                user_id=conversation.user_id,
                guild_id=conversation.guild_id,
                channel_id=conversation.channel_id,
                meta_data=conversation.meta_data,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)

            return Conversation.model_validate(orm)

    async def get_conversation_by_id(self, conversation_id: str) -> Conversation | None:
        async with self.async_session_maker() as session:
            stmt = select(ConversationORM).where(ConversationORM.id == conversation_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return None

            return Conversation.model_validate(orm)

    async def get_by_user_and_guild(
        self, user_id: str, guild_id: str | None = None
    ) -> list[Conversation]:
        async with self.async_session_maker() as session:
            stmt = select(ConversationORM).where(ConversationORM.user_id == user_id)

            if guild_id is not None:
                stmt = stmt.where(ConversationORM.guild_id == guild_id)
            else:
                stmt = stmt.where(ConversationORM.guild_id.is_(None))

            stmt = stmt.order_by(ConversationORM.updated_at.desc())

            result = await session.execute(stmt)
            orms = result.scalars().all()

            return [Conversation.model_validate(orm) for orm in orms]

    async def get_or_create_conversation(
        self, user_id: str, guild_id: str | None, channel_id: str
    ) -> Conversation:
        # Try to get existing conversation
        conversations = await self.get_by_user_and_guild(user_id, guild_id)

        # Filter by channel and get most recent
        for conv in conversations:
            if conv.channel_id == channel_id:
                return conv

        # Create new conversation
        create_data = ConversationCreate(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )
        return await self.create_conversation(create_data)

    async def update_conversation(
        self, conversation_id: str, updates: ConversationUpdate
    ) -> Conversation | None:
        async with self.async_session_maker() as session:
            stmt = select(ConversationORM).where(ConversationORM.id == conversation_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return None

            if updates.meta_data is not None:
                orm.meta_data = updates.meta_data

            await session.commit()
            await session.refresh(orm)

            return Conversation.model_validate(orm)

    async def delete_conversation(self, conversation_id: str) -> bool:
        async with self.async_session_maker() as session:
            stmt = select(ConversationORM).where(ConversationORM.id == conversation_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return False

            await session.delete(orm)
            await session.commit()

            return True

    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """Delete conversations older than specified days."""
        async with self.async_session_maker() as session:
            cutoff = datetime.now(UTC) - timedelta(days=days)

            stmt = delete(ConversationORM).where(ConversationORM.updated_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()

            count = result.rowcount
            if count > 0:
                log.info("old_conversations_cleaned", count=count, days=days)

            return count

    # Message Repository Methods

    async def create_message(self, message: MessageCreate) -> Message:
        async with self.async_session_maker() as session:
            orm = MessageORM(
                conversation_id=message.conversation_id,
                role=message.role.value,
                content=message.content,
                discord_message_id=message.discord_message_id,
                meta_data=message.meta_data,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)

            return Message.model_validate(orm)

    async def get_message_by_id(self, message_id: str) -> Message | None:
        async with self.async_session_maker() as session:
            stmt = select(MessageORM).where(MessageORM.id == message_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return None

            return Message.model_validate(orm)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
        role: MessageRole | None = None,
    ) -> list[Message]:
        async with self.async_session_maker() as session:
            stmt = select(MessageORM).where(MessageORM.conversation_id == conversation_id)

            if role is not None:
                stmt = stmt.where(MessageORM.role == role.value)

            stmt = stmt.order_by(MessageORM.created_at.asc())

            if limit is not None:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            orms = result.scalars().all()

            return [Message.model_validate(orm) for orm in orms]

    async def get_conversation_history(
        self,
        conversation_id: str,
        max_runs: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history formatted for LLM context.

        Returns messages in pairs of (user, assistant) up to max_runs.
        """
        messages = await self.get_conversation_messages(
            conversation_id,
            limit=max_runs * 2 + 10,  # Get extra, then filter
        )

        # Convert to LLM format
        history = []
        for msg in messages:
            if msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                history.append({"role": msg.role.value, "content": msg.content})

        # Limit to max_runs pairs
        # Keep system messages, then truncate user/assistant pairs
        system_messages = [m for m in history if m["role"] == "system"]
        user_assistant = [m for m in history if m["role"] != "system"]

        # Keep last max_runs pairs (2 messages per run)
        user_assistant = user_assistant[-(max_runs * 2) :]

        return system_messages + user_assistant

    async def update_message(self, message_id: str, updates: MessageUpdate) -> Message | None:
        async with self.async_session_maker() as session:
            stmt = select(MessageORM).where(MessageORM.id == message_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return None

            if updates.content is not None:
                orm.content = updates.content
            if updates.meta_data is not None:
                orm.meta_data = updates.meta_data

            await session.commit()
            await session.refresh(orm)

            return Message.model_validate(orm)

    async def delete_message(self, message_id: str) -> bool:
        async with self.async_session_maker() as session:
            stmt = select(MessageORM).where(MessageORM.id == message_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return False

            await session.delete(orm)
            await session.commit()

            return True

    async def delete_conversation_messages(self, conversation_id: str) -> int:
        async with self.async_session_maker() as session:
            stmt = delete(MessageORM).where(MessageORM.conversation_id == conversation_id)
            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount


# Global repository instance (for backward compatibility)
_repository: SQLiteRepository | None = None


def get_repository() -> SQLiteRepository:
    """
    Get the global repository instance.

    Creates a new instance if none exists.
    For testing, use set_repository() to inject a mock.
    """
    global _repository
    if _repository is None:
        _repository = SQLiteRepository()
    return _repository


def set_repository(repo: SQLiteRepository | None) -> None:
    """
    Set the global repository instance.

    Use this for dependency injection in tests.

    Args:
        repo: Repository instance to use, or None to reset
    """
    global _repository
    _repository = repo


def reset_repository() -> None:
    """
    Reset the global repository instance.

    Call this in test teardown to ensure clean state.
    """
    global _repository
    if _repository is not None:
        # Close existing connection if any
        try:
            import asyncio

            asyncio.get_event_loop().run_until_complete(_repository.close())
        except Exception:
            pass
    _repository = None


__all__ = [
    "SQLiteRepository",
    "MessageORM",
    "get_repository",
    "set_repository",
    "reset_repository",
]
