# AGENTS.md — BotSalinha Test Suite

<!-- PARENT: ../AGENTS.md -->
<!-- GENERATED: 2026-02-27 -->
<!-- UPDATED: 2026-02-27 -->

## Purpose

This AGENTS.md defines the testing strategy, patterns, and conventions for the BotSalinha test suite. It provides comprehensive guidance for writing, organizing, and executing tests across different test categories while maintaining high code quality and test coverage.

## Key Files

| File | Description | Purpose |
|------|-------------|---------|
| `conftest.py` | Shared fixtures and test configuration | Provides `test_settings`, `test_engine`, `test_session`, `test_repository` fixtures used across all test suites |
| `pytest.ini` | Pytest configuration | Defines test discovery patterns, markers, and CLI options |
| `pyproject.toml` | Project metadata and dependencies | Contains test dependencies, coverage configuration, and pytest setup |

## Test Suite Organization

| Directory | Description | Test Types | Coverage Scope |
|----------|-------------|------------|----------------|
| `unit/` | Isolated component tests | `@pytest.mark.unit` | Individual components in isolation |
| `integration/` | Multi-component tests | `@pytest.mark.integration` | Multiple working together |
| `e2e/` | End-to-end system tests | `@pytest.mark.e2e` | Full system workflows |
| `fixtures/` | Test data and factories | - | Shared test utilities and data |

## AI Agent Instructions

### Test Architecture Principles

1. **AAA Pattern**: Arrange, Act, Assert
   - **Arrange**: Set up test data and dependencies
   - **Act**: Execute the function under test
   - **Assert**: Verify the expected outcome

2. **Arrange-Act-Assert with Context**
   ```python
   # Arrange
   mock_discord_client = mocker.MagicMock()
   test_question = "Qual a diferença entre direito constitucional e administrativo?"

   # Act
   response = await agent_wrapper.generate_response(
       user_id=12345,
       question=test_question,
       conversation_history=[]
   )

   # Assert
   assert response is not None
   assert isinstance(response, str)
   assert len(response) > 0
   ```

3. **Isolation**: Each test should be independent and self-contained
4. **Determinism**: Tests should produce the same results every time
5. **Performance**: Unit tests should be fast (< 100ms each)

### Testing Patterns by Category

#### Unit Tests (`tests/unit/`)
- **Focus**: Test individual components in isolation
- **Mocking**: Use `pytest-mock` for all external dependencies
- **Database**: In-memory SQLite with test engine
- **Examples**:
  - `test_agent_wrapper.py`: Test response generation logic
  - `test_rate_limiter.py`: Test rate limiting calculations
  - `test_discord_commands.py`: Test individual command handlers

#### Integration Tests (`tests/integration/`)
- **Focus**: Test multiple components working together
- **Scope**: Service layer integration, repository operations
- **Database**: Test database with temporary files
- **Examples**:
  - `test_agent_with_repository.py`: Test agent with database persistence
  - `test_conversation_flow.py`: Test conversation state management

#### E2E Tests (`tests/e2e/`)
- **Focus**: Full system workflows and user journeys
- **Scope**: Discord integration, AI responses, database persistence
- **Mocking**: Real API mocks for Discord and OpenAI
- **Examples**:
  - `test_discord_bot_workflow.py`: Complete bot interaction flow
  - `test_end_to_end_conversation.py`: Multi-turn conversations

#### Fixtures (`tests/fixtures/`)
- **Focus**: Shared test utilities and data
- **Contents**:
  - `factories/`: Test data factories using `factory-boy`
  - `mocks.py`: Common mock configurations
  - `data/`: Static test data files

### Mocking Strategy

#### Discord API Mocking
```python
import pytest
from unittest.mock import MagicMock, AsyncMock
import pytest_mock

@pytest.fixture
def mock_discord_client(mocker: pytest_mock.MockerFixture) -> MagicMock:
    """Mock Discord client for testing bot commands."""
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 12345
    mock_user.name = "TestUser"

    mock_message = AsyncMock()
    mock_message.author = mock_user
    mock_message.content = "!ask O que é direito administrativo?"
    mock_message.channel = MagicMock()
    mock_message.channel.send = AsyncMock()

    mock_client.user = MagicMock()
    mock_client.user.id = 67890
    mock_client.is_ready = True

    return mock_client
```

