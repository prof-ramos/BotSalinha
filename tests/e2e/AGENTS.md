<!-- AGENTS:START -->
<!-- AGENTS:VERSION:1.0.0 -->
<!-- PARENT:../../AGENTS.md -->
<!-- GENERATED:2026-02-27 -->
<!-- UPDATED:2026-02-27 -->

# AGENTS.md — End-to-End Tests (tests/e2e/)

## Purpose

This directory contains end-to-end (E2E) tests for BotSalinha that verify complete system workflows including:
- Full Discord bot integration (commands, responses, history management)
- CLI chat mode functionality
- Complete AI agent request/response cycles
- Rate limiting behavior across system boundaries
- Database persistence and conversation history
- Error handling and recovery scenarios

**Key characteristics:**
- Test real user workflows from command to response
- May require 5-30 seconds per test (AI API calls, Discord API)
- Use `@pytest.mark.e2e` decorator
- Can access real secrets (Discord token, API keys)
- Integration with `@pytest.mark.slow` when appropriate

---

## Key Files

| File | Purpose | Testing Patterns |
| ----- | ------- | ---------------- |
| **`test_discord_bot.py`** | Full Discord command workflows | `@pytest.mark.e2e`, Discord API mocking, real command execution |
| **`test_cli_chat.py`** | CLI --chat mode testing | `@pytest.mark.e2e`, stdin/stdout capture, CLI argument parsing |
| **`test_ai_responses.py`** | Complete AI agent cycles | `@pytest.mark.e2e`, OpenAI/Gemini API mocking, response validation |
| **`test_history_management.py`** | Conversation persistence | `@pytest.mark.e2e`, database fixtures, history clearing/validation |
| **`test_rate_limiting.py`** | Rate limiting across boundaries | `@pytest.mark.e2e`, time-based tests, concurrent request scenarios |
| **`test_error_scenarios.py`** | Error handling and recovery | `@pytest.mark.e2e`, API failure simulation, retry behavior |
| **`test_full_workflow.py`** | Complete user journey | `@pytest.mark.slow`, `@pytest.mark.e2e`, end-to-end command chain |
| **`conftest.py`** | Shared E2E fixtures | Real secrets, Discord bot setup, test user accounts |

---

## AI Agent Instructions

### When Writing E2E Tests

1. **Focus on user workflows, not implementation details**
   ```python
   # Instead of testing internal methods:
   def test_ai_response_generation():
       result = agent.generate_response(question)  # Don't test this directly

   # Test the complete user journey:
   @pytest.mark.e2e
   def test_ask_command_full_workflow():
       # User types !ask question → Bot responds → History persists
   ```

2. **Use realistic Brazilian contest law content**
   ```python
   @pytest.mark.e2e
   def test_realistic_contest_question():
       question = "Qual é o prazo para recurso em processo administrativo disciplinar no regime jurídico único?"
       # Use real Brazilian law terminology
   ```

3. **Verify conversation context**
   ```python
   @pytest.mark.e2e
   async def test_conversation_context_maintained():
       # First question about constituição
       # Follow-up about mesmo artigo - should maintain context
       assert "artigo 37" in response  # Verify context carryover
   ```

### Test Data Patterns

```python
# Use realistic Brazilian names and contexts
CONTEST_QUESTIONS = [
    "Qual é o regime jurídico dos servidores públicos federais?",
    "Quais os princípios da administração pública?",
    "Como funciona a estabilidade de servidor estatutário?",
    "Quais as hipóteses de cassação de aposentadoria?",
    "Qual é o prazo para licitações no regime de pregão?"
]

# Use realistic Discord test scenarios
DISCORD_CONTEXTS = [
    {"guild_id": TEST_GUILD_ID, "channel_id": TEXT_CHANNEL_ID, "user_id": REGULAR_USER_ID},
    {"guild_id": TEST_GUILD_ID, "channel_id": PRIVATE_CHANNEL_ID, "user_id": VIP_USER_ID},
    {"guild_id": DIFFERENT_GUILD_ID, "channel_id": PUBLIC_CHANNEL_ID, "user_id": NEW_USER_ID}
]
```

---

## Testing Requirements

### Prerequisites

1. **Environment Setup** (secrets required)
   ```bash
   # Copy and configure real secrets for E2E testing
   cp ../../.env.example .env.e2e
   # Edit with real Discord token and OpenAI API key
   export BOT_ENV=e2e
   ```

2. **Test Accounts**
   - Test Discord server with bot invited
   - Test user accounts (regular, VIP, moderator roles)
   - Dedicated test channels for commands

3. **Timing Configuration**
   ```python
   # In conftest.py or fixtures
   @pytest.fixture(scope="session")
   def e2e_timeout():
       return 45  # E2E tests can take longer due to real API calls

   # Add to pytest.ini or conftest.py
   pytest_addoption = {
       "--e2e-secrets": help="Path to E2E secrets file"
   }
   ```

### Required Dependencies

```python
# conftest.py imports
import pytest
import pytest_asyncio
import asyncio
import freezegun
from unittest.mock import AsyncMock, MagicMock

# BotSalinha imports for E2E testing
from src.core.discord import BotSalinhaBot
from src.core.agent import AgentWrapper
from src.storage.sqlite_repository import SQLiteRepository
from src.config.settings import get_settings
```

---

## Common Patterns

### 1. Full Discord Command Testing

```python
@pytest.mark.e2e
@pytest.mark.discord
async def test_ask_command_integration(test_bot, test_channel, test_user):
    """Test complete !ask command flow"""
    # Setup
    await test_bot.wait_until_ready()

    # Simulate user typing !ask question
    ctx = MagicMock()
    ctx.guild.id = test_channel.guild.id
    ctx.channel.id = test_channel.id
    ctx.author.id = test_user.id
    ctx.message.content = "!ask Qual é o regime jurídico dos servidores públicos?"

    # Execute command
    response = await test_bot.ask(ctx)

    # Verify
    assert response is not None
    assert "Regime Jurídico Único" in response or "RJU" in response
    # Check history persisted
    history = await test_bot.agent.get_conversation_history(test_user.id)
    assert len(history) > 0
```

### 2. CLI Chat Mode Testing

```python
@pytest.mark.e2e
@pytest.mark.slow
def test_cli_chat_mode():
    """Test CLI --chat mode end-to-end"""
    from subprocess import run, PIPE
    import json

    # Start CLI chat
    process = run([
        "uv", "run", "bot.py", "--chat",
        "--token", TEST_DISCORD_TOKEN
    ], input="Qual é o princípio da impessoalidade?\n",
    capture_output=True, text=True, timeout=30)

    # Verify response
    output = process.stdout
    assert "impessoalidade" in output.lower()
    assert "interesse público" in output.lower()
    assert process.returncode == 0
```

### 3. AI Agent Cycle Testing

```python
@pytest.mark.e2e
async def test_ai_response_cycle():
    """Test complete AI agent request/response cycle"""
    # Setup agent with real credentials
    settings = get_settings()
    agent = AgentWrapper(
        api_key=settings.OPENAI_API_KEY,
        model="gpt-4o-mini",
        history_runs=2
    )

    # Test Brazilian contest question
    question = "Quais são os requisitos para aposentadoria especial?"
    response = await agent.generate_response(question)

    # Verify response quality and Brazilian context
    assert isinstance(response, str)
    assert len(response) > 50  # Substantial response
    assert "aposentadoria" in response.lower()
    # Should not contain generic non-Brazilian content
    assert "social security" not in response.lower()

    # Verify history persisted
    history = await agent.get_conversation_history(user_id=TEST_USER_ID)
    assert len(history) == 1  # One exchange completed
```

### 4. History Management Testing

