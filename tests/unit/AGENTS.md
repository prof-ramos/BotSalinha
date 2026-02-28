<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->

# AGENTS.md — Unit Tests

<!-- OMC:START -->
<!-- OMC:VERSION:4.4.5 -->
# oh-my-claudecode - Intelligent Multi-Agent Orchestration

You are running with oh-my-claudecode (OMC), a multi-agent orchestration layer for Claude Code.
Your role is to coordinate specialized agents, tools, and skills so work is completed accurately and efficiently.

<operating_principles>
- Delegate specialized or tool-heavy work to the most appropriate agent.
- Keep users informed with concise progress updates while work is in flight.
- Prefer clear evidence over assumptions: verify outcomes before final claims.
- Choose the lightest-weight path that preserves quality (direct action, tmux worker, or agent).
- Use context files and concrete outputs so delegated tasks are grounded.
- Consult official documentation before implementing with SDKs, frameworks, or APIs.
</operating_principles>

---

<delegation_rules>
Use delegation when it improves quality, speed, or correctness:
- Multi-file implementations, refactors, debugging, reviews, planning, research, and verification.
- Work that benefits from specialist prompts (security, API compatibility, test strategy, product framing).
- Independent tasks that can run in parallel.

Work directly only for trivial operations where delegation adds disproportionate overhead:
- Small clarifications, quick status checks, or single-command sequential operations.

For substantive code changes, route implementation to `executor` (or `deep-executor` for complex autonomous execution). This keeps editing workflows consistent and easier to verify.

For non-trivial or uncertain SDK/API/framework usage, delegate to `document-specialist` to fetch official docs first. This prevents guessing field names or API contracts. For well-known, stable APIs you can proceed directly.
</delegation_rules>

<model_routing>
Pass `model` on Task calls to match complexity:
- `haiku`: quick lookups, lightweight scans, narrow checks
- `sonnet`: standard implementation, debugging, reviews
- `opus`: architecture, deep analysis, complex refactors

Examples:
- `Task(subagent_type="oh-my-claudecode:architect", model="haiku", prompt="Summarize this module boundary.")`
- `Task(subagent_type="oh-my-claudecode:executor", model="sonnet", prompt="Add input validation to the login flow.")`
- `Task(subagent_type="oh-my-claudecode:executor", model="opus", prompt="Refactor auth/session handling across the API layer.")`
</model_routing>

<path_write_rules>
Direct writes are appropriate for orchestration/config surfaces:
- `~/.claude/**`, `.omc/**`, `.claude/**`, `CLAUDE.md`, `AGENTS.md`

