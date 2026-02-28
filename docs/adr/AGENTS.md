# AGENTS.md — BotSalinha AI Agent Conventions

**Parent reference:** ../../AGENTS.md

<!-- ADR:START -->
<!-- ADR:GENERATED:2026-02-27T00:00:00Z -->
<!-- ADR:UPDATED:2026-02-27T00:00:00Z -->
<!-- ADR:STATUS:Accepted -->
<!-- ADR:CONTEXT:Defining agent conventions and AI integration patterns -->
<!-- ADR:DECISION:Establish standardized agent conventions -->
<!-- ADR:CONSEQUENCES:Provides consistent agent behavior, prompt management, and error handling -->

## Purpose

This document defines the AI agent conventions and integration patterns for BotSalinha. It establishes standards for:

- Agent configuration and prompt management
- Error handling and retry mechanisms
- Conversation history management
- Rate limiting integration
- Testing patterns for AI agents

## Key Files

| File | Purpose | Conventions |
| --- | --- | --- |
| `src/core/agent.py` | AgentWrapper implementation | Agno framework integration, OpenAI/Google |
| `src/config/yaml_config.py` | Configuration parsing | Pydantic validation, YAML loading |
| `src/utils/errors.py` | Exception hierarchy | BotSalinhaError base, APIError subclasses |
| `src/utils/retry.py` | Retry mechanisms | Exponential backoff, async_retry |
| `prompt/` | System prompts | Versioned prompts, active prompt selection |
| `tests/unit/` | Agent tests | Mock AI responses, prompt tests |
| `tests/integration/` | Integration tests | Full agent workflow |

## Status: Accepted

## Context

BotSalinha uses AI agents to provide contextual conversations about Brazilian law and public contest preparation.<br>The agent system must:

1. **Support multiple AI providers** (OpenAI gpt-4o-mini, Google Gemini)
2. **Maintain conversation history** for context-aware responses
3. **Implement rate limiting** per user and guild
4. **Handle API failures gracefully** with retry mechanisms
5. **Support prompt versioning** for different agent behaviors
6. **Be testable** without making real API calls

The Agno framework provides the foundation for agent integration, while custom components handle Discord-specific requirements.

## Decision

We will implement AI agent conventions using the following patterns:


### 1. AgentWrapper Pattern
- Centralized AI response generation in `AgentWrapper`
- Abstract provider interface supporting OpenAI and Google AI
- Configuration-driven provider selection via `config.yaml`
- Conversation history management with configurable depth


### 2. Prompt Management
- Versioned prompts in `prompt/` directory
- Active prompt selection via `config.yaml`
- Support for Markdown and JSON prompt formats
- Prompt validation and error handling


### 3. Error Handling Hierarchy
- `BotSalinhaError` as base exception class
- `APIError` for AI provider failures
- `RetryExhaustedError` for retry failures
- Structured logging with correlation IDs


### 4. Rate Limiting Integration
- Token bucket algorithm per user/guild
- Configurable request limits and time windows
- Integration with middleware layer
- Graceful degradation when limits exceeded


### 5. Testing Patterns
- Mock AI responses using `pytest-mock`
- Freeze conversation history for reproducible tests
- Test prompt loading and validation
- Test error scenarios and retry logic


## Consequences

### Positive
- **Consistent Agent Behavior**: All agents follow the same patterns for configuration, error handling, and retry logic
- **Easy Provider Switching**: Configuration-based provider selection without code changes
- **Maintainable Prompts**: Versioned prompts with easy switching and validation
- **Robust Error Handling**: Comprehensive error hierarchy and retry mechanisms
- **Testable Components**: All agent functionality can be tested without real API calls

### Negative
- **Configuration Complexity**: Multiple config files (`config.yaml`, environment variables) require careful management
- **Learning Curve**: Developers must understand the agent wrapper pattern and Agno framework
- **Prompt Management Overhead**: Versioned prompts require careful versioning and testing

### Neutral
- **Performance**: Async operations throughout, but API calls remain network-bound
- **Flexibility**: Extensible to new AI providers and prompt strategies
- **Dependency on Agno**: Framework-specific conventions may limit certain optimizations

