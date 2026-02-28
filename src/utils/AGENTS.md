<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->

# AGENTS.md — BotSalinha Utils

## Purpose

Este módulo contém utilitários fundamentais para o BotSalinha, incluindo gerenciamento de erros customizados, configuração de logging estruturado e lógica de retry com exponential backoff. Todos os utilitários são assíncronos e seguem as melhores práticas da comunidade Python.

### Componentes Principais
- **Gerenciamento de Erros:** Hierarquia de exceções customizadas herdeiras de `BotSalinhaError`
- **Logging Estruturado:** Configuração do structlog com suporte a contextvars para logs request-scoped
- **Retry Assíncrono:** Decorator e função de retry com exponential backoff usando tenacity
- **Circuit Breaker:** Implementação simples para prevenir cascata de falhas

## Arquivos Chave

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `errors.py` | Hierarquia de exceções customizadas | `cat errors.py` |
| `logger.py` | Configuração de logging estruturado com structlog | `cat logger.py` |
| `retry.py` | Lógica de retry assíncrono com circuit breaker | `cat retry.py` |

## Para Agentes de IA

### Instruções de Trabalho

1. **Entenda o Contexto:**
   - Todos os utilitários são assíncronos (`async/await`)
   - Exceções customizadas herdam de `BotSalinhaError` para consistência
   - Logging estruturado com contextvars para rastreamento de requisições
   - Retry lógico integrado automaticamente em operações externas

2. **Padrões de Código:**
   - Sempre use exceções customizadas em vez de Exception genéricas
   - Structlog requer keyword args para contexto estruturado
   - AsyncRetryConfig configura política de retry centralizada
   - CircuitBreaker protege contra falhas em cascata

3. **Configuração Importante:**
   - Exceções específicas para diferentes tipos de falhas
   - Logging em formato JSON ou texto configurável
   - Retry automático para API errors e connection errors
   - Circuit breaker com threshold configurável

### Padrões Comuns

#### Exceções
```python
from .errors import BotSalinhaError, APIError, RateLimitError

# Usar exceções específicas
try:
    await external_api_call()
except APIError as e:
    log.error("api_failed", status_code=e.status_code, response=e.response_body)
    raise RateLimitError("Limite atingido", retry_after=30)
```

#### Logging Estruturado
```python
from .logger import setup_logging, bind_request_context

# Setup inicial
log = setup_logging(log_level="INFO", log_format="json")

# Contexto de requisição
bind_request_context(request_id="abc123", user_id=123, guild_id=456)
log.info("process_request", action="discord_command")
```

#### Retry Assíncrono
```python
from .retry import async_retry, AsyncRetryConfig

# Configuração padrão
config = AsyncRetryConfig(max_attempts=3, wait_min=1.0, wait_max=60.0)

# Uso direto
result = await async_retry(api_call, config=config)

# Ou como decorator
@async_retry_decorator(max_attempts=5, operation_name="database_query")
async def get_user_data(user_id: int):
    return await database.get_user(user_id)
```

#### Circuit Breaker
```python
from .retry import CircuitBreaker

breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

# Proteger uma operação
try:
    result = await breaker.call(some_operation)
except RetryExhaustedError:
    # Circuit está aberto
    log.warning("service_unavailable", service="database")
```

## Exception Hierarchy

### BotSalinhaError (Base)
Exceção base para todos os erros do BotSalinha, inclui:
- `message`: Mensagem legível para humanos
- `details`: Contexto adicional para logging/debugging
- `to_dict()`: Converte para dicionário

### Exceções Específicas
```python
# API failures (OpenAI, Discord, etc.)
APIError(status_code, response_body, details)

# Rate limiting (users ou APIs)
RateLimitError(retry_after, limit, window_seconds)

# Input validation failures
ValidationError(field, value, details)

# Database operations
DatabaseError(query, table, details)

# Configuration issues
ConfigurationError(config_key, details)

# Retry exhaustion
RetryExhaustedError(last_error, attempts, details)
```

## Logging Configuration

### Formatos Suportados
- **JSON**: Para produção e análise automatizada
- **Texto**: Para desenvolvimento com cores e formatação

### Níveis de Log
- `DEBUG`: Informações detalhadas para debugging
- `INFO`: Informações gerais sobre operações
- `WARNING**: Avisos sobre condições inesperadas
- `ERROR`: Erros que não interrompem a aplicação
- `CRITICAL`: Erros graves que podem causar falha

### Contexto de Requisição
```python
# Associar contexto aos logs
bind_request_context(
    request_id="abc123",
    user_id=456789,
    guild_id=987654,
    command="!ask"
)

# Logs automaticamente incluem contexto
log.info("command_processed", response_time=0.5)
```

## Retry Logic

### AsyncRetryConfig
```python
@dataclass
class AsyncRetryConfig:
    max_attempts: int = 3
    wait_min: float = 1.0      # Mínimo wait time
    wait_max: float = 60.0     # Máximo wait time
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (APIError, ConnectionError, TimeoutError)
```

### Exponential Backoff
- Tempo de espera: `min(wait_max, wait_min * (exponential_base ** (attempt-1)))`
- Logging detalhado de cada tentativa
- Retenta apenas em exceções específicas

### Circuit Breaker States
- **CLOSED**: Funcionando normalmente
- **OPEN**: Rejeita chamadas após threshold de falhas
- **HALF-OPEN**: Testa recuperação após timeout

## Common Patterns

### API Calls com Retry
```python
async def call_openai_api(prompt: str) -> str:
    try:
        return await async_retry(
            openai.chat.completions.create,
            config=AsyncRetryConfig(max_attempts=3),
            operation_name="openai_completion"
        )
    except RetryExhaustedError as e:
        log.error("openai_retries_exhausted", error=str(e.last_error))
        raise BotSalinhaError("API temporariamente indisponível") from e
```

### Database com Circuit Breaker
```python
db_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

async def get_conversation_history(user_id: int):
    return await db_breaker.call(
        repository.get_conversation_history,
        user_id
    )
```

### Error Handling Centralizado
```python
try:
    result = await some_operation()
except BotSalinhaError:
    # Re-raising custom exceptions
    raise
except Exception as e:
    # Convertendo para custom exception
    log.error("unexpected_error", error=str(e))
    raise BotSalinhaError("Operação falhou", details={"original": str(e)}) from e
```

## Dependencies

### Externas
- **structlog** (v23.0+) - Logging estruturado com suporte a contextvars
- **tenacity** (v8.0+) - Implementação de retry lógica com exponential backoff
- **contextvars** (Python 3.7+) - Variáveis de contexto assíncrono

### Internas
- `BotSalinhaError` - Base para todas as exceções customizadas
- `setup_logging()` - Configuração inicial do logging
- `bind_request_context()` - Helper para contexto de requisição
- `AsyncRetryConfig` - Configuração centralizada de retry
- `CircuitBreaker` - Proteção contra falhas em cascata

## Ambiente de Execução

### Configuração Padrão
```python
# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Retry
MAX_RETRIES=3
RETRY_DELAY_SECONDS=1
RETRY_MAX_DELAY_SECONDS=60

# Circuit Breaker
FAILURE_THRESHOLD=5
RECOVERY_TIMEOUT=60
```

### Melhores Práticas
1. **Sempre capture exceções específicas** em vez de Exception genéricas
2. **Use logging estruturado** com keyword args para melhor análise
3. **Configure circuit breaker** para serviços externos
4. **Teste retry logic** em diferentes cenários de falha
5. **Monitore logs de retry** para identificar problemas recorrentes