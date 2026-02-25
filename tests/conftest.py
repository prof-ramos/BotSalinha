"""
Pytest configuration and shared fixtures.

Uses best practices from Context7 for fixture management.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import Settings
from src.core.agent import AgentWrapper
from src.core.discord import BotSalinhaBot
from src.models.conversation import ConversationORM
from src.models.message import create_message_orm, MessageRole
from src.models.message import MessageCreate
from src.storage.sqlite_repository import SQLiteRepository
from src.storage.repository import ConversationRepository, MessageRepository
from src.middleware.rate_limiter import RateLimiter

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create event loop for async tests.

    This fixture is session-scoped to avoid creating a new loop for each test.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def test_settings(monkeypatch) -> Settings:
    """
    Provide test settings with minimal configuration.

    Environment variables are reset per test.
    """
    monkeypatch.setenv("BOTSALINHA_DISCORD__TOKEN", "test_token_12345")
    monkeypatch.setenv("BOTSALINHA_GOOGLE__API_KEY", "test_api_key")
    monkeypatch.setenv("BOTSALINHA_DATABASE__URL", TEST_DATABASE_URL)
    monkeypatch.setenv("BOTSALINHA_APP__ENV", "testing")
    monkeypatch.setenv("BOTSALINHA_RATE__LIMIT__REQUESTS", "100")

    from src.config.settings import settings
    # Clear cache to reload settings
    from src.config.settings import get_settings
    get_settings.cache_clear()

    return get_settings()


@pytest_asyncio.fixture
async def test_engine(test_settings: Settings):
    """
    Create test database engine.

    Creates an in-memory SQLite database for each test.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(ConversationORM.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(ConversationORM.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """
    Create test database session.

    Provides a clean session for each test.
    """
    async_session_maker = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def conversation_repository(test_engine) -> ConversationRepository:
    """Create conversation repository for testing."""
    repo = SQLiteRepository(TEST_DATABASE_URL)
    await repo.initialize_database()
    await repo.create_tables()

    yield repo

    await repo.close()


@pytest_asyncio.fixture
async def message_repository(test_engine) -> MessageRepository:
    """Create message repository for testing."""
    repo = SQLiteRepository(TEST_DATABASE_URL)
    await repo.initialize_database()
    await repo.create_tables()

    yield repo

    await repo.close()


@pytest.fixture
def mock_discord_context():
    """Create a mock Discord command context."""
    ctx = MagicMock()
    ctx.author.id = 123456789
    ctx.author.name = "TestUser"
    ctx.author.bot = False
    ctx.guild.id = 987654321
    ctx.guild.name = "TestGuild"
    ctx.channel.id = 111222333
    ctx.channel.name = "test-channel"
    ctx.message.id = 999888777
    ctx.send = AsyncMock()
    ctx.typing = AsyncMock()

    return ctx


@pytest.fixture
def rate_limiter():
    """Create a rate limiter for testing."""
    # Use lenient settings for tests
    return RateLimiter(
        requests=100,
        window_seconds=60,
    )


@pytest.fixture
def agent_wrapper(test_settings: Settings):
    """Create an agent wrapper for testing."""
    return AgentWrapper()


# Autouse fixture to clear contextvars between tests
@pytest.fixture(autouse=True)
async def clear_contextvars():
    """
    Clear structlog contextvars between tests.

    This ensures context doesn't leak between tests.
    """
    from structlog.contextvars import clear_contextvars
    clear_contextvars()
    yield
    clear_contextvars()


# Helper functions for tests
async def create_test_conversation(
    repo: ConversationRepository,
    user_id: str = "123",
    guild_id: str | None = "456",
    channel_id: str = "789",
) -> Any:
    """Helper to create a test conversation."""
    from src.models.conversation import ConversationCreate

    conv = await repo.create(
        ConversationCreate(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )
    )
    return conv


async def create_test_message(
    repo: MessageRepository,
    conversation_id: str,
    role: MessageRole = MessageRole.USER,
    content: str = "Test message",
) -> Any:
    """Helper to create a test message."""
    msg = await repo.create(
        MessageCreate(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
    )
    return msg
