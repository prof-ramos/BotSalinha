"""Unit tests for SQLiteRepository."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.models.conversation import (
    Base,
    ConversationCreate,
    ConversationUpdate,
)
from src.models.message import MessageCreate, MessageRole
from src.storage.sqlite_repository import SQLiteRepository


@pytest_asyncio.fixture
async def repository():
    """Create a fresh in-memory repository for each test."""
    # Use in-memory database for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create repository with test engine
    repo = SQLiteRepository.__new__(SQLiteRepository)
    repo.engine = engine
    repo.async_session_maker = async_session_maker

    yield repo

    # Cleanup
    await engine.dispose()


class TestConversationRepository:
    """Tests for conversation repository methods."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, repository: SQLiteRepository) -> None:
        """Should create a new conversation."""
        conv_create = ConversationCreate(
            user_id="user123",
            guild_id="guild456",
            channel_id="channel789",
        )

        conversation = await repository.create_conversation(conv_create)

        assert conversation.id is not None
        assert conversation.user_id == "user123"
        assert conversation.guild_id == "guild456"
        assert conversation.channel_id == "channel789"

    @pytest.mark.asyncio
    async def test_get_conversation_by_id(self, repository: SQLiteRepository) -> None:
        """Should retrieve conversation by ID."""
        conv_create = ConversationCreate(
            user_id="user123",
            guild_id="guild456",
            channel_id="channel789",
        )
        created = await repository.create_conversation(conv_create)

        retrieved = await repository.get_conversation_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.user_id == "user123"

    @pytest.mark.asyncio
    async def test_get_conversation_by_id_not_found(
        self, repository: SQLiteRepository
    ) -> None:
        """Should return None for non-existent conversation."""
        result = await repository.get_conversation_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user_and_guild(self, repository: SQLiteRepository) -> None:
        """Should get conversations filtered by user and guild."""
        # Create multiple conversations
        await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )
        await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch2")
        )
        await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild2", channel_id="ch3")
        )
        await repository.create_conversation(
            ConversationCreate(user_id="user2", guild_id="guild1", channel_id="ch4")
        )

        # Get user1's conversations in guild1
        result = await repository.get_by_user_and_guild("user1", "guild1")

        assert len(result) == 2
        for conv in result:
            assert conv.user_id == "user1"
            assert conv.guild_id == "guild1"

    @pytest.mark.asyncio
    async def test_get_by_user_dm(
        self, repository: SQLiteRepository
    ) -> None:
        """Should get DM conversations (no guild_id)."""
        await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id=None, channel_id="dm1")
        )
        await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        result = await repository.get_by_user_and_guild("user1", None)

        assert len(result) == 1
        assert result[0].guild_id is None

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_existing(
        self, repository: SQLiteRepository
    ) -> None:
        """Should return existing conversation if exists."""
        created = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        retrieved = await repository.get_or_create_conversation(
            user_id="user1", guild_id="guild1", channel_id="ch1"
        )

        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_new(
        self, repository: SQLiteRepository
    ) -> None:
        """Should create new conversation if none exists."""
        conversation = await repository.get_or_create_conversation(
            user_id="user1", guild_id="guild1", channel_id="ch1"
        )

        assert conversation.id is not None
        assert conversation.user_id == "user1"
        assert conversation.channel_id == "ch1"

    @pytest.mark.asyncio
    async def test_update_conversation(
        self, repository: SQLiteRepository
    ) -> None:
        """Should update conversation metadata."""
        created = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        # meta_data expects a JSON string
        updated = await repository.update_conversation(
            created.id,
            ConversationUpdate(meta_data='{"topic": "legal_questions"}'),
        )

        assert updated is not None
        assert updated.meta_data == '{"topic": "legal_questions"}'

    @pytest.mark.asyncio
    async def test_update_conversation_not_found(
        self, repository: SQLiteRepository
    ) -> None:
        """Should return None when updating non-existent conversation."""
        result = await repository.update_conversation(
            "nonexistent",
            ConversationUpdate(meta_data='{"topic": "test"}'),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_conversation(
        self, repository: SQLiteRepository
    ) -> None:
        """Should delete conversation."""
        created = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        deleted = await repository.delete_conversation(created.id)
        assert deleted is True

        # Verify it's gone
        retrieved = await repository.get_conversation_by_id(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(
        self, repository: SQLiteRepository
    ) -> None:
        """Should return False when deleting non-existent conversation."""
        result = await repository.delete_conversation("nonexistent")
        assert result is False


class TestMessageRepository:
    """Tests for message repository methods."""

    @pytest.mark.asyncio
    async def test_create_message(self, repository: SQLiteRepository) -> None:
        """Should create a new message."""
        # Create conversation first
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        msg_create = MessageCreate(
            conversation_id=conv.id,
            role=MessageRole.USER,
            content="Hello, world!",
        )

        message = await repository.create_message(msg_create)

        assert message.id is not None
        assert message.conversation_id == conv.id
        assert message.role == MessageRole.USER
        assert message.content == "Hello, world!"

    @pytest.mark.asyncio
    async def test_get_message_by_id(self, repository: SQLiteRepository) -> None:
        """Should retrieve message by ID."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )
        created = await repository.create_message(
            MessageCreate(
                conversation_id=conv.id,
                role=MessageRole.USER,
                content="Test message",
            )
        )

        retrieved = await repository.get_message_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.content == "Test message"

    @pytest.mark.asyncio
    async def test_get_conversation_messages(
        self, repository: SQLiteRepository
    ) -> None:
        """Should get all messages for a conversation."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="Q1")
        )
        await repository.create_message(
            MessageCreate(
                conversation_id=conv.id, role=MessageRole.ASSISTANT, content="A1"
            )
        )
        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="Q2")
        )

        messages = await repository.get_conversation_messages(conv.id)

        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_get_conversation_messages_with_limit(
        self, repository: SQLiteRepository
    ) -> None:
        """Should limit number of messages returned."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        for i in range(5):
            await repository.create_message(
                MessageCreate(
                    conversation_id=conv.id,
                    role=MessageRole.USER,
                    content=f"Message {i}",
                )
            )

        messages = await repository.get_conversation_messages(conv.id, limit=3)

        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_get_conversation_messages_filter_by_role(
        self, repository: SQLiteRepository
    ) -> None:
        """Should filter messages by role."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="Q")
        )
        await repository.create_message(
            MessageCreate(
                conversation_id=conv.id, role=MessageRole.ASSISTANT, content="A"
            )
        )

        user_messages = await repository.get_conversation_messages(
            conv.id, role=MessageRole.USER
        )

        assert len(user_messages) == 1
        assert user_messages[0].role == MessageRole.USER

    @pytest.mark.asyncio
    async def test_get_conversation_history(
        self, repository: SQLiteRepository
    ) -> None:
        """Should get history formatted for LLM context."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="Q1")
        )
        await repository.create_message(
            MessageCreate(
                conversation_id=conv.id, role=MessageRole.ASSISTANT, content="A1"
            )
        )
        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="Q2")
        )
        await repository.create_message(
            MessageCreate(
                conversation_id=conv.id, role=MessageRole.ASSISTANT, content="A2"
            )
        )

        history = await repository.get_conversation_history(conv.id, max_runs=1)

        # Should return only last pair (2 messages) with max_runs=1
        assert len(history) <= 2

    @pytest.mark.asyncio
    async def test_delete_message(self, repository: SQLiteRepository) -> None:
        """Should delete a message."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )
        created = await repository.create_message(
            MessageCreate(
                conversation_id=conv.id,
                role=MessageRole.USER,
                content="To delete",
            )
        )

        deleted = await repository.delete_message(created.id)
        assert deleted is True

        retrieved = await repository.get_message_by_id(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_conversation_messages(
        self, repository: SQLiteRepository
    ) -> None:
        """Should delete all messages for a conversation."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="M1")
        )
        await repository.create_message(
            MessageCreate(conversation_id=conv.id, role=MessageRole.USER, content="M2")
        )

        count = await repository.delete_conversation_messages(conv.id)
        assert count == 2

        messages = await repository.get_conversation_messages(conv.id)
        assert len(messages) == 0


class TestRepositoryEdgeCases:
    """Edge case tests for repository."""

    @pytest.mark.asyncio
    async def test_conversation_auto_timestamps(
        self, repository: SQLiteRepository
    ) -> None:
        """Should auto-generate created_at and updated_at."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )

        assert conv.created_at is not None
        assert conv.updated_at is not None

    @pytest.mark.asyncio
    async def test_message_auto_timestamp(
        self, repository: SQLiteRepository
    ) -> None:
        """Should auto-generate created_at for messages."""
        conv = await repository.create_conversation(
            ConversationCreate(user_id="user1", guild_id="guild1", channel_id="ch1")
        )
        msg = await repository.create_message(
            MessageCreate(
                conversation_id=conv.id,
                role=MessageRole.USER,
                content="Test",
            )
        )

        assert msg.created_at is not None

    @pytest.mark.asyncio
    async def test_multiple_conversations_same_user_different_channels(
        self, repository: SQLiteRepository
    ) -> None:
        """Should allow same user to have conversations in different channels."""
        conv1 = await repository.get_or_create_conversation(
            user_id="user1", guild_id="guild1", channel_id="ch1"
        )
        conv2 = await repository.get_or_create_conversation(
            user_id="user1", guild_id="guild1", channel_id="ch2"
        )

        assert conv1.id != conv2.id
        assert conv1.channel_id == "ch1"
        assert conv2.channel_id == "ch2"