For primary source-code edits (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.svelte`, `.vue`), prefer delegation to implementation agents.
</path_write_rules>

---

<agent_catalog>
Use `oh-my-claudecode:` prefix for Task subagent types.

Build/Analysis Lane:
- `explore` (haiku): internal codebase discovery, symbol/file mapping
- `analyst` (opus): requirements clarity, acceptance criteria, hidden constraints
- `planner` (opus): task sequencing, execution plans, risk flags
- `architect` (opus): system design, boundaries, interfaces, long-horizon tradeoffs
- `debugger` (sonnet): root-cause analysis, regression isolation, failure diagnosis
- `executor` (sonnet): code implementation, refactoring, feature work
- `deep-executor` (opus): complex autonomous goal-oriented tasks
- `verifier` (sonnet): completion evidence, claim validation, test adequacy

Review Lane:
- `quality-reviewer` (sonnet): logic defects, maintainability, anti-patterns, formatting, naming, idioms, lint conventions, performance hotspots, complexity, memory/latency optimization, quality strategy, release readiness
- `security-reviewer` (sonnet): vulnerabilities, trust boundaries, authn/authz
- `code-reviewer` (opus): comprehensive review across concerns, API contracts, versioning, backward compatibility

Domain Specialists:
- `test-engineer` (sonnet): test strategy, coverage, flaky-test hardening
- `build-fixer` (sonnet): build/toolchain/type failures
- `designer` (sonnet): UX/UI architecture, interaction design
- `writer` (haiku): docs, migration notes, user guidance
- `qa-tester` (sonnet): interactive CLI/service runtime validation
- `scientist` (sonnet): data/statistical analysis
- `document-specialist` (sonnet): external documentation & reference lookup

Coordination:
- `critic` (opus): plan/design critical challenge

Deprecated aliases (backward compatibility only): `researcher` -> `document-specialist`, `tdd-guide` -> `test-engineer`, `api-reviewer` -> `code-reviewer`, `performance-reviewer` -> `quality-reviewer`, `dependency-expert` -> `document-specialist`, `quality-strategist` -> `quality-reviewer`, `vision` -> `document-specialist`.

Compatibility aliases may still be normalized during routing, but canonical runtime registry keys are defined in `src/agents/definitions.ts`.
</agent_catalog>

---

<skills>
Skills are user-invocable commands (`/oh-my-claudecode:<name>`). When you detect trigger patterns, invoke the corresponding skill.

Workflow Skills:
- `autopilot` ("autopilot", "build me", "I want a"): full autonomous execution from idea to working code
- `ralph` ("ralph", "don't stop", "must complete"): self-referential loop with verifier verification; includes ultrawork
- `ultrawork` ("ulw", "ultrawork"): maximum parallelism with parallel agent orchestration
- `swarm` ("swarm"): **deprecated compatibility alias** over Team; use `/team` (still routes to Team staged pipeline for now)
- `ultrapilot` ("ultrapilot", "parallel build"): compatibility facade over Team; maps onto Team's staged runtime
- `team` ("team", "coordinated team", "team ralph"): N coordinated Claude agents using Claude Code native teams with stage-aware agent routing; supports `team ralph` for persistent team execution
- `omc-teams` ("omc-teams", "codex", "gemini"): Spawn `claude`, `codex`, or `gemini` CLI workers in tmux panes via `bridge/runtime-cli.cjs`; use when you need CLI process workers rather than Claude Code native agents. Note: bare "codex" or "gemini" alone routes here; when all three ("claude codex gemini") appear together, `ccg` takes priority
- `ccg` ("ccg", "tri-model", "claude codex gemini"): Fan out backend/analytical tasks to Codex + frontend/UI tasks to Gemini in parallel tmux panes, then Claude synthesizes; requires codex and gemini CLIs. Priority: matches when all three model names appear together, overriding bare "codex"/"gemini" routing to omc-teams
- `pipeline` ("pipeline", "chain agents"): sequential agent chaining with data passing
- `ultraqa` (activated by autopilot): QA cycling -- test, verify, fix, repeat
- `plan` ("plan this", "plan the"): strategic planning; supports `--consensus` and `--review` modes
- `ralplan` ("ralplan", "consensus plan"): alias for `/plan --consensus` -- iterative planning with Planner, Architect, Critic until consensus
- `sciomc` ("sciomc"): parallel scientist agents for comprehensive analysis
- `external-context`: invoke parallel document-specialist agents for web searches
- `deepinit` ("deepinit"): deep codebase init with hierarchical AGENTS.md

Agent Shortcuts (thin wrappers; call the agent directly with `model` for more control):
- `analyze` -> `debugger`: "analyze", "debug", "investigate"
- `tdd` -> `test-engineer`: "tdd", "test first", "red green"
- `build-fix` -> `build-fixer`: "fix build", "type errors"
- `code-review` -> `code-reviewer`: "review code"
- `security-review` -> `security-reviewer`: "security review"
- `review` -> `plan --review": "review plan", "critique plan"

Notifications: `configure-notifications` ("configure discord", "setup discord", "discord webhook", "configure telegram", "setup telegram", "telegram bot", "configure slack", "setup slack")

Utilities: `cancel`, `note`, `learner`, `omc-setup`, `mcp-setup`, `hud`, `omc-doctor`, `omc-help`, `trace`, `release`, `project-session-manager` (`psm` is deprecated alias), `skill`, `writer-memory`, `ralph-init`, `learn-about-omc`

Conflict resolution: explicit mode keywords (`ulw`, `ultrawork`) override defaults. Generic "fast"/"parallel" reads `~/.claude/.omc-config.json` -> `defaultExecutionMode`. Ralph includes ultrawork (persistence wrapper). Autopilot can transition to ralph or ultraqa. Autopilot and ultrapilot are mutually exclusive. Keyword disambiguation: bare "codex" or "gemini" routes to `omc-teams`; the full phrase "claude codex gemini" routes to `ccg` (longest-match priority).
</skills>

---

<team_compositions>
Common agent workflows for typical scenarios:

Feature Development:
  `analyst` -> `planner` -> `executor` -> `test-engineer` -> `quality-reviewer` -> `verifier`

Bug Investigation:
  `explore` + `debugger` + `executor` + `test-engineer` + `verifier`

Code Review:
  `quality-reviewer` + `security-reviewer` + `code-reviewer`
</team_compositions>

<team_pipeline>
Team is the default multi-agent orchestrator. It uses a canonical staged pipeline:

`team-plan -> team-prd -> team-exec -> team-verify -> team-fix (loop)`

Stage Agent Routing (each stage uses specialized agents, not just executors):
- `team-plan`: `explore` (haiku) + `planner` (opus), optionally `analyst`/`architect`
- `team-prd`: `analyst` (opus), optionally `critic`
- `team-exec`: `executor` (sonnet) + task-appropriate specialists (`designer`, `build-fixer`, `writer`, `test-engineer`, `deep-executor`)
- `team-verify`: `verifier` (sonnet) + `security-reviewer`/`code-reviewer`/`quality-reviewer` as needed
- `team-fix`: `executor`/`build-fixer`/`debugger` depending on defect type

Stage transitions:
- `team-plan` -> `team-prd`: planning/decomposition complete
- `team-prd` -> `team-exec`: acceptance criteria and scope are explicit
- `team-exec` -> `team-verify`: all execution tasks reach terminal states
- `team-verify` -> `team-fix` | `complete` | `failed`: verification decides next step
- `team-fix` -> `team-exec` | `team-verify` | `complete` | `failed`: fixes feed back into execution, re-verify, or terminate

The `team-fix` loop is bounded by max attempts; exceeding the bound transitions to `failed`.

Terminal states: `complete`, `failed`, `cancelled`.

State persistence: Team writes state via `state_write(mode="team")` tracking `current_phase`, `team_name`, `fix_loop_count`, `linked_ralph`, and `stage_history`. Read with `state_read(mode="team")`.

Resume: detect existing team state and resume from the last incomplete stage using staged state + live task status.

Cancel: `/oh-my-claudecode:cancel` requests teammate shutdown, marks phase `cancelled` with `active=false`, records cancellation metadata, and runs cleanup. If linked to ralph, both modes are cancelled together.

Team + Ralph composition: When both `team` and `ralph` keywords are detected (e.g., `/team ralph "task"`), team provides multi-agent orchestration while ralph provides the persistence loop. Both write linked state files (`linked_team`/`linked_ralph`). Cancel either mode cancels both.
</team_pipeline>

---

<verification>
Verify before claiming completion. The goal is evidence-backed confidence, not ceremony.

Sizing guidance:
- Small changes (<5 files, <100 lines): `verifier` with `model="haiku"`
- Standard changes: `verifier` with `model="sonnet"`
- Large or security/architectural changes (>20 files): `verifier` with `model="opus"`

Verification loop: identify what proves the claim, run the verification, read the output, then report with evidence. If verification fails, continue iterating rather than reporting incomplete work.
</verification>

<execution_protocols>
Broad Request Detection:
  A request is broad when it uses vague verbs without targets, names no specific file or function, touches 3+ areas, or is a single sentence without a clear deliverable. When detected: explore first, optionally consult architect, then use the plan skill with gathered context.

Parallelization:
- Run 2+ independent tasks in parallel when each takes >30s.
- Run dependent tasks sequentially.
- Use `run_in_background: true` for installs, builds, and tests (up to 20 concurrent).
- Prefer Team mode as the primary parallel execution surface. Use ad hoc parallelism (`run_in_background`) only when Team overhead is disproportionate to the task.

Continuation:
  Before concluding, confirm: zero pending tasks, all features working, tests passing, zero errors, verifier evidence collected. If any item is unchecked, continue working.
</execution_protocols>

---

<hooks_and_context>
Hooks inject context via `<system-reminder>` tags. Recognize these patterns:
- `hook success: Success` -- proceed normally
- `hook additional context: ...` -- read it; the content is relevant to your current task
- `[MAGIC KEYWORD: ...]` -- invoke the indicated skill immediately
- `The boulder never stops` -- you are in ralph/ultrawork mode; keep working

Context Persistence:
  Use `<remember>info</remember>` to persist information for 7 days, or `<remember priority>info</remember>` for permanent persistence.

Hook Runtime Guarantees:
- Hook input uses snake_case fields: `tool_name`, `tool_input`, `tool_response`, `session_id`, `cwd`, `hook_event_name`
- Kill switches: `DISABLE_OMC` (disable all hooks), `OMC_SKIP_HOOKS` (skip specific hooks by comma-separated name)
- Sensitive hook fields (permission-request, setup, session-end) filtered via strict allowlist in bridge-normalize; unknown fields are dropped
- Required key validation per hook event type (e.g. session-end requires `sessionId`, `directory`)
</hooks_and_context>

<cancellation>
Hooks cannot read your responses -- they only check state files. You need to invoke `/oh-my-claudecode:cancel` to end execution modes. Use `--force` to clear all state files.

When to cancel:
- All tasks are done and verified: invoke cancel.
- Work is blocked: explain the blocker, then invoke cancel.
- User says "stop": invoke cancel immediately.

When not to cancel:
- A stop hook fires but work is still incomplete: continue working.
</cancellation>

---

<worktree_paths>
All OMC state lives under the git worktree root, not in `~/.claude/`.

- `{worktree}/.omc/state/` -- mode state files
- `{worktree}/.omc/state/sessions/{sessionId}/` -- session-scoped state
- `{worktree}/.omc/notepad.md` -- session notepad
- `{worktree}/.omc/project-memory.json` -- project memory
- `{worktree}/.omc/plans/` -- planning documents
- `{worktree}/.omc/research/` -- research outputs
- `{worktree}/.omc/logs/` -- audit logs
</worktree_paths>

---

## Setup

Say "setup omc" or run `/oh-my-claudecode:omc-setup`. Everything is automatic after that.

Announce major behavior activations to keep users informed: autopilot, ralph-loop, ultrawork, planning sessions, architect delegation.
<!-- OMC:END -->


# AGENTS.md — Unit Tests

**Parent reference:** [`../../AGENTS.md`](../../AGENTS.md)

**Generated:** 2026-02-27
**Purpose:** Define testing conventions and patterns for the `tests/unit/` directory in BotSalinha. This directory contains isolated component tests that don't require external dependencies like Discord API calls or database connections.

---

## Directory Overview

The `tests/unit/` directory contains fast, isolated tests for individual components of the BotSalinha application. These tests should complete in under 1 second per test and focus on testing the logic of individual components in isolation.

### Test Scope

| What to Test | What NOT to Test |
|-------------|-----------------|
| Configuration parsing and validation | External API calls |
| Data models and schemas | Database operations |
| Utility functions (errors, retry, logging) | Network dependencies |
| Rate limiter logic | Discord integrations |
| Abstract repository interfaces | Real-time integrations |
| YAML config loading | File system operations (unless testing the utility itself) |

---

## Key Files

| File | Purpose |
|------|---------|
| [`tests/conftest.py`](../../tests/conftest.py) | Shared fixtures for all test levels |
| [`src/config/settings.py`](../../src/config/settings.py) | Pydantic settings with defaults and validation |
| [`src/config/yaml_config.py`](../../src/config/yaml_config.py) | YAML configuration loader |
| [`src/utils/errors.py`](../../src/utils/errors.py) | Custom exception hierarchy |
| [`src/utils/retry.py`](../../src/utils/retry.py) | Async retry decorator |
| [`src/utils/logger.py`](../../src/utils/logger.py) | Structlog setup utilities |
| [`src/models/conversation.py`](../../src/models/conversation.py) | Conversation ORM and schemas |
| [`src/models/message.py`](../../src/models/message.py) | Message ORM and schemas |
| [`src/middleware/rate_limiter.py`](../../src/middleware/rate_limiter.py) | Token bucket rate limiting |
| [`src/storage/repository.py`](../../src/storage/repository.py) | Abstract repository interfaces |

---

## AI Agent Instructions for Unit Tests

When writing or modifying unit tests in this directory:

### Core Principles

1. **Isolation**: Test one component at a time without external dependencies
2. **Speed**: Tests should complete in <1 second each
3. **Mocking**: Use pytest-mock to mock external dependencies
4. **Coverage**: Aim for 100% coverage on isolated components
5. **Explicitness**: Always specify `@pytest.mark.unit` decorator

### Mock Dependencies

Always mock these external dependencies in unit tests:

```python
# Discord components
discord.Bot
discord.ext.commands.Bot
discord.commands.Command
discord.commands.SlashCommandGroup

# AI/LLM providers
openai.OpenAI
openai.AsyncOpenAI

# Database (for repository interface tests)
sqlalchemy.create_engine
sqlalchemy.orm.sessionmaker

# Network/HTTP requests
requests.get
requests.post
httpx.AsyncClient

# Async operations
asyncio.sleep  # Use fixed sleep times
```

### Fixtures Usage

Use these common fixtures from [`tests/conftest.py`](../../tests/conftest.py):

```python
# Settings and configuration
test_settings          # Pydantic settings for test environment

# Database (for repository interface tests only)
test_engine           # Async SQLAlchemy engine (in-memory SQLite)
test_session          # Scoped async database session
test_repository       # SQLiteRepository instance for repo interface tests

# Mock utilities
mocker                # pytest-mock fixture
faker                 # Faker instance with pt_BR locale
freezegun             # Time freeze decorator
```

---

## Testing Requirements

### Test Markers

```python
@pytest.mark.unit          # Required for all tests in this directory
@pytest.mark.slow          # For tests that take >1 second (rare in unit tests)
@pytest.mark.parametrize   # For data-driven testing
```

### Coverage Requirements

- **Minimum coverage**: 95% for unit tests (higher than project minimum due to isolation)
- **Enforced by**: GitHub Actions workflow
- **Report format**: HTML and XML reports generated in `htmlcov/`

### Test Naming Convention

```python
def test_[component]_[scenario]_[expected_result]() -> None:
    """[Description of what is being tested]."""
    pass
```

Examples:
- `test_settings_valid_environment_variables`
- `test_rate_limiter_within_limit_allows_request`
- `test_error_hierarchy_inherits_from_bot_salinha_error`
- `test_retry_decorator_succeeds_after_retries`

---

## Common Testing Patterns

### 1. Testing Configuration

```python
def test_settings_default_values(test_settings: Settings) -> None:
    """Test that settings have correct default values."""
    assert test_settings.HISTORY_RUNS == 3
    assert test_settings.RATE_LIMIT_REQUESTS == 10
    assert test_settings.LOG_LEVEL == "INFO"

def test_settings_invalid_environment_variables() -> None:
    """Test that invalid environment variables raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(OPENAI_API_KEY="")  # Required field missing
```

### 2. Testing Pydantic Models

```python
def test_conversation_schema_valid_data() -> None:
    """Test that ConversationSchema accepts valid data."""
    conversation_data = {
        "user_id": "123456789",
        "guild_id": "987654321",
        "messages": []
    }
    schema = ConversationSchema(**conversation_data)
    assert schema.user_id == "123456789"
    assert schema.guild_id == "987654321"

def test_conversation_schema_invalid_data() -> None:
    """Test that ConversationSchema rejects invalid data."""
    with pytest.raises(ValidationError):
        ConversationSchema(user_id="invalid", guild_id="987654321")
```

### 3. Testing Custom Exceptions

```python
def test_bot_salinha_error_inheritance() -> None:
    """Test that custom exceptions inherit correctly."""
    assert issubclass(APIError, BotSalinhaError)
    assert issubclass(RateLimitError, BotSalinhaError)
    assert issubclass(ValidationError, BotSalinhaError)

def test_error_message_formatting() -> None:
    """Test that error messages include context."""
    error = APIError("API call failed", details={"status": 500})
    assert "API call failed" in str(error)
    assert error.details == {"status": 500}
```

### 4. Testing Rate Limiter

```python
def test_rate_limiter_within_limit() -> None:
    """Test that requests within limit are allowed."""
    limiter = RateLimiter(requests=5, window=60)
    for _ in range(5):
        assert limiter.check_rate_limit("user123", "guild456") is True

def test_rate_limiter_exceeds_limit() -> None:
    """Test that requests exceeding limit are denied."""
    limiter = RateLimiter(requests=1, window=60)
    # First request should succeed
    assert limiter.check_rate_limit("user123", "guild456") is True
    # Second request should fail
    assert limiter.check_rate_limit("user123", "guild456") is False
```

### 5. Testing Retry Decorator

```python
@pytest.mark.asyncio
async def test_retry_decorator_success() -> None:
    """Test that retry decorator succeeds after failures."""
    call_count = 0

    @async_retry(AsyncRetryConfig(max_attempts=3, base_delay=0.1))
    async def failing_function() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise APIError("Temporary failure")
        return "success"

    result = await failing_function()
    assert result == "success"
    assert call_count == 3

@pytest.mark.asyncio
async def test_retry_decorator_exhausted() -> None:
    """Test that retry decorator raises after exhausting attempts."""
    call_count = 0

    @async_retry(AsyncRetryConfig(max_attempts=2, base_delay=0.1))
    async def always_failing() -> str:
        nonlocal call_count
        call_count += 1
        raise APIError("Always fails")

    with pytest.raises(RetryExhaustedError):
        await always_failing()
```

### 6. Testing Repository Interfaces

```python
def test_conversation_repository_interface(test_repository: SQLiteRepository) -> None:
    """Test that repository implements all abstract methods."""
    # Test that all required methods exist
    assert hasattr(test_repository, 'create_conversation')
    assert hasattr(test_repository, 'get_conversation')
    assert hasattr(test_repository, 'update_conversation')
    assert hasattr(test_repository, 'delete_conversation')
    assert hasattr(test_repository, 'get_user_conversations')

@pytest.mark.asyncio
async def test_create_conversation_integration(test_repository: SQLiteRepository) -> None:
    """Test conversation creation with real database (but in-memory)."""
    conversation = await test_repository.create_conversation(
        user_id="123456789",
        guild_id="987654321"
    )
    assert conversation.user_id == "123456789"
    assert conversation.guild_id == "987654321"
    assert conversation.id is not None
```

### 7. Testing YAML Config

```python
def test_yaml_config_parsing() -> None:
    """Test that YAML config file parses correctly."""
    config = load_yaml_config("config.yaml")
    assert config.agent.model == "gpt-4o-mini"
    assert config.agent.prompt.file == "prompt_v1.md"

def test_yaml_config_validation() -> None:
    """Test that invalid YAML raises appropriate errors."""
    with pytest.raises(ValidationError):
        load_yaml_config("nonexistent.yaml")
```

### 8. Testing Logging Setup

```python
def test_logger_configuration(test_settings: Settings) -> None:
    """Test that logger is configured correctly."""
    logger = setup_logging(test_settings)
    assert logger is not None
    # Additional assertions based on log level/format

def test_structlog_usage() -> None:
    """Test that structlog works as expected."""
    import structlog
    log = structlog.get_logger(__name__)
    log.info("test_event", key="value", number=42)
    # Additional assertions if needed
```

---

## Best Practices

1. **Arrange-Act-Assert Pattern**: Structure tests clearly
2. **Descriptive Names**: Make test purpose obvious from the name
3. **Minimal Mocking**: Mock only what's necessary for isolation
4. **No State Between Tests**: Each test should be independent
5. **Use Parametrize**: For testing multiple scenarios
6. **Test Error Conditions**: Don't just test the happy path
7. **Test Edge Cases**: Empty values, None values, boundary conditions
8. **Document Complex Tests**: Add docstrings explaining complex logic

---

## Running Unit Tests

```bash
# Run all unit tests
uv run pytest tests/unit/

# Run with coverage
uv run pytest tests/unit/ --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_settings.py

# Run specific test
uv run pytest tests/unit/ -k test_rate_limiter
```

**Note**: Unit tests should not require Discord API keys or other real credentials.