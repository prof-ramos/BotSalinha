# Test Coverage Analysis - BotSalinha

## Executive Summary

**Current Overall Coverage:** 44% (618 lines covered, 1107 total statements)

**Test Structure:** Tests exist only in the E2E category. Unit and integration test directories are completely empty, leaving critical system components untested at the component level.

---

## Coverage by Module

### ✅ High Coverage (>85%)

| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| `models/conversation.py` | 98% | 43 | Excellent - Pydantic models are well-tested |
| `models/message.py` | 98% | 49 | Excellent - Pydantic models are well-tested |
| `config/settings.py` | 85% | 85 | Good - Env var handling mostly covered |
| `config/__init__.py` | 100% | 3 | — |
| `core/__init__.py` | 100% | 4 | — |
| `middleware/__init__.py` | 100% | 2 | — |
| `models/__init__.py` | 100% | 3 | — |
| `storage/__init__.py` | 100% | 2 | — |
| `utils/__init__.py` | 100% | 4 | — |

### ⚠️ Medium Coverage (50-85%)

| Module | Coverage | Lines | Missing Lines | Issue |
|--------|----------|-------|---|--------|
| `config/yaml_config.py` | 58% | 93 | 39 | Config parsing paths untested, YAML validation not comprehensive |
| `middleware/rate_limiter.py` | 46% | 97 | 52 | Token bucket algorithm paths untested, edge cases missing |
| `storage/repository.py` | 71% | 49 | 14 | Abstract interface not fully tested |

### 🔴 Critical Coverage (<50%)

| Module | Coverage | Lines | Missing Lines | Critical Functions |
|---------|----------|-------|---|---|
| **`core/agent.py`** | 31% | 64 | 44 | ❌ Response generation (`generate_response`) not tested at unit level |
| **`core/discord.py`** | 30% | 100 | 70 | ❌ Most commands untested, command flow not unit-tested |
| **`core/lifecycle.py`** | 27% | 96 | 70 | ❌ Signal handling, cleanup tasks not tested |
| **`storage/sqlite_repository.py`** | 20% | 170 | 136 | ❌ All database operations untested - critical! |
| **`utils/errors.py`** | 29% | 58 | 41 | ❌ Exception hierarchy not tested |
| **`utils/logger.py`** | 33% | 51 | 34 | ❌ Logging configuration not tested |
| **`utils/retry.py`** | 36% | 84 | 54 | ❌ Retry decorator edge cases not tested |
| **`main.py`** | 0% | 49 | 49 | ❌ CLI argument parsing not tested |

---

## Problem Analysis

### 1. **Missing Unit Tests**
The `tests/unit/` directory is completely empty. This means:
- Individual components have NO isolated tests
- Dependencies are always mocked at the E2E level
- Bugs in component logic are only caught during full E2E runs
- Regression detection is slow (full system needed to run)

### 2. **Missing Integration Tests**
The `tests/integration/` directory is completely empty. This means:
- Multi-component interactions are untested
- Database-aware operations have no integration tests
- Error handling paths in component interactions are not verified
- Repository implementations (SQLiteRepository) are untested

### 3. **Critical Gap: Database Layer (20% coverage)**

**`sqlite_repository.py` (136 lines untested)**

This is the most critical gap. The repository handles:
- ✅ Conversation CRUD operations (create, read, update, delete)
- ✅ Message persistence and retrieval
- ✅ Database initialization and schema management
- ✅ Connection pooling and session management

**Currently untested:**
- ❌ Actual database create/read/update/delete operations
- ❌ Complex queries (message history retrieval, pagination)
- ❌ Database error handling (connection failures, constraint violations)
- ❌ Transaction management and rollback scenarios
- ❌ Data consistency across operations
- ❌ Migration compatibility

**Why this matters:** Every user interaction depends on the database layer. Silent data loss or corruption would not be detected.

### 4. **Critical Gap: Discord Commands (30% coverage)**

**`core/discord.py` (70 lines untested)**

The bot's core functionality includes commands:
- `!ask` - Main user interaction
- `!ping`, `!help`, `!info`, `!clear`

**Currently untested at unit level:**
- ❌ Command validation (empty arguments, malformed input)
- ❌ Error responses (API failures, rate limit scenarios)
- ❌ Message formatting (long response splitting)
- ❌ Channel/guild isolation (conversations should be per-channel)
- ❌ User permission checks
- ❌ Edge cases (bot mentions, DMs)

**Why this matters:** Users interact directly with these commands. Command bugs directly impact user experience.

### 5. **Critical Gap: AI Response Generation (31% coverage)**

**`core/agent.py` (44 lines untested)**

**Currently untested:**
- ❌ Response generation with conversation history
- ❌ Prompt injection scenarios
- ❌ Token limit handling (max_tokens parameter)
- ❌ Error recovery (API timeouts, rate limiting)
- ❌ Response validation and sanitization

### 6. **Infrastructure Gaps**

| Component | Coverage | Gap | Impact |
|-----------|----------|-----|--------|
| **Lifecycle Management** | 27% | Signal handling, graceful shutdown | Crashes on SIGTERM, orphaned connections |
| **Retry Logic** | 36% | Exponential backoff edge cases | Failed retries not validated |
| **Error Hierarchy** | 29% | Exception construction and serialization | Error reporting unreliable |
| **Logging** | 33% | Log configuration, format switching | Logging failures silent |
| **CLI Entry Point** | 0% | Argument parsing, mode selection | CLI completely untested |

---

## Recommended Test Improvements

### Priority 1: Critical Path (Unit Tests) - 3-4 days

These are blocking issues that can cause data loss or silent failures:

#### 1.1 Database Layer Tests (`tests/unit/storage/test_sqlite_repository.py`) - 100+ lines
**Coverage Goal:** 90%+ (currently 20%)

```python
# Required test cases:
- test_create_conversation_persists_to_db
- test_get_conversation_by_id_returns_data
- test_update_conversation_updates_timestamp
- test_delete_conversation_removes_all_messages
- test_create_message_associates_with_conversation
- test_get_messages_by_conversation_returns_history
- test_message_ordering_by_timestamp
- test_database_error_handling(connection_failure, constraint_violation)
- test_concurrent_message_creation
- test_pagination_for_large_message_sets
- test_transaction_rollback_on_error
```

**Testing approach:**
- Use `test_engine` fixture with in-memory SQLite
- Test each CRUD operation independently
- Test with realistic data volumes (100-1000 messages)
- Test error scenarios with connection mocking

---

#### 1.2 Discord Commands Tests (`tests/unit/core/test_discord_commands.py`) - 80+ lines
**Coverage Goal:** 90%+ (currently 30%)

```python
# Required test cases:
- test_ask_command_with_valid_question
- test_ask_command_with_empty_question (validation)
- test_ask_command_enforces_rate_limit
- test_ask_command_splits_long_responses
- test_ask_command_handles_api_error
- test_ask_command_creates_new_conversation
- test_ask_command_uses_existing_conversation
- test_ping_command_responds
- test_help_command_displays_all_commands
- test_clear_command_deletes_user_history
- test_command_channel_isolation
- test_command_error_messages_user_friendly
```

**Testing approach:**
- Use `mock_discord_context` fixture
- Mock Gemini API with `mock_gemini_api`
- Test input validation and error messages
- Verify database interactions

---

#### 1.3 Agent Wrapper Tests (`tests/unit/core/test_agent_wrapper.py`) - 50+ lines
**Coverage Goal:** 85%+ (currently 31%)

```python
# Required test cases:
- test_generate_response_with_empty_history
- test_generate_response_includes_conversation_history
- test_response_generation_on_api_error
- test_response_respects_max_tokens
- test_conversation_history_saved_to_db
- test_prompt_loading_from_config
- test_provider_selection(google, openai)
- test_temperature_parameter_applied
```

**Testing approach:**
- Mock Gemini API responses
- Use `conversation_repository` fixture
- Test with various conversation histories
- Verify repository interactions

---

### Priority 2: Integration Tests - 2-3 days

These test component interactions without full E2E setup:

#### 2.1 Database + Repository Integration (`tests/integration/test_repository_database.py`) - 60+ lines
**Coverage Goal:** 95%+

```python
# Test flows:
- test_conversation_lifecycle(create → update → delete)
- test_message_retrieval_preserves_order_and_timestamps
- test_concurrent_users_separate_conversations
- test_large_conversation_pagination
- test_database_constraints(foreign_key, unique_constraints)
```

---

#### 2.2 Discord + Agent Integration (`tests/integration/test_command_agent_flow.py`) - 60+ lines

```python
# Test flows:
- test_ask_command_updates_database
- test_rate_limiter_blocks_rapid_requests
- test_error_in_agent_propagates_to_user_message
- test_conversation_history_maintained_across_commands
```

---

#### 2.3 Configuration Integration (`tests/integration/test_config_loading.py`) - 40+ lines

```python
# Test flows:
- test_settings_loaded_from_env
- test_yaml_config_parsed_correctly
- test_prompt_file_loaded_from_config
- test_invalid_config_raises_error
```

---

### Priority 3: Infrastructure & Edge Cases - 2-3 days

#### 3.1 Rate Limiter Tests (`tests/unit/middleware/test_rate_limiter.py`) - 60+ lines
**Coverage Goal:** 90%+ (currently 46%)

```python
# Test cases:
- test_token_bucket_refills_correctly
- test_token_bucket_capacity_limit
- test_rate_limiter_blocks_after_limit
- test_rate_limiter_per_user_isolation
- test_rate_limiter_per_guild_tracking
- test_wait_time_calculation
- test_user_unblocked_after_window
```

---

#### 3.2 Lifecycle & Signal Handling (`tests/unit/core/test_lifecycle.py`) - 50+ lines
**Coverage Goal:** 85%+ (currently 27%)

```python
# Test cases:
- test_signal_handler_setup
- test_graceful_shutdown_calls_cleanup_tasks
- test_multiple_cleanup_tasks_executed_in_order
- test_sigterm_triggers_shutdown
- test_sigint_prevents_force_quit_on_first_signal
```

---

#### 3.3 Error Hierarchy Tests (`tests/unit/utils/test_errors.py`) - 40+ lines
**Coverage Goal:** 95%+ (currently 29%)

```python
# Test cases:
- test_error_to_dict_serialization
- test_api_error_with_status_code
- test_rate_limit_error_retry_after
- test_validation_error_field_info
- test_custom_exception_message_format
```

---

#### 3.4 Retry Decorator Tests (`tests/unit/utils/test_retry.py`) - 50+ lines
**Coverage Goal:** 90%+ (currently 36%)

```python
# Test cases:
- test_retry_succeeds_on_first_attempt
- test_retry_succeeds_after_n_failures
- test_retry_exhausted_after_max_attempts
- test_exponential_backoff_timing
- test_jitter_applied_to_delay
- test_retry_only_on_specified_exceptions
```

---

#### 3.5 Logger Configuration Tests (`tests/unit/utils/test_logger.py`) - 40+ lines
**Coverage Goal:** 85%+ (currently 33%)

```python
# Test cases:
- test_json_format_output
- test_text_format_output
- test_log_level_filtering
- test_context_vars_binding
- test_timestamp_iso_format
```

---

#### 3.6 YAML Config Parsing (`tests/unit/config/test_yaml_config.py`) - 50+ lines
**Coverage Goal:** 95%+ (currently 58%)

```python
# Test cases:
- test_default_config_values
- test_valid_model_configuration
- test_invalid_temperature_rejected
- test_prompt_file_validation
- test_missing_config_file_raises_error
- test_missing_prompt_file_raises_error
- test_config_yaml_syntax_errors
```

---

#### 3.7 CLI Entry Point Tests (`tests/unit/test_main.py`) - 40+ lines
**Coverage Goal:** 95%+ (currently 0%)

```python
# Test cases:
- test_parse_args_default_discord_mode
- test_parse_args_chat_mode
- test_run_discord_bot_initializes_bot
- test_run_chat_mode_initializes_repl
- test_env_loading_from_dotenv
```

---

### Priority 4: E2E Hardening - 1-2 days

Improve existing E2E tests in `tests/e2e/`:

#### 4.1 Expand E2E Command Coverage
Currently covers basic happy paths. Add:
```python
# Error scenarios:
- test_ask_command_with_api_timeout
- test_ask_command_with_rate_limit_exceeded
- test_ask_command_handles_malformed_response
- test_bot_recovers_after_api_downtime

# Edge cases:
- test_very_long_questions (>2000 chars)
- test_special_characters_in_questions
- test_rapid_command_execution
- test_concurrent_users_in_same_guild
```

---

## Implementation Strategy

### Phase 1: Foundation (Week 1)
1. Create `tests/unit/` directory structure:
   ```
   tests/unit/
   ├── config/
   │   └── test_yaml_config.py
   ├── core/
   │   ├── test_agent_wrapper.py
   │   ├── test_discord_commands.py
   │   └── test_lifecycle.py
   ├── middleware/
   │   └── test_rate_limiter.py
   ├── storage/
   │   └── test_sqlite_repository.py
   ├── utils/
   │   ├── test_errors.py
   │   ├── test_logger.py
   │   └── test_retry.py
   └── test_main.py
   ```

2. Write database unit tests first (highest priority)
3. Write command unit tests
4. Write supporting infrastructure tests

### Phase 2: Integration (Week 2)
1. Create `tests/integration/` directory
2. Write integration tests for workflows
3. Test component interactions

### Phase 3: Polish (Week 3)
1. Expand E2E test coverage
2. Add edge case testing
3. Achieve 80%+ coverage goal

---

## Coverage Target

| Category | Current | Target | Gap |
|----------|---------|--------|-----|
| **Overall** | 44% | 80% | +36% |
| **Database Layer** | 20% | 90% | +70% |
| **Discord Commands** | 30% | 90% | +60% |
| **Agent/AI** | 31% | 85% | +54% |
| **Infrastructure** | 33-46% | 85%+ | +40-50% |

**Estimated scope:** 800-1000 lines of test code across 15-18 new test files.

---

## Testing Best Practices to Implement

1. **Use fixtures from conftest.py** - Don't recreate mocks
2. **Test one behavior per test** - Avoid mega-tests
3. **Clear Arrange-Act-Assert** - 3-part test structure
4. **Descriptive test names** - Should read like documentation
5. **Use markers** - `@pytest.mark.unit`, `@pytest.mark.integration`
6. **Mock external dependencies** - Discord API, Gemini API, file I/O
7. **Test error paths** - Not just happy paths
8. **Use parameterization** - Test multiple scenarios efficiently

---

## Expected Benefits

✅ **Faster feedback loop** - Unit tests run in <5 seconds
✅ **Better debugging** - Know exactly which component fails
✅ **Regression prevention** - Catch breaking changes immediately
✅ **Documentation** - Tests serve as usage examples
✅ **Confidence** - Deploy with >80% coverage assurance
✅ **Easier refactoring** - Change code without fear

---

## Risks of Current State

🔴 **Data loss** - Database bugs silently corrupt user conversations
🔴 **Silent errors** - Command failures only caught during full E2E runs
🔴 **Slow CI** - E2E tests take 90+ seconds to validate changes
🔴 **Low confidence** - Hard to guarantee code quality
🔴 **Difficult refactoring** - Must run full E2E suite for simple changes

---

## Next Steps

1. **Review this analysis** with the team
2. **Prioritize Phase 1** (database and command tests)
3. **Create tracking issue** for test implementation
4. **Begin Phase 1 implementation** starting with `test_sqlite_repository.py`
5. **Set up CI gate** - Block merges if coverage drops below 80%