## Subdirectories

### `prompt/`
Contains system prompts with different styles and complexity levels:

- `prompt_v1.md` - Simple, direct prompt (default)
- `prompt_v2.json` - Few-shot prompt with examples
- `prompt_v3.md` - Advanced chain-of-thought prompt

### `tests/unit/`
Agent-specific unit tests:

- `test_agent.py` - AgentWrapper behavior testing
- `test_prompt_loading.py` - Prompt validation and switching
- `test_error_handling.py` - Exception hierarchy testing

### `tests/integration/`
Integration tests for complete agent workflows:

- `test_agent_with_history.py` - Conversation history persistence
- `test_agent_rate_limiting.py` - Rate limiting integration
- `test_agent_discord_integration.py` - Full Discord workflow

## AI Agent Instructions

### For Developers

1. **Always use the AgentWrapper**: Never call AI providers directly; use `AgentWrapper.generate_response()`

2. **Configure via YAML**: Update `config.yaml` for provider settings, prompt selection, and agent behavior

3. **Handle Errors Gracefully**: Catch `APIError` and `RetryExhaustedError`; implement fallback behavior

4. **Test with Mocks**: Use `pytest-mock` to mock AI responses; never make real API calls in tests

5. **Log Everything**: Use structlog with correlation IDs for traceability

### For Prompt Designers

1. **Follow Prompt Conventions**: Use the established prompt format from existing versions

2. **Test Prompts**: Validate new prompts with `test_prompt_loading.py`

3. **Document Changes**: Update prompt version and document changes in version history

4. **Consider Context**: Design prompts to work with conversation history

### For Operations

1. **Monitor API Usage**: Track AI provider usage and costs

2. **Monitor Error Rates**: Set up alerts for high error rates from specific providers

3. **Prompt Rollback**: Be prepared to revert prompt changes if issues arise

4. **Configuration Validation**: Validate YAML configuration before deployment

## Common Patterns

### Creating a New Agent Configuration

```python
# src/config/settings.py
class AgentConfig(BaseModel):
    provider: str = Field(default="openai", description="AI provider: openai or google")
    model: str = Field(default="gpt-4o-mini", description="Model name")
    max_tokens: int = Field(default=1000, description="Max response tokens")
    temperature: float = Field(default=0.7, description="Response randomness")
    history_runs: int = Field(default=3, description="History context depth")
```

### Implementing Agent Response Generation

```python
# src/core/agent.py
class AgentWrapper:
    async def generate_response(
        self,
        messages: List[MessageSchema],
        user_id: int,
        guild_id: int
    ) -> str:
        # Rate limiting check
        if not self.rate_limiter.check_limit(user_id, guild_id):
            raise RateLimitError("Rate limit exceeded")

        # Prepare conversation with history
        conversation = self._prepare_conversation(messages)

        # Generate response with retry
        try:
            response = await self._call_ai_api(conversation)
            return response
        except APIError as e:
            log.error("ai_api_failed", error=str(e))
            raise
```

### Testing Agent Responses

```python
# tests/unit/test_agent.py
@pytest.mark.unit
async def test_generate_response_with_mock():
    # Mock AI response
    mock_response = "This is a test response"

    with patch('src.core.agent.AgentWrapper._call_ai_api') as mock_call:
        mock_call.return_value = mock_response

        agent = AgentWrapper(...)
        result = await agent.generate_response(
            messages=[test_message],
            user_id=123,
            guild_id=456
        )

        assert result == mock_response
        mock_call.assert_called_once()
```

### Prompt Loading and Validation

```python
# src/core/agent.py
class AgentWrapper:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.prompt = self._load_prompt(config.prompt_file)

    def _load_prompt(self, prompt_file: str) -> str:
        prompt_path = Path(__file__).parent.parent / "prompt" / prompt_file
        if not prompt_path.exists():
            raise ConfigurationError(f"Prompt file not found: {prompt_file}")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
```

## ADR:END -->