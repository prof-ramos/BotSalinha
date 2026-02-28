# AGENTS.md — Configuration Management Module

**Parent:** [`../../AGENTS.md`](../../AGENTS.md)
**Generated:** 2026-02-27
**Last Updated:** 2026-02-27

---

## Purpose

The configuration management module (`src/config/`) handles all aspects of BotSalinha's configuration system, including environment variables, YAML configuration loading, Pydantic validation, and settings management. This module ensures type safety, validation, and centralized configuration access throughout the application.

---

## Key Files

| File | Purpose | Key Classes/Functions |
|------|---------|---------------------|
| [`settings.py`](settings.py) | Pydantic Settings with nested models | `Settings`, `DiscordConfig`, `OpenAIConfig`, `GoogleConfig`, `DatabaseConfig`, `RateLimitConfig`, `RetryConfig` |
| [`yaml_config.py`](yaml_config.py) | YAML config loader for agent/model settings | `load_yaml_config`, `YamlConfig`, `ModelConfig`, `PromptConfig`, `AgentBehaviorConfig` |
| [`mcp_config.py`](mcp_config.py) | MCP (Model Context Protocol) configuration | `MCPConfig`, `MCPServerConfig` |

---

## AI Agent Instructions

### For Configuration Management

When working with this configuration module, follow these patterns:

1. **Always use `get_settings()`** - Never call `Settings()` directly
2. **Environment Variable Naming**: Use double underscore for nested config (`DATABASE__URL`)
3. **Nested Priority**: Double underscore format has priority over flat format
4. **Provider Selection**: Choose provider in `config.yaml`, NOT via environment variable
5. **Singleton Pattern**: Settings are cached with `@lru_cache`

### Configuration Types

#### Environment Variables
- Support both flat (`DATABASE_URL`) and nested (`DATABASE__URL`) formats
- Nested format takes precedence when both exist
- All variables have sensible defaults
- See [`.env.example`](../../.env.example) for complete list

#### YAML Configuration
- Located in [`config.yaml`](../../config.yaml)
- Defines AI model provider, model ID, temperature
- Specifies active prompt file location
- Controls agent behavior flags
- Includes MCP (Model Context Protocol) server configurations
- Example structure:
```yaml
provider: openai
model: gpt-4o-mini
temperature: 0.1
prompt: prompt/prompt_v1.md
```

---

## Common Patterns

### Settings Access

```python
from src.config.settings import get_settings

# Correct way - uses cached singleton
settings = get_settings()

# Access nested configs
discord_config = settings.discord
openai_config = settings.openai
database_config = settings.database
```

### Environment Variable Hierarchy

1. Double underscore format (highest priority)
   ```python
   DATABASE__URL=sqlite:///custom/path.db
   ```

2. Flat format (lower priority)
   ```python
   DATABASE_URL=sqlite:///default/path.db
   ```

3. Default values in Pydantic models

### Configuration Validation

All configuration classes use Pydantic validation with type hints:
```python
class DatabaseConfig(BaseModel):
    url: str = Field(default="sqlite:///data/botsalinha.db")
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)
```

### Rate Limit Configuration

```python
class RateLimitConfig(BaseSettings):
    requests: int = Field(default=10, ge=1, le=100, description="Max requests per time window")
    window_seconds: int = Field(default=60, ge=1, le=3600, description="Time window in seconds")
```

### Retry Configuration

```python
class RetryConfig(BaseSettings):
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    delay_seconds: float = Field(default=1.0, ge=0.1, le=60, description="Initial delay")
    max_delay_seconds: float = Field(default=60.0, ge=1.0, le=300, description="Maximum delay")
    exponential_base: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff base")
```

---

## Dependencies

### Direct Dependencies

- **pydantic** - Type-safe data validation using Python type annotations
- **pydantic-settings** - Settings management with environment variable support
- **pyyaml** - YAML configuration file parsing
- **structlog** - Structured logging (imported by logger module)

### Transitive Dependencies

- **typing-extensions** - Extended type hints
- **python-dotenv** - Environment variable management (via settings)

### External API Dependencies

- **OpenAI** - AI model provider configuration
- **Google** - Alternative AI provider (Gemini) configuration

### Test Dependencies

- **pytest** - Testing framework
- **pytest-mock** - Mock utilities for testing
- **freezegun** - Time manipulation for testing
- **faker** - Fake data generation

---

## Configuration Loading Flow

1. **Environment Variables** → System environment
2. **YAML Config** → [`config.yaml`](../../config.yaml)
3. **Pydantic Models** → Type validation and defaults
4. **Cached Settings** → `get_settings()` singleton
5. **Runtime Access** → Configuration available throughout app

---

## Validation Rules

### Required Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | - | Discord bot token |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_MESSAGE_CONTENT_INTENT` | `true` | Enable message content intent |
| `COMMAND_PREFIX` | `!` | Command prefix |
| `GOOGLE_API_KEY` | - | Google API key |
| `HISTORY_RUNS` | `3` | Conversation history pairs |
| `RATE_LIMIT_REQUESTS` | `10` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit time window |
| `DATABASE__URL` | `sqlite:///data/botsalinha.db` | SQLite database path |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_FORMAT` | `json` | Log format |
| `APP_ENV` | `development` | Environment |
| `DEBUG` | `false` | Debug mode |
| `MAX_RETRIES` | `3` | Max retries |
| `RETRY_DELAY_SECONDS` | `1` | Retry delay |
| `RETRY_MAX_DELAY_SECONDS` | `60` | Max retry delay |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_MESSAGE_CONTENT_INTENT` | `true` | Enable message content intent |
| `COMMAND_PREFIX` | `!` | Command prefix |
| `GOOGLE_API_KEY` | - | Google API key |
| `HISTORY_RUNS` | `3` | Conversation history pairs |
| `RATE_LIMIT_REQUESTS` | `10` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit time window |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_FORMAT` | `json` | Log format |
| `APP_ENV` | `development` | Environment |
| `DEBUG` | `false` | Debug mode |
| `MAX_RETRIES` | `3` | Max retries |
| `RETRY_DELAY_SECONDS` | `1` | Retry delay |
| `RETRY_MAX_DELAY_SECONDS` | `60` | Max retry delay |

### Configuration Constraints

- All numeric fields have minimum/maximum constraints
- String fields have length limits where appropriate
- URL fields must be valid URLs
- API keys are validated as non-empty strings
- Rate limit values must be positive integers