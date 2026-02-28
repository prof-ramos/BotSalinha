"""
SQLite repository implementation.

Implements conversation and message repositories using SQLAlchemy with SQLite.
Uses async patterns and proper connection management.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import structlog
from cachetools import TTLCache
from sqlalchemy import delete, select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.selectable import TypedReturnsRows

if TYPE_CHECKING:
    pass

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
from ..utils.log_events import LogEvents
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

    def __init__(
        self,
        database_url: str | None = None,
        engine: AsyncEngine | None = None,
    ) -> None:
        """
        Initialize the SQLite repository.

        Args:
            database_url: Database URL (defaults to settings). Ignored when engine is provided.
            engine: Existing AsyncEngine to reuse (e.g. for tests sharing an in-memory DB).
        """
        if engine is not None:
            self.engine = engine
            self.database_url = str(engine.url)
        else:
            self.database_url = database_url or settings.database.url

            # Convert sqlite:// to sqlite+aiosqlite:// for async support
            if self.database_url.startswith("sqlite:///"):
                self.database_url = self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

            # Create async engine with optimized settings for SQLite
            # StaticPool reuses a single connection — ideal for SQLite
            # which serializes writes regardless of pool strategy.
            self.engine = create_async_engine(
                self.database_url,
                echo=settings.database.echo,
                connect_args={
                    "check_same_thread": False,  # Needed for SQLite
                },
                poolclass=StaticPool,
            )

        # TTL cache for conversation lookups (avoids repeated DB hits)
        self._conversation_cache: TTLCache[str, Any] = TTLCache(maxsize=256, ttl=300)

        # Create session factory
        self.async_session_maker = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

        log.info(
            LogEvents.REPOSITORIO_SQLITE_INICIALIZADO,
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

            log.info(LogEvents.MODO_WAL_ATIVADO)

    async def create_tables(self) -> None:
        """Create all tables in the database."""
        async with self.engine.begin() as conn:
            await conn.run_sync(ConversationORM.metadata.create_all)
            log.info(LogEvents.TABELAS_BANCO_CRIADAS)

    async def close(self) -> None:
        """Close the database connection."""
        await self.engine.dispose()
        log.info(LogEvents.REPOSITORIO_SQLITE_FECHADO)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Open a short-lived database session for direct SQL access.

        Use this when external code (e.g. RAG services, CLI commands) needs
        a raw SQLAlchemy session backed by the same engine as this repository.

        Example::

            async with repo.session() as s:
                result = await s.execute(select(DocumentORM))
        """
        async with self.async_session_maker() as s:
            yield s

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
        # Check cache first
        cache_key = f"{user_id}:{guild_id}:{channel_id}"
        if cache_key in self._conversation_cache:
            return cast(Conversation, self._conversation_cache[cache_key])

        # Single optimized query with channel_id filter (avoids N+1 pattern)
        async with self.async_session_maker() as session:
            stmt = select(ConversationORM).where(
                ConversationORM.user_id == user_id,
                ConversationORM.channel_id == channel_id,
            )
            if guild_id is not None:
                stmt = stmt.where(ConversationORM.guild_id == guild_id)
            else:
                stmt = stmt.where(ConversationORM.guild_id.is_(None))

            stmt = stmt.order_by(ConversationORM.updated_at.desc()).limit(1)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is not None:
                conv = Conversation.model_validate(orm)
                self._conversation_cache[cache_key] = conv
                return conv

        # Create new conversation
        create_data = ConversationCreate(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )
        conv = await self.create_conversation(create_data)
        self._conversation_cache[cache_key] = conv
        return conv

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

            # Invalidate cache entries referencing this conversation
            keys_to_remove = [
                k for k, v in list(self._conversation_cache.items()) if v.id == conversation_id
            ]
            for k in keys_to_remove:
                self._conversation_cache.pop(k, None)

            return True

    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """Delete conversations older than specified days."""
        async with self.async_session_maker() as session:
            cutoff = datetime.now(UTC) - timedelta(days=days)

            stmt = delete(ConversationORM).where(ConversationORM.updated_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()

            # Use cursor_result to get proper typing for rowcount
            cursor_result = cast(CursorResult[Any], result)
            count = cursor_result.rowcount
            if count > 0:
                log.info(LogEvents.CONVERSAS_ANTIGAS_LIMPAS, count=count, days=days)

            return count

    async def get_dm_conversations(self, user_id: str) -> list[Conversation]:
        """
        Get all DM (Direct Message) conversations for a user.

        Args:
            user_id: Discord user ID

        Returns:
            List of DM conversations (guild_id is None)
        """
        return await self.get_by_user_and_guild(user_id=user_id, guild_id=None)

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
            stmt: TypedReturnsRows[tuple[Any]] = select(MessageORM).where(  # type: ignore[valid-type]
                MessageORM.id == message_id  # type: ignore[attr-defined]
            )
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
            stmt: Any = select(MessageORM).where(MessageORM.conversation_id == conversation_id)  # type: ignore[valid-type,attr-defined]

            if role is not None:
                stmt = stmt.where(MessageORM.role == role.value)  # type: ignore[attr-defined]

            stmt = stmt.order_by(MessageORM.created_at.asc())  # type: ignore[attr-defined]

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

        Returns the last N user/assistant message pairs directly as dicts,
        bypassing Pydantic conversion for performance.
        """
        async with self.async_session_maker() as session:
            # Query only the columns we need, filter by role in SQL,
            # fetch only the exact number of messages needed.
            stmt = (
                select(MessageORM.role, MessageORM.content)  # type: ignore[attr-defined]
                .where(
                    MessageORM.conversation_id == conversation_id,  # type: ignore[attr-defined]
                    MessageORM.role.in_(["user", "assistant"]),  # type: ignore[attr-defined]
                )
                .order_by(MessageORM.created_at.desc())  # type: ignore[attr-defined]
                .limit(max_runs * 2)
            )
            result = await session.execute(stmt)
            rows = result.all()

        # Reverse to chronological order
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    async def update_message(self, message_id: str, updates: MessageUpdate) -> Message | None:
        async with self.async_session_maker() as session:
            stmt: Any = select(MessageORM).where(MessageORM.id == message_id)  # type: ignore[valid-type,attr-defined]
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
            stmt: Any = select(MessageORM).where(MessageORM.id == message_id)  # type: ignore[valid-type,attr-defined]
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()

            if orm is None:
                return False

            await session.delete(orm)
            await session.commit()

            return True

    async def delete_conversation_messages(self, conversation_id: str) -> int:
        async with self.async_session_maker() as session:
            stmt = delete(MessageORM).where(MessageORM.conversation_id == conversation_id)  # type: ignore[attr-defined]
            cursor_result = cast(CursorResult[Any], await session.execute(stmt))
            await session.commit()

            return cursor_result.rowcount

    async def clear_all_history(self) -> dict[str, int]:
        """
        Delete all conversations and messages from the database.

        Returns:
            Dictionary with counts of deleted items
        """
        async with self.async_session_maker() as session:
            # Delete messages first (foreign key constraints)
            msg_stmt = delete(MessageORM)
            msg_result = await session.execute(msg_stmt)

            # Delete conversations
            conv_stmt = delete(ConversationORM)
            conv_result = await session.execute(conv_stmt)

            await session.commit()

            # Clear cache
            self._conversation_cache.clear()

            counts = {
                "messages": msg_result.rowcount,  # type: ignore[attr-defined]
                "conversations": conv_result.rowcount,  # type: ignore[attr-defined]
            }

            log.info(LogEvents.BANCO_DADOS_LIMPO, **counts)
            return counts


# Global repository instance
repository: SQLiteRepository | None = None


def get_repository() -> SQLiteRepository:
    """Get the global repository instance."""
    global repository
    if repository is None:
        repository = SQLiteRepository()
    return repository


__all__ = [
    "SQLiteRepository",
    "MessageORM",
    "get_repository",
    "repository",
]
