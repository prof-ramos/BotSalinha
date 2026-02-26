"""
Pytest configuration and shared fixtures.

Uses best practices from Context7 for fixture management.
"""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from faker import Faker
from freezegun import freeze_time
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import Settings
from src.core.agent import AgentWrapper
from src.middleware.rate_limiter import RateLimiter
from src.models.conversation import ConversationORM
from src.models.message import MessageCreate, MessageRole
from src.storage.repository import ConversationRepository, MessageRepository
from src.storage.sqlite_repository import SQLiteRepository

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Initialize Faker for Brazilian Portuguese test data
fake = Faker("pt_BR")


@pytest.fixture(autouse=True)
def seed_faker():
    """Seed Faker for deterministic test data across runs."""
    Faker.seed(12345)
    yield


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

    Environment variables are reset per test using monkeypatch.
    """
    monkeypatch.setenv("BOTSALINHA_DISCORD__TOKEN", "test_token_12345")
    monkeypatch.setenv("BOTSALINHA_GOOGLE__API_KEY", "test_api_key")
    monkeypatch.setenv("BOTSALINHA_DATABASE__URL", TEST_DATABASE_URL)
    monkeypatch.setenv("BOTSALINHA_APP__ENV", "testing")
    monkeypatch.setenv("BOTSALINHA_RATE__LIMIT__REQUESTS", "100")

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
    async_session_maker = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

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
    ctx.author = MagicMock()
    ctx.author.id = 123456789
    ctx.author.name = "TestUser"
    ctx.author.bot = False
    ctx.author.mention = "<@123456789>"
    ctx.guild = MagicMock()
    ctx.guild.id = 987654321
    ctx.guild.name = "TestGuild"
    ctx.channel = MagicMock()
    ctx.channel.id = 111222333
    ctx.channel.name = "test-channel"
    ctx.message = MagicMock()
    ctx.message.id = 999888777
    ctx.message.content = ""
    ctx.message.author = ctx.author
    ctx.message.guild = ctx.guild
    ctx.message.channel = ctx.channel
    ctx.send = AsyncMock()
    ctx.typing = AsyncMock()
    ctx.reply = AsyncMock()

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

    conv = await repo.create_conversation(
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
    msg = await repo.create_message(
        MessageCreate(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
    )
    return msg


# ===== Additional Fixtures for E2E Testing =====


def pytest_configure(config):
    """
    Configure custom pytest markers.

    Markers can be used to categorize tests:
    - pytest.mark.e2e: End-to-end tests
    - pytest.mark.integration: Integration tests
    - pytest.mark.unit: Unit tests
    - pytest.mark.slow: Slow-running tests
    - pytest.mark.discord: Tests requiring Discord mocks
    - pytest.mark.gemini: Tests requiring Gemini API mocks
    - pytest.mark.database: Tests requiring database
    """
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "discord: Tests requiring Discord mocks")
    config.addinivalue_line("markers", "gemini: Tests requiring Gemini API mocks")
    config.addinivalue_line("markers", "database: Tests requiring database")


@pytest.fixture
def mock_gemini_api():
    """
    Mock the Gemini API for testing using httpx.

    NOTE: The google-genai SDK uses httpx internally. This fixture mocks
    httpx.AsyncClient.send to intercept API calls.

    For more reliable testing, consider using the agent_with_openrouter fixture
    with a real OpenRouter API key instead.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock httpx response
    async def mock_send(request, **kwargs):
        """Mock httpx send method."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}

        # Mock json() method
        mock_response.json = MagicMock(
            return_value={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Esta é uma resposta de teste do BotSalinha sobre direito brasileiro. No Brasil, o princípio da legalidade é fundamental e está estabelecido no artigo 37 da Constituição Federal."
                                }
                            ],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ]
            }
        )

        # Mock aread() method for streaming
        async def mock_aread():
            return b'{"candidates": [{"content": {"parts": [{"text": "Test response"}]}}]}'

        mock_response.aread = mock_aread

        return mock_response

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=mock_send)):
        yield


@pytest.fixture
def openrouter_test_model(monkeypatch):
    """
    Configure test environment to use OpenRouter with free model.

    This fixture overrides the model configuration to use OpenRouter's
    free tier for testing, avoiding the need to mock HTTP requests.

    Requires OPENROUTER_API_KEY environment variable to be set.
    Free model used: google/gemma-2-9b-it:free

    Usage in tests:
        def test_my_agent(openrouter_test_model, agent_wrapper):
            response = await agent_wrapper.generate_response(...)
    """
    import os

    # Check if API key is set
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    # Set environment variables for OpenRouter
    monkeypatch.setenv("OPENROUTER_API_KEY", api_key)
    monkeypatch.setenv("BOTSALINHA_GOOGLE__MODEL_ID", "openrouter:google/gemma-2-9b-it:free")

    # Import here to avoid import errors if google-genai not installed
    try:
        from agno.models.openrouter import OpenRouter

        return OpenRouter(
            id="google/gemma-2-9b-it:free",
            api_key=api_key,
        )
    except ImportError:
        pytest.skip("OpenRouter not available - install agno[openrouter]")


@pytest.fixture
def agent_with_openrouter(openrouter_test_model, conversation_repository):
    """
    Create an AgentWrapper configured with OpenRouter for testing.

    This fixture provides a test-ready agent that uses OpenRouter's free tier
    instead of Gemini, avoiding API mocking issues.

    Example:
        async def test_legal_question(agent_with_openrouter):
            response = await agent_with_openrouter.generate_response(
                prompt="Qual é o prazo de prescrição?",
                conversation_id="test-conv-1",
                user_id="test-user",
            )
            assert len(response) > 50
    """
    from agno.agent import Agent

    from src.config.yaml_config import yaml_config
    from src.core.agent import AgentWrapper

    # Create a test agent with OpenRouter
    test_agent = Agent(
        name="BotSalinhaTest",
        model=openrouter_test_model,
        instructions=yaml_config.prompt_content,
        add_history_to_context=True,
        num_history_runs=3,
        add_datetime_to_context=True,
        markdown=True,
        debug_mode=False,
    )

    # Create a wrapper with the test agent
    wrapper = AgentWrapper(repository=conversation_repository)
    wrapper.agent = test_agent  # Replace the Gemini agent with OpenRouter

    return wrapper


@pytest.fixture
def frozen_time():
    """
    Freeze time for consistent testing.

    Uses freezegun to freeze time at a fixed point.
    """
    with freeze_time("2024-01-15 10:30:00"):
        yield datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


@pytest.fixture
def test_user_id():
    """Provide a consistent test user ID."""
    return "123456789012345678"


@pytest.fixture
def test_guild_id():
    """Provide a consistent test guild ID."""
    return "987654321098765432"


@pytest.fixture
def test_channel_id():
    """Provide a consistent test channel ID."""
    return "111222333444555666"


@pytest.fixture
def fake_legal_question():
    """
    Generate a fake legal question.

    Uses Faker to create realistic-looking Brazilian legal questions.
    """
    questions = [
        "Qual é o prazo de prescrição para uma ação trabalhista?",
        "Quais são os requisitos para ingressar no cargo de procurador?",
        "Explique a diferença entre crime doloso e culposo.",
        "Qual é a base de cálculo do ICMS?",
        "Quais são os direitos fundamentais previstos na Constituição?",
        "O que é jurisprudência e qual o seu valor?",
        "Explique o princípio da dignidade da pessoa humana.",
        "Quais são os tipos de penas previstas no Código Penal?",
    ]
    return fake.random_element(questions)


@pytest.fixture
def fake_legal_response():
    """
    Generate a fake legal response.

    Uses Faker to create realistic-looking legal responses.
    """
    responses = [
        "De acordo com a Constituição Federal de 1988, o prazo é de 5 anos para ações trabalhistas.",
        "Os requisitos incluem bacharelado em Direito, aprovação em concurso público e posse.",
        "Crime doloso ocorre quando há intenção do agente, enquanto crime culposo resulta de negligência.",
        "A base de cálculo do ICMS é o valor da operação, conforme artigo 13 da Lei Complementar 87/1996.",
        "Os direitos fundamentais estão previstos no artigo 5º da Constituição Federal.",
        "A jurisprudência é o conjunto de decisões reiteradas dos tribunais sobre uma matéria.",
        "O princípio da dignidade da pessoa humana está no artigo 1º, inciso III da Constituição.",
        "O Código Penal prevê penas privativas de liberdade, restritivas de direitos e multa.",
    ]
    return fake.random_element(responses)


@pytest_asyncio.fixture
async def bot_wrapper(conversation_repository):
    """
    Create bot wrapper with test repository.

    This is a shared fixture for E2E tests that need a Discord bot wrapper.
    """
    from tests.fixtures.bot_wrapper import DiscordBotWrapper

    wrapper = DiscordBotWrapper(repository=conversation_repository)
    yield wrapper
    await wrapper.cleanup()