#### OpenAI API Mocking
```python
@pytest.fixture
def mock_openai_client(mocker: pytest_mock.MockerFixture) -> MagicMock:
    """Mock OpenAI client for testing AI responses."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Resposta sobre direito administrativo..."
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client
```

### Database Testing Patterns

#### Test Database Setup
```python
@pytest.fixture
def test_engine() -> AsyncEngine:
    """Create test database engine with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )

    # Create all tables
    async def setup_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Run setup in event loop
    asyncio.run(setup_tables())
    return engine
```

#### Repository Testing
```python
@pytest.fixture
def test_repository(test_engine: AsyncEngine) -> SQLiteRepository:
    """Create test repository with in-memory database."""
    return SQLiteRepository(test_engine)

@pytest.mark.asyncio
async def test_save_conversation(test_repository: SQLiteRepository) -> None:
    """Test conversation persistence."""
    # Arrange
    conversation = ConversationORM(
        user_id=12345,
        guild_id=67890,
        messages=[
            MessageORM(role="user", content="Test question"),
            MessageORM(role="assistant", content="Test response")
        ]
    )

    # Act
    saved = await test_repository.save_conversation(conversation)

    # Assert
    assert saved.id is not None
    assert saved.user_id == 12345
    assert len(saved.messages) == 2
```

### Brazilian Test Data

```python
@pytest.fixture
def brazilian_factory(faker: Faker) -> Faker:
    """Faker instance configured for Brazilian Portuguese."""
    faker.unique.clear()
    faker.add_provider(pt_BR)
    return faker

@pytest.fixture
def sample_brazilian_question(brazilian_factory: Faker) -> str:
    """Generate realistic Brazilian legal question."""
    return brazilian_factory.sentence(
        nb_words=15,
        ext_word_list=[
            "direito", "constitucional", "administrativo",
            "penal", "civil", "processo", "justiça"
        ]
    )
```

### Time-Dependent Testing

```python
import freezegun

@pytest.mark.asyncio
@freezegun.freeze_time("2024-01-15 10:00:00")
async def test_rate_limit_with_frozen_time() -> None:
    """Test rate limiting with fixed time."""
    # Arrange
    rate_limiter = RateLimiter(
        requests=3,
        window_seconds=60
    )

    user_id = 12345

    # Act & Assert - first 3 requests should pass
    for _ in range(3):
        assert await rate_limiter.check_rate_limit(user_id) is True

    # 4th request should be blocked
    assert await rate_limiter.check_rate_limit(user_id) is False
```

## Testing Requirements

### Coverage Requirements
- **Minimum Coverage**: 70% (enforced in CI)
- **Unit Tests**: 90%+ coverage required
- **Integration Tests**: 80%+ coverage required
- **E2E Tests**: Coverage not required (functional validation)

### Test Execution Patterns

#### Run All Tests
```bash
uv run pytest
```

#### Run Specific Test Suite
```bash
# Unit tests only
uv run pytest tests/unit/

# Integration tests only
uv run pytest tests/integration/

# E2E tests only
uv run pytest tests/e2e/

# Tests with coverage
uv run pytest --cov=src --cov-report=html
```

#### Parallel Testing
```bash
uv run pytest --numprocesses=auto
```

### Test Markers Usage

```python
# Unit test example
@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_response_generation() -> None:
    """Test that agent generates valid response."""
    # Arrange
    agent = AgentWrapper(...)

    # Act
    response = await agent.generate_response(
        user_id=12345,
        question="Test question",
        conversation_history=[]
    )

    # Assert
    assert isinstance(response, str)
    assert len(response) > 0

# Integration test example
@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_persistence() -> None:
    """Test conversation persistence through repository."""
    # Integration of agent + repository
    pass

# E2E test example
@pytest.mark.e2e
@pytest.mark.discord
async def test_discord_bot_workflow() -> None:
    """Test complete Discord bot interaction."""
    # Full system integration
    pass
```

