<!-- Parent: ../../AGENTS.md | Generated: 2026-02-27 | Updated: 2026-02-27 -->

# AGENTS.md — Storage Layer

## Purpose

O módulo `src/storage/` implementa a camada de acesso a dados do BotSalinha usando o padrão Repository Pattern com interfaces abstratas e implementação SQLite via SQLAlchemy ORM assíncrono. Esta camada garante separação de preocupações, testeabilidade e injeção de dependência robusta.

### Arquitetura Principal
- **Interface Abstrata:** `ConversationRepository` e `MessageRepository` definem contratos de dados
- **Implementação SQLite:** `SQLiteRepository` com suporte async e cache TTL
- **Factory Pattern:** `create_repository()` gerencia ciclo de vida do repositório
- **Injeção de Dependência:** Context manager garante setup e cleanup automático

## Arquivos Chave

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `repository.py` | Interfaces abstratas dos repositórios | `cat repository.py` |
| `factory.py` | Factory com DI pattern e lifecycle | `cat factory.py` |
| `sqlite_repository.py` | Implementação SQLite com SQLAlchemy | `cat sqlite_repository.py` |

## Interface Abstrata Repository

### ConversationRepository
Interface para operações CRUD de conversas:

```python
# Métodos principais:
- create_conversation(conversation: ConversationCreate) -> Conversation
- get_conversation_by_id(conversation_id: str) -> Conversation | None
- get_by_user_and_guild(user_id: str, guild_id: str | None) -> list[Conversation]
- get_or_create_conversation(user_id: str, guild_id: str | None, channel_id: str) -> Conversation
- update_conversation(conversation_id: str, updates: ConversationUpdate) -> Conversation | None
- delete_conversation(conversation_id: str) -> bool
- cleanup_old_conversations(days: int = 30) -> int
```

### MessageRepository
Interface para operações CRUD de mensagens:

```python
# Métodos principais:
- create_message(message: MessageCreate) -> Message
- get_message_by_id(message_id: str) -> Message | None
- get_conversation_messages(conversation_id: str, limit: int | None = None, role: MessageRole | None = None) -> list[Message]
- get_conversation_history(conversation_id: str, max_runs: int = 3) -> list[dict[str, Any]]
- update_message(message_id: str, updates: MessageUpdate) -> Message | None
- delete_message(message_id: str) -> bool
- delete_conversation_messages(conversation_id: str) -> int
```

## Factory Pattern - create_repository()

### CRITICAL: Padrão DI Migration

Este é o coração da migração de padrão DI. A factory garante:

**Factory Guarantees:**
1. **On entry:** `initialize_database()` + `create_tables()` + repository instance
2. **On exit:** `finally` block sempre chama `close()` para cleanup
3. **Exception-safe:** Sem vazamentos de conexões
4. **No manual repo.close() needed:** Gerenciado automaticamente

### Uso Correto (NOVO PADRÃO)

```python
# SEMPRE use create_repository() com async with em novo código
from src.storage.factory import create_repository

async def some_function():
    async with create_repository() as repo:
        # DB já está inicializado e tabelas criadas
        conversation = await repo.get_or_create_conversation(
            user_id="123",
            guild_id="456",
            channel_id="789"
        )
        await repo.create_message(MessageCreate(...))
    # Repository é automaticamente fechado após o context
```

### Padrão Herdado (DEPRECATED)

```python
 # LEGACY: get_repository() é deprecated (removido em v2.1)
from src.storage.sqlite_repository import get_repository

# ⚠️ NÃO USE em novo código - apenas para compatibilidade temporária
repo = get_repository()  # Não garante setup/automatic cleanup
```

## SQLiteRepository Implementation

### Características Técnicas

```python
# Configuração do Engine
- AsyncEngine com StaticPool (ótimo para SQLite)
- WAL mode para melhor concurrency
- Cache TTL de 5 minutos para conversas (maxsize=256)
- Session factory com expire_on_commit=False

# Otimizações
- SELECT apenas colunas necessárias em get_conversation_history
- Cache invalidation automática em delete_conversation
- Single query otimizada em get_or_create_conversation
```

### Métodos Especiais

#### get_conversation_history() - Performance
Retorna mensagens formatadas para LLM contexto:

```python
# Retorna dicts brutos (bypass Pydantic) para performance
async def get_conversation_history(
    self,
    conversation_id: str,
    max_runs: int = 3
) -> list[dict[str, Any]]:
    # Query apenas colunas necessárias
    # Filtra por role em SQL
    # Limita exatamente max_runs * 2 mensagens
    # Formata direto como dicts para LLM
```

#### clear_all_history() - Cleanup Completo
```python
async def clear_all_history(self) -> dict[str, int]:
    # Deleta mensagens primeiro (foreign key constraints)
    # Deleta conversas
    # Limpa cache TTL
    # Retorna contagens
```

## Para Agentes de IA

### Instruções de Trabalho

1. **ENTENDA O PATTERN:**
   - NUNCA instanciar `SQLiteRepository()` diretamente
   - SEMPRE usar `create_repository()` com `async with`
   - A factory garante setup/cleanup automático
   - Usar interfaces abstratas em testes (mocks)

2. **PADRÕES OBRIGATÓRIOS:**
   ```python
   # CORRETO - Novo padrão DI
   async with create_repository() as repo:
       await repo.create_conversation(data)

   # INCORRETO - Evite (apenas fallback herdado)
   repo = get_repository()  # Legacy - não usar em novo código
   ```

3. **EXCEPTION HANDLING:**
   - A factory garante cleanup em `finally` block
   - Sem vazamentos mesmo em exceptions
   - Log automático de operações via structlog

### Requisitos de Testes

1. **Mock de Repositórios:**
   - Criar mocks das interfaces abstratas
   - Usar fixtures para in-memory SQLite
   - Testar pattern `async with create_repository()`

2. **Convenções de Teste:**
   ```python
   # Testes unitários - mock da interface
   from unittest.mock import AsyncMock, MagicMock

   # Testes integration - usar factory real
   async def test_conversation_flow():
       async with create_repository() as repo:
           # Testar fluxo completo
           pass
   ```

3. **Cobertura Mínima:** 80% para camada de dados

### Padrões Comuns

#### Adicionar Novo Método de Repositório

1. **Interface Abstrata:**
   ```python
   # repository.py
   @abstractmethod
   async def my_new_method(self, param: str) -> SomeType:
       """Descrição do método."""
       pass
   ```

2. **Implementação SQLite:**
   ```python
   # sqlite_repository.py
   async def my_new_method(self, param: str) -> SomeType:
       async with self.async_session_maker() as session:
           # Implementação com session
           pass
   ```

3. **Atualizar Factory:**
   ```python
   # factory.py - não necessário, factory usa o método da implementação
   ```

#### Adicionar Novo Modelo de Dados

1. **Criar ORM + Pydantic em `src/models/`**
2. **Adicionar métodos abstratos em `repository.py`**
3. **Implementar em `sqlite_repository.py`**
4. **Gerar migração:** `uv run alembic revision --autogenerate -m "add_my_model"`
5. **Aplicar:** `uv run alembic upgrade head`

#### Configuração de Teste

```python
# tests/conftest.py - fixture para repository
@pytest.fixture
async def test_repository():
    async with create_repository() as repo:
        yield repo
    # Cleanup automático via factory
```

## Dependências

### Dependências Diretas
- **sqlalchemy[asyncio]** (v2.0+) - ORM assíncrono
- **sqlalchemy.pool** - StaticPool para SQLite
- **cachetools** - Cache TTL para conversas
- **structlog** - Logging estruturado

### Configuração de Ambiente
```bash
# Variáveis de ambiente para SQLite
DATABASE_URL=sqlite:///data/botsalinha.db
DATABASE__URL=sqlite:///data/botsalinha.db  # Format aninhado tem prioridade
```

## Performance Considerations

### Cache Strategy
- **TTL Cache:** 5 minutos para conversas (maxsize=256)
- **Cache Invalidation:** Automático em `delete_conversation()`
- **Cache Keys:** `{user_id}:{guild_id}:{channel_id}`

### Query Optimization
- **Column Selection:** Apenas colunas necessárias
- **Index Usage:** Guild/User IDs são indexados
- **Bulk Operations:** `delete_conversation_messages()` usa bulk delete
- **Connection Pool:** StaticPool ideal para SQLite

## Limitações

1. **SQLite:** Single-thread por natureza
2. **Cache:** TTL apenas em conversas (mensagens não cacheadas)
3. **Schema:** Mudanças requerem migrações manuais
4. **Concurrency:** Limitado pelo WAL mode do SQLite

## Migration Status

- ✅ **create_repository()** - Padrão principal
- ✅ **SQLiteRepository** - Implementação completa
- ⚠️ **get_repository()** - Legacy (compatibilidade temporária)
- 🚫 **Manual repo.close()** - Não mais necessário (factory garante)