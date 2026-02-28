<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->

# AGENTS.md — BotSalinha Implementation Plans

## Purpose

This directory contains implementation plans and strategies from ralplan consensus workflow for BotSalinha. Each plan follows a structured approach with problem statements, proposed solutions, acceptance criteria, and architecture considerations.

### Key Components
- **Problem Statement:** Clear identification of what needs to be implemented
- **Proposed Solution:** Architectural approach and implementation strategy
- **Acceptance Criteria:** Measurable criteria for completion
- **Architecture Considerations:** Technical decisions and trade-offs
- **Testing Strategy:** Verification approach and test coverage

## Parent Reference

This documentation extends the main AGENTS.md file located at `../../AGENTS.md`, which provides comprehensive project overview, code conventions, and development guidelines.

## Implementation Plans

### 1. Multi-Model Alignment (arquivado em 2026-02-28)

**Problem Statement:** Standardize runtime, tests, and documentation for official support of both `openai` and `google` providers, with `openai` as default and `config.yaml` as single source of truth.

**Proposed Solution:**
- Unified configuration contract using Pydantic models
- Startup validation for invalid providers or missing API keys
- Standardized test suite with consistent markers and fixtures
- Single narrative documentation with provider switching examples

**Acceptance Criteria:**
- Bot starts with both `openai` and `google` by changing only `config.yaml`
- Invalid provider or missing API key fails startup with actionable error messages
- Test suite passes with consistent markers/fixtures
- Documentation and configuration examples are consistent

**Architecture Considerations:**
- Pydantic Settings with `SettingsConfigDict`
- Pydantic v2 validation with `Literal`/`field_validator`
- Pytest markers registration and selection
- Configuration validation at startup

**Testing Strategy:**
- Unit tests for configuration validation
- Integration tests for provider switching
- Smoke tests with both providers
- Verification: `uv run pytest -k "settings or yaml_config or config" -v`

### 2. MCP Integration ([mcp-integration.md](./mcp-integration.md))

**Problem Statement:** Add MCP (Model Context Protocol) server support to BotSalinha to enable external tools and API access through standardized interface.

**Proposed Solution:**
- Pydantic models for MCP configuration (consistent with existing `yaml_config.py`)
- Support for `stdio`, `sse`, and `streamable-http` transports
- Lazy initialization via `MCPToolsManager`
- Optional tool name prefix to avoid conflicts

**Acceptance Criteria:**
- MCP servers can be configured in `config.yaml`
- Tools are available to the AI agent when MCP is enabled
- MCP failures don't prevent bot operation
- Environment variables are properly passed to servers

**Architecture Considerations:**
- Pydantic models for configuration validation
- Lazy initialization for performance
- Non-blocking design - MCP failures don't break bot
- Tool name prefixes for conflict resolution

**Testing Strategy:**
- Configuration validation tests
- MCP server connection tests
- Tool availability verification
- Error handling and recovery tests
- Verification: Manual testing with MCP server examples

## Common Patterns

### Configuration Management
- Use Pydantic models for all configuration
- Validate at startup with actionable error messages
- Keep credentials in environment variables
- Use YAML for configuration files

### Testing Approach
- Unit tests for isolated components
- Integration tests for multi-component workflows
- E2E tests for complete scenarios
- Mock all external APIs (Discord, OpenAI, Google)
- Use fixtures from `tests/conftest.py`

### Error Handling
- Custom exception hierarchy inheriting from `BotSalinhaError`
- Structured logging with context
- Graceful degradation for non-critical failures
- Clear error messages for users

### Code Organization
- Repository pattern for database access
- Dependency injection for services
- Async/await throughout for I/O operations
- Clear separation of concerns between modules

## Development Workflow

### Creating New Plans
1. Define clear problem statement
2. Propose solution with architecture considerations
3. Define measurable acceptance criteria
4. Outline testing strategy
5. Include verification commands

### Implementation Checklist
- [ ] Update configuration models
- [ ] Implement core functionality
- [ ] Add comprehensive tests
- [ ] Update documentation
- [ ] Verify acceptance criteria
- [ ] Run full test suite
- [ ] Check linting and type hints

## Key Files Reference

| File | Purpose | Related Plan |
|------|---------|--------------|
| `src/config/yaml_config.py` | Configuration loading and validation | Multi-Model Alignment |
| `src/config/mcp_config.py` | MCP configuration models | MCP Integration |
| `src/core/agent.py` | Agent wrapper with MCP support | MCP Integration |
| `src/config/settings.py` | Environment variable settings | Multi-Model Alignment |
| `config.yaml` | Main configuration file | Both plans |

## Verification Commands

For Multi-Model Alignment:
```bash
uv run pytest -k "settings or yaml_config or config" -v
uv run pytest -m "not slow" -v
uv run ruff check . && uv run mypy src && uv run pytest
```

For MCP Integration:
```bash
uv run pytest -k "mcp or agent" -v
uv run mypy src/config/mcp_config.py
uv run mypy src/core/agent.py
```

## Status Updates

- **Multi-Model Alignment:** ✅ Complete (all tasks marked done)
- **MCP Integration:** 🚧 In progress (architecture decisions made, implementation pending)

## Dependencies

### External Tools
- **Agno AI Agent Framework** - Core AI functionality
- **discord.py** - Discord API integration
- **Pydantic** - Data validation and settings
- **SQLAlchemy** - Database ORM
- **Alembic** - Database migrations

### Development Tools
- **pytest** - Testing framework
- **ruff** - Linting and formatting
- **mypy** - Type checking
- **pre-commit** - Code quality hooks
- **uv** - Package management