### Test Data Management

#### Test Factories
```python
# fixtures/factories.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from src.models.conversation import ConversationORM, MessageORM

class MessageFactory(SQLAlchemyModelFactory):
    class Meta:
        model = MessageORM
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    role = factory.Faker("random_element", elements=["user", "assistant"])
    content = factory.Faker("text")

class ConversationFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ConversationORM
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    user_id = factory.Faker("random_int", min=1, max=1000000)
    guild_id = factory.Faker("random_int", min=1, max=1000000)
```

### Test Cleanup

```python
@pytest.fixture(autouse=True)
async def cleanup_test_data(test_session: AsyncSession) -> None:
    """Clean up test data after each test."""
    yield
    # Clear all tables
    async with test_session.begin():
        for table in reversed(Base.metadata.sorted_tables):
            await test_session.execute(table.delete())
```

## Common Test Patterns

### Error Testing
```python
@pytest.mark.asyncio
async def test_rate_limit_exceeded_error() -> None:
    """Test that rate limit error is raised correctly."""
    # Arrange
    rate_limiter = RateLimiter(requests=1, window_seconds=1)
    user_id = 12345

    # First request should succeed
    assert await rate_limiter.check_rate_limit(user_id) is True

    # Second request should raise error
    with pytest.raises(RateLimitError):
        await rate_limiter.check_rate_limit(user_id)
```

### Async/Await Patterns
```python
@pytest.mark.asyncio
async def test_async_operations() -> None:
    """Test async operations with proper await."""
    # Arrange
    repository = SQLiteRepository(test_engine)

    # Act
    result = await repository.save_conversation(conversation)

    # Assert
    assert await repository.get_conversation(result.id) is not None
```

### Parameterized Testing
```python
@pytest.mark.parametrize("question,expected_length", [
    ("Curta", 1),
    ("Média", 10),
    ("Longa", 100),
])
@pytest.mark.asyncio
async def test_response_length_handling(question: str, expected_length: int) -> None:
    """Test response length handling with different input sizes."""
    # Act
    response = await agent.generate_response(
        user_id=12345,
        question=question * expected_length,
        conversation_history=[]
    )

    # Assert
    assert len(response) >= expected_length
```

### Performance Testing
```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_agent_response_performance() -> None:
    """Test that agent responses are generated within acceptable time."""
    import time

    # Arrange
    agent = AgentWrapper(...)
    start_time = time.time()

    # Act
    response = await agent.generate_response(
        user_id=12345,
        question="Performance test question",
        conversation_history=[]
    )

    # Assert
    end_time = time.time()
    assert (end_time - start_time) < 5.0  # 5 second timeout
    assert response is not None
```

### Context Managers
```python
@pytest.mark.asyncio
async def test_transaction_management() -> None:
    """Test database transaction management."""
    async with test_session.begin():
        # Perform operations within transaction
        conversation = await test_session.execute(
            select(ConversationORM).where(ConversationORM.user_id == 12345)
        )
        assert conversation is not None

    # Verify transaction was rolled back
    async with test_session.begin():
        result = await test_session.execute(
            select(ConversationORM).where(ConversationORM.user_id == 12345)
        )
        assert result is None
```

## Best Practices

1. **Test Independence**: Each test should be self-contained
2. **Descriptive Names**: Use clear, descriptive test names
3. **One Assertion per Test**: Focus on testing one behavior per test
4. **Use Fixtures**: Reuse common setup code through fixtures
5. **Mock External Dependencies**: Never call real APIs in tests
6. **Document Complex Tests**: Add docstrings for complex test scenarios
7. **Keep Tests Fast**: Unit tests should run in milliseconds
8. **Maintain Coverage**: Aim for 80%+ test coverage
9. **Use Brazilian Portuguese**: Test data should reflect Brazilian context
10. **Follow AAA Pattern**: Arrange, Act, Assert structure for all tests