```python
@pytest.mark.e2e
async def test_conversation_history_persistence():
    """Test conversation history across multiple requests"""
    user_id = TEST_USER_ID
    agent = AgentWrapper(settings.OPENAI_API_KEY, "gpt-4o-mini", history_runs=3)

    # First question
    q1 = "Qual é o artigo da constituição sobre administração pública?"
    r1 = await agent.generate_response(q1, user_id=user_id)

    # Second question building on first
    q2 = "Quais são os princípios desse artigo?"
    r2 = await agent.generate_response(q2, user_id=user_id)

    # Verify context maintained
    history = await agent.get_conversation_history(user_id=user_id)
    assert len(history) == 2  # Two exchanges
    assert "artigo 37" in r1.lower() or "administracao publica" in r1.lower()
    assert "princípios" in r2.lower() and "administracao" in r2.lower()

    # Test history clearing
    await agent.clear_conversation_history(user_id=user_id)
    cleared = await agent.get_conversation_history(user_id=user_id)
    assert len(cleared) == 0
```

### 5. Rate Limiting Testing

```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_rate_limiting_boundaries():
    """Test rate limiting across system boundaries"""
    from src.middleware.rate_limiter import RateLimiter

    limiter = RateLimiter(
        requests=3, window_seconds=60,
        requests_per_guild=10
    )

    user_id = TEST_USER_ID
    guild_id = TEST_GUILD_ID

    # Should allow within limits
    for i in range(3):
        allowed = await limiter.check_rate_limit(user_id, guild_id)
        assert allowed is True

    # Should exceed limit
    fourth_attempt = await limiter.check_rate_limit(user_id, guild_id)
    assert fourth_attempt is False

    # Test guild-level limiting
    different_user_id = DIFFERENT_USER_ID
    for i in range(10):
        allowed = await limiter.check_rate_limit(different_user_id, guild_id)
        assert allowed is True

    guild_limit = await limiter.check_rate_limit(different_user_id, guild_id)
    assert guild_limit is False
```

### 6. Error Scenario Testing

```python
@pytest.mark.e2e
async def test_api_error_handling():
    """Test behavior when AI API fails"""
    agent = AgentWrapper(
        api_key="invalid-key",  # Will cause API failure
        model="gpt-4o-mini",
        history_runs=2
    )

    question = "Qual é o regime jurídico?"

    # Should handle gracefully with retry logic
    with pytest.raises(APIError) as exc_info:
        await agent.generate_response(question)

    # Verify proper error structure
    error = exc_info.value
    assert "API Error" in str(error)
    assert error.status_code == 401  # Unauthorized
```

### 7. Full Workflow Testing

```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_complete_user_journey():
    """Test complete user journey from command to response to history"""
    # Setup
    bot = await setup_test_bot()
    user = await setup_test_user()

    # Step 1: User asks initial question
    response1 = await bot.ask_command_handler(user, "!ask Qual é o regime jurídico?")
    assert "Regime Jurídico Único" in response1

    # Step 2: User asks follow-up question
    response2 = await bot.ask_command_handler(user, "!ask E sobre estabilidade?")
    assert "estabilidade" in response2
    assert "estatutário" in response2

    # Step 3: User clears history
    clear_response = await bot.clear_command_handler(user, "!limpar")
    assert "histórico" in clear_response.lower()

    # Step 4: User asks new question (fresh context)
    response4 = await bot.ask_command_handler(user, "!ask Qual é o princípio da moralidade?")
    assert "moralidade" in response4
    assert "interesse público" in response4

    # Verify all interactions recorded
    history = await bot.agent.get_conversation_history(user.id)
    assert len(history) == 3  # Two asks + one clear
```

---

## E2E Test Execution

```bash
# Run all E2E tests
uv run pytest tests/e2e/ -v

# Run specific E2E test
uv run pytest tests/e2e/test_discord_bot.py::test_ask_command_full_workflow -v

# Run E2E tests with real secrets
uv run pytest tests/e2e/ --env-file .env.e2e -v

# Run with coverage (E2E tests count toward coverage)
uv run pytest tests/e2e/ --cov=src/core --cov-report=term-missing

# Run slow E2E tests only
uv run pytest tests/e2e/ -m "e2e and slow" -v

# Run in parallel (be careful with rate limits)
uv run pytest tests/e2e/ --numprocesses=2 -v
```

**Note:** E2E tests should be run sparingly as they use real API calls and can count against rate limits. Consider running them in CI/CD but not on every local commit.

<!-- AGENTS:END -->