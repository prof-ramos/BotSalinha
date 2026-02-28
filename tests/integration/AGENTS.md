<!-- Generated: 2026-02-27 | Updated: 2026-02-27 | Parent: ../../AGENTS.md -->

# AGENTS.md — Integration Tests — BotSalinha

## Purpose

This directory contains **integration tests** for BotSalinha, focusing on multi-component interactions and real-world scenarios. Integration tests verify that components work together correctly, testing the boundaries between units and simulating production workflows.

### Key Integration Targets
- **Agent + Repository Integration**: AI agent with conversation persistence
- **Discord Bot + Rate Limiter**: Command handling with rate limiting
- **Config Loading + Validation**: YAML and environment configuration
- **MCP Tools + Agent**: AI agent with MCP tool integration
- **Database Operations**: SQLAlchemy async with Alembic migrations

## File Structure

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `__init__.py` | Módulo de integração (atualmente vazio) | `echo "Integration tests"` |
| `conftest.py` | Fixtures compartilhadas (definido em `../conftest.py`) | `pytest tests/` |

## Key Files and Integration Patterns

### Integration Test Patterns

| Component | Integration Target | Test Focus |
|-----------|-------------------|------------|
| `AgentWrapper` | `SQLiteRepository` | Conversation persistence, history management |
| `BotSalinhaBot` | `RateLimiter` | Command rate limiting per user/guild |
| `Settings` | `yaml_config` | Configuration loading and validation |
| `MCPToolsManager` | `AgentWrapper` | Tool integration with AI agent |
| `ConversationORM` | `MessageRepository` | Database relationship integrity |

### Integration Test Structure

```python
# Integration tests follow this pattern:
@pytest.mark.integration
async def test_integration_scenario(test_settings, conversation_repository):
    # 1. Setup real components (no mocking of internal dependencies)
    # 2. Exercise component interactions
    # 3. Verify integration behavior
    # 4. Test error handling and edge cases

    # Example: Agent + Repository integration
    agent = AgentWrapper(repository=conversation_repository)
    response = await agent.generate_response(
        prompt="Pergunta legal",
        conversation_id="test-conv",
        user_id="test-user"
    )

    # Verify conversation was persisted
    assert len(response) > 10
    assert await conversation_repository.count_conversations() >= 1
```

## AI Agent Instructions

### Integration Test Guidelines

1. **Component Interaction Tests:**
   - Test real interactions between components, not mocks
   - Mock only external APIs (Discord, OpenAI, Google)
   - Use in-memory SQLite for fast database operations
   - Test error scenarios and recovery paths

2. **Rate Limiting Integration:**
   ```python
   @pytest.mark.integration
   async def test_rate_limiter_integration(rate_limiter, mock_discord_context):
       # Test rate limiting across multiple commands
       for _ in range(10):
           await rate_limiter.check_rate_limit(
               user_id=mock_discord_context.author.id,
               guild_id=mock_discord_context.guild.id
           )
       # Verify rate limiting works correctly
   ```

3. **Repository Integration:**
   ```python
   @pytest.mark.integration
   @pytest.mark.database
   async def test_agent_repository_integration(agent_wrapper, conversation_repository):
       # Test conversation persistence and retrieval
       conv = await conversation_repository.create_conversation(
           ConversationCreate(
               user_id="123",
               guild_id="456",
               channel_id="789"
           )
       )
       # Verify agent uses repository correctly
       response = await agent_wrapper.generate_response(
           prompt="Test question",
           conversation_id=str(conv.id),
           user_id="123"
       )
   ```

4. **Configuration Integration:**
   ```python
   @pytest.mark.integration
   async def test_settings_yaml_integration(test_settings):
       # Test settings loading with YAML config
       from src.config.yaml_config import yaml_config
       assert yaml_config.prompt_content is not None
       assert yaml_config.model_provider is not None
   ```

## Testing Requirements

### Markers Disponíveis
```python
@pytest.mark.integration   # Multi-component integration tests (padrão)
@pytest.mark.database     # Tests requiring database operations
@pytest.mark.discord      # Tests requiring Discord API mocking
@pytest.mark.ai_provider  # Tests requiring OpenAI/Google API mocking
@pytest.mark.slow         # Tests taking > 5 seconds
@pytest.mark.mcp          # Tests requiring MCP tools
```

### Key Integration Test Requirements

1. **Performance Requirements:**
   - Tests should complete in 1-5 seconds (excluding slow tests)
   - Use in-memory SQLite for fast database operations
   - Mock external APIs to avoid rate limits

2. **Data Management:**
   - Use fixtures from `tests/conftest.py` for consistent setup
   - Clean up database state after each test
   - Use deterministic Faker seeding for reproducible data

3. **Error Scenarios:**
   - Test API failures with `mock_ai_response_error`
   - Test rate limiting with `rate_limiter`
   - Test database connection failures
   - Test configuration validation errors

### Fixtures Essenciais

| Fixture | Uso Principal |
|---------|-------------|
| `test_settings` | Configuração de ambiente para testes |
| `conversation_repository` | Repositório SQLite em memória |
| `message_repository` | Repositório de mensagens |
| `agent_wrapper` | Agente com repository integrado |
| `rate_limiter` | Limitador de taxa configurado |
| `mock_discord_context` | Contexto Discord para testes |
| `mock_ai_response` | Resposta AI para testes sem API |

## Common Integration Test Patterns

### Agent + Repository Integration Test
```python
@pytest.mark.integration
async def test_conversation_persistence_integration(
    conversation_repository,
    agent_wrapper,
    test_user_id,
    test_guild_id
):
    """Test that conversations are properly persisted and retrieved."""

    # Create a conversation
    conv = await create_test_conversation(
        conversation_repository,
        user_id=test_user_id,
        guild_id=test_guild_id
    )

    # Generate response using agent
    response = await agent_wrapper.generate_response(
        prompt="Qual é o prazo de prescrição?",
        conversation_id=str(conv.id),
        user_id=test_user_id
    )

    # Verify conversation was persisted with response
    conversations = await conversation_repository.get_conversations_by_user(
        user_id=test_user_id,
        guild_id=test_guild_id
    )
    assert len(conversations) >= 1
```

### Discord Bot + Rate Limiter Integration
```python
@pytest.mark.integration
async def test_command_rate_limiting_integration(
    rate_limiter,
    mock_discord_context
):
    """Test that commands respect rate limits."""

    user_id = str(mock_discord_context.author.id)
    guild_id = str(mock_discord_context.guild.id)

    # Should pass within rate limits
    for i in range(10):
        can_proceed = await rate_limiter.check_rate_limit(user_id, guild_id)
        assert can_proceed is True

    # Should fail after exceeding limits
    can_proceed = await rate_limiter.check_rate_limit(user_id, guild_id)
    assert can_proceed is False
```

### MCP Tools Integration Test
```python
@pytest.mark.integration
@pytest.mark.mcp
async def test_mcp_tools_integration(agent_wrapper):
    """Test that MCP tools work with the AI agent."""

    # Mock MCP tools integration
    # This test would verify that the agent can use MCP tools
    # when generating responses

    response = await agent_wrapper.generate_response(
        prompt="Usando ferramentas MCP para pesquisa",
        conversation_id="test-mcp-conv",
        user_id="test-user"
    )

    # Verify tool integration worked
    assert len(response) > 50
    assert "ferramentas" in response.lower()
```

## Running Integration Tests

### Commandos para Execução
```bash
# Run all integration tests
uv run pytest tests/integration/

# Run specific integration test
uv run pytest tests/integration/ -k "test_conversation_persistence_integration"

# Run with coverage
uv run pytest tests/integration/ --cov=src/core/ --cov-report=html

# Run in parallel
uv run pytest tests/integration/ --numprocesses=auto
```

### Test Coverage Requirements
- **Minimum coverage:** 70% (enforced in CI)
- **Integration tests must cover:**
  - Agent + Repository interactions
  - Rate limiting scenarios
  - Configuration loading
  - Error handling paths
  - Database transaction integrity

## Integration Test Guidelines

### Test Organization
- Group related integration tests in logical files
- Use descriptive test names that indicate integration scope
- Maintain test independence with proper setup/teardown
- Document complex test scenarios in docstrings

### Mocking Strategy
- **Mock external APIs**: Discord, OpenAI, Google (use fixtures)
- **Don't mock internal dependencies**: Agents, repositories, middleware
- **Use test doubles for slow operations**: Database, network calls
- **Verify mock interactions** where appropriate

### Performance Considerations
- Keep integration tests fast (1-5 seconds typical)
- Use in-memory SQLite for database tests
- Reuse fixtures to avoid duplication
- Parallelize independent integration tests