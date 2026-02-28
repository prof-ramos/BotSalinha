<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->
<!-- Parent: ../../AGENTS.md -->

# AGENTS.md — Middleware Layer

## Purpose

The middleware layer provides request interceptors and processing components that sit between the Discord interface and the core services. Currently implements rate limiting using the token bucket algorithm to prevent abuse and ensure fair resource usage across users and guilds.

### Component Characteristics
- **Algorithm:** Token bucket rate limiting
- **Scope:** Per-user and per-guild rate limiting
- **Concurrency:** Thread-safe (asyncio single-threaded, no locks needed)
- **Storage:** In-memory with automatic cleanup
- **Configuration:** Via `RateLimitConfig` in settings

## Arquivos Chave

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `rate_limiter.py` | Token bucket rate limiter implementation | `cat rate_limiter.py` |
| `__init__.py` | Module exports (RateLimiter, TokenBucket) | `cat __init__.py` |

## Estrutura do Componente

### TokenBucket
- **Purpose:** Core token bucket algorithm implementation
- **Key Properties:**
  - `capacity`: Maximum tokens in bucket
  - `refill_rate`: Tokens per second
  - `tokens`: Current token count
  - `last_update`: Last refill timestamp
- **Key Methods:**
  - `consume()`: Try to consume tokens
  - `wait_time`: Calculate time until next token available

### UserBucket
- **Purpose:** Rate limit state for a specific user/guild
- **Key Properties:**
  - `bucket`: Associated TokenBucket
  - `limited_until`: Timestamp when rate limit expires
- **Key Methods:**
  - `is_rate_limited`: Check if currently limited
  - `mark_rate_limited()`: Set limit duration

### RateLimiter
- **Purpose:** Main rate limiting service
- **Key Properties:**
  - `requests`: Max requests per window (default: 10)
  - `window_seconds`: Time window in seconds (default: 60)
  - `refill_rate`: Calculated tokens per second
  - `_users`: Dictionary of user buckets
- **Key Methods:**
  - `check_rate_limit()`: Check if user is rate limited
  - `check_decorator()`: Discord command decorator
  - `reset_user()`: Reset rate limit for specific user
  - `reset_all()`: Reset all rate limits
  - `get_stats()`: Get usage statistics

## Para Agentes de IA

### Instruções de Trabalho

1. **Entenda o Algoritmo:**
   - Token bucket permite burst traffic quando há tokens disponíveis
   - O limite é aplicado por combinação de `user_id:guild_id` (ou `user_id:dm` para DMs)
   - Tokens são recarregados continuamente com base no tempo decorrido
   - Quando o bucket esgota, o usuário é marcado como rate limited

2. **Padrões de Código:**
   - Todo código assíncrono (`async/await`)
   - Usa `structlog` para logging estruturado
   - Lança `RateLimitError` quando limite é excedido
   - Sem locks necessários devido ao asyncio single-threaded
   - Limpeza automática de buckets não utilizados

3. **Configuração Importante:**
   - Configurado via `settings.rate_limit`
   - Padrão: 10 requests por 60 segundos por usuário/guilda
   - Pode ser sobrescrito ao instanciar `RateLimiter`
   - Intervalo de limpeza: 5 minutos

### Integração com Discord

```python
# Decorator para comandos Discord
@rate_limiter.check_decorator()
async def my_command(ctx: Context):
    await ctx.send("Command executed!")

# Verificação manual
try:
    await rate_limiter.check_rate_limit(user_id=ctx.author.id, guild_id=ctx.guild.id)
    # Process command
except RateLimitError as e:
    await ctx.send(f"Rate limit exceeded. Try again in {e.retry_after:.1f} seconds.")
```

### Requisitos de Testes

1. **Markers Disponíveis:**
   ```python
   @pytest.mark.unit          # Teste isolado (sem I/O)
   @pytest.mark.integration   # Teste com mock de tempo
   @pytest.mark.asyncio       # Testes assíncronos
   ```

2. **Mock de Tempo:**
   - Use `freezegun` para testes dependentes de tempo
   - Simule cenários de burst traffic
   - Teste recarregamento de tokens

3. **Cobertura Mínima:** 90% (crítico para componentes de segurança)

### Padrões Comuns

#### Criar Novo Middleware
1. Seguir o padrão de decorator do rate limiter
2. Implementar verificação assíncrona
3. Lançar exceções apropriadas
4. Adicionar logging estruturado
5. Implementar limpeza automática de estado

#### Customizar Rate Limiting
```python
# Configuração personalizada
custom_limiter = RateLimiter(
    requests=5,  # Menos requests
    window_seconds=30,  # Janela menor
    cleanup_interval=60.0  # Limpeza mais frequente
)

# Usar em comandos específicos
@custom_limiter.check_decorator()
async def premium_command(ctx: Context):
    await ctx.send("Premium command!")
```

## Dependências

### Dependências Externas
- **structlog** (v23.0+) - Logging estruturado
- **pydantic** (v2.0+) - Validação de configuração
- **typing_extensions** - Extensões de typing para Python 3.11+

### Dependências de Código
- **src/config/settings** - RateLimitConfig via Pydantic
- **src/utils/errors** - RateLimitError exception
- **discord.py** - Context para integração Discord

## Ambiente de Execução

### Variáveis de Ambiente
```bash
RATE_LIMIT__REQUESTS=10          # Requests por janela
RATE_LIMIT__WINDOW_SECONDS=60     # Janela de tempo em segundos
```

### Monitoramento
```python
# Obter estatísticas
stats = rate_limiter.get_stats()
print(f"Usuários monitorados: {stats['tracked_users']}")
print(f"Usuários limitados: {stats['rate_limited_users']}")
```

### Reset Manual
```python
# Resetar para usuário específico
rate_limiter.reset_user(user_id=123, guild_id=456)

# Resetar todos os limites
rate_limiter.reset_all()
```