# BotSalinha - Documentação de Código

Documentação técnica detalhada dos módulos principais do BotSalinha.

## Índice

1. [Core](#core) - Bot Discord, Agente AI, Lifecycle
2. [Models](#models) - Modelos de Dados
3. [Storage](#storage) - Repository Pattern e Implementações
4. [Middleware](#middleware) - Rate Limiting
5. [Utils](#utils) - Utilitários (Retry, Errors, Logger)
6. [Services](#services) - Camada de Serviço
7. [RAG](#rag) - Retrieval-Augmented Generation
8. [Diagramas de Arquitetura](#diagramas-de-arquitetura) - Visualização do Sistema

---

## Core

### `src/core/discord.py` - BotSalinhaBot

Bot Discord principal usando `discord.py` com comandos e eventos.

**Classe Principal:** `BotSalinhaBot(commands.Bot)`

#### Inicialização

```python
bot = BotSalinhaBot()
```

O bot configura automaticamente:
- **Intents:** `message_content=True`, `guilds=True`, `dm_messages=True`
- **Command prefix:** Configurado em settings (default: `!`)
- **Repository:** SQLite ou Convex (baseado em configuração)
- **Agent:** AgentWrapper com Agno + Gemini/OpenAI

#### Comandos Discord

| Comando | Descrição | Rate Limit |
|---------|-----------|------------|
| `!ask <pergunta>` | Faz pergunta ao AI | 1 req/minuto por usuário |
| `!ping` | Verifica latência | Sem limite |
| `!ajuda` / `!help` | Mostra ajuda | Sem limite |
| `!limpar` / `!clear` | Limpa histórico | Sem limite |
| `!info` | Informações do bot | Sem limite |

#### Eventos

**`on_ready()`** - Bot iniciado
- Log bot ID, nome, quantidade de guilds e usuários
- Seta `_ready_event`

**`on_message(message)`** - Processa mensagens
- Ignora mensagens de outros bots
- Bind request context para tracing
- Processa apenas comandos com prefix

**`on_command_error(ctx, error)`** - Tratamento de erros
- `CommandNotFound`: Silencioso
- `MissingPermissions`: Mostra permissões faltando
- `MissingRequiredArgument`: Mostra argumento faltando
- `BadArgument`: Mostra erro de validação
- `RateLimitError`: Mostra mensagem de rate limit
- Outros: Mensagem genérica de erro

#### Método Principal: `ask_command`

```python
async def ask_command(self, ctx: commands.Context, question: str) -> None:
    # 1. Envia indicador "typing..."
    await ctx.typing()

    # 2. Obtém ou cria conversa
    conversation = await self.conversation_service.get_or_create_conversation(
        user_id=str(ctx.author.id),
        guild_id=str(ctx.guild.id) if ctx.guild else None,
        channel_id=str(ctx.channel.id),
    )

    # 3. Processa pergunta via service
    response_chunks = await self.conversation_service.process_question(
        question=question,
        conversation=conversation,
        user_id=str(ctx.author.id),
        guild_id=str(ctx.guild.id) if ctx.guild else None,
        discord_message_id=str(ctx.message.id),
    )

    # 4. Envia chunks de resposta
    for chunk in response_chunks:
        await ctx.send(chunk)
```

---

### `src/core/agent.py` - AgentWrapper

Wrapper para Agno Agent com integração RAG e gerenciamento de contexto.

**Classe Principal:** `AgentWrapper`

#### Inicialização

```python
agent = AgentWrapper(
    repository=MessageRepository,  # OBRIGATÓRIO
    db_session=AsyncSession,       # Opcional (para RAG)
    enable_rag=bool,               # Opcional (default: settings)
)
```

O AgentWrapper:
1. Carrega prompt do arquivo configurado em `config.yaml`
2. Configura modelo (Google Gemini ou OpenAI)
3. Inicializa serviços RAG se habilitado
4. Configura gerenciador de ferramentas MCP (se configurado)

#### Métodos Principais

**`generate_response(prompt, conversation_id, user_id, guild_id)`**

Gera resposta sem RAG:

```python
response = await agent.generate_response(
    prompt="Qual é o artigo 1º da CF?",
    conversation_id="conv-123",
    user_id="user-456",
    guild_id="guild-789",  # opcional
)
# Returns: str (resposta)
```

**`generate_response_with_rag(...)`** - Gera resposta com contexto RAG

```python
response, rag_context = await agent.generate_response_with_rag(
    prompt="Qual é o artigo 1º da CF?",
    conversation_id="conv-123",
    user_id="user-456",
    guild_id="guild-789",
)
# Returns: tuple[str, RAGContext | None]
```

**`save_message(conversation_id, role, content, discord_message_id)`**

Salva mensagem no repositório:

```python
await agent.save_message(
    conversation_id="conv-123",
    role="user",  # ou "assistant"
    content="Olá!",
    discord_message_id="msg-456",  # opcional
)
```

**`run_cli(session_id)`** - Modo CLI interativo

```python
await agent.run_cli(session_id="cli_session")
# Abre interface CLI com streaming e suporte a Markdown
```

#### Prompt Building

O prompt é construído com:

1. **RAG Context** (se disponível e confidence >= média)
   - Blocos de documentos recuperados
   - Similaridades e fontes
   - Instruções baseadas em confidence

2. **Conversation History**
   - Últimas N mensagens (configurável)
   - Formato: "Usuário: ..." / "BotSalinha: ..."

3. **Nova Mensagem**
   - Prompt atual do usuário

---

### `src/core/lifecycle.py` - Graceful Shutdown

Gerenciamento de lifecycle da aplicação com signal handling.

**Classe Principal:** `GracefulShutdown`

#### Uso com Context Manager

```python
async with managed_lifecycle():
    await bot.start()
# Cleanup automático no final
```

#### Uso Manual

```python
shutdown_manager = GracefulShutdown()

# Registrar cleanup tasks
async def cleanup_db():
    await repository.close()

shutdown_manager.register_cleanup_task(cleanup_db)
shutdown_manager.setup_signal_handlers()

# Aguardar shutdown
await shutdown_manager.wait_for_shutdown()
await shutdown_manager.cleanup()
```

#### Signals Suportados

- `SIGINT` (Ctrl+C)
- `SIGTERM` (kill)

#### Comportamento

1. Primeiro signal: Inicia graceful shutdown
2. Segundo signal (enquanto shutting down): Force quit
3. Cleanup tasks executadas sequencialmente
4. Repository fechado automaticamente

---

## Models

### `src/models/conversation.py` - Conversation Models

Modelos ORM e Pydantic para conversas.

#### ORM Model: `ConversationORM`

```python
class ConversationORM(Base):
    __tablename__ = "conversations"

    id: str                    # UUID (primary key)
    user_id: str               # Discord user ID (indexed)
    guild_id: str | None       # Discord guild ID (indexed, nullable)
    channel_id: str            # Discord channel ID (indexed)
    created_at: datetime        # UTC timestamp
    updated_at: datetime        # UTC timestamp (auto-update)
    meta_data: str | None       # JSON string

    # Relationship: messages (lazy loaded)
```

#### Pydantic Schemas

| Schema | Uso |
|--------|-----|
| `ConversationCreate` | Criar nova conversa |
| `ConversationUpdate` | Atualizar metadata |
| `Conversation` | Response com campos |
| `ConversationWithMessages` | Response com mensagens incluídas |

**Campos:**

```python
class ConversationCreate(BaseModel):
    user_id: str                # Obrigatório
    guild_id: str | None        # Opcional (DMs = None)
    channel_id: str             # Obrigatório
    meta_data: str | None       # JSON opcional
```

---

### `src/models/message.py` - Message Models

Modelos ORM e Pydantic para mensagens.

#### ORM Model: `MessageORM`

Criado dinamicamente para evitar circular imports:

```python
class MessageORM(Base):
    __tablename__ = "messages"

    id: str                    # UUID (primary key)
    conversation_id: str       # FK → conversations.id (CASCADE)
    role: str                  # "user" | "assistant" | "system"
    content: str               # Texto da mensagem
    discord_message_id: str | None  # Discord message ID (indexed)
    created_at: datetime        # UTC timestamp
    meta_data: str | None       # JSON string
```

#### Enum: `MessageRole`

```python
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
```

#### Pydantic Schemas

| Schema | Uso |
|--------|-----|
| `MessageCreate` | Criar mensagem |
| `MessageUpdate` | Atualizar conteúdo |
| `Message` | Response |
| `MessageWithConversation` | Response com conversa |

---

### `src/models/rag_models.py` - RAG Models

Modelos ORM para RAG (Retrieval-Augmented Generation).

#### ORM: `DocumentORM`

```python
class DocumentORM(Base):
    __tablename__ = "rag_documents"

    id: int                       # Auto-increment primary key
    nome: str                     # Nome do documento (indexed)
    arquivo_origem: str           # Caminho do arquivo
    content_hash: str | None      # SHA-256 hash (unique, indexed)
    chunk_count: int              # Número de chunks
    token_count: int              # Total de tokens
    created_at: datetime           # UTC timestamp

    # Relationship: chunks (cascade delete)
    chunks: Mapped[list["ChunkORM"]]
```

#### ORM: `ChunkORM`

```python
class ChunkORM(Base):
    __tablename__ = "rag_chunks"

    id: str                      # Chunk ID (primary key)
    documento_id: int            # FK → rag_documents.id (CASCADE)
    texto: str                   # Texto do chunk
    metadados: str               # JSON metadata
    token_count: int             # Tokens no chunk
    embedding: bytes | None      # Embedding serializado (float32)
    created_at: datetime          # UTC timestamp

    # Relationship: documento (lazy joined)
    documento: Mapped["DocumentORM"]
```

---

## Storage

### `src/storage/repository.py` - Repository Interfaces

Interfaces abstratas para acesso a dados (Repository Pattern).

#### `ConversationRepository` (Abstract)

Define interface para operações de conversa:

```python
class ConversationRepository(ABC):
    @abstractmethod
    async def create_conversation(self, conversation: ConversationCreate) -> Conversation:
        """Criar nova conversa"""

    @abstractmethod
    async def get_conversation_by_id(self, conversation_id: str) -> Conversation | None:
        """Obter conversa por ID"""

    @abstractmethod
    async def get_by_user_and_guild(self, user_id: str, guild_id: str | None) -> list[Conversation]:
        """Listar conversas de usuário em guild"""

    @abstractmethod
    async def get_or_create_conversation(self, user_id: str, guild_id: str | None, channel_id: str) -> Conversation:
        """Obter existente ou criar nova"""

    @abstractmethod
    async def update_conversation(self, conversation_id: str, updates: ConversationUpdate) -> Conversation | None:
        """Atualizar metadata"""

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Deletar conversa"""

    @abstractmethod
    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """Limpar conversas antigas"""
```

#### `MessageRepository` (Abstract)

Define interface para operações de mensagem:

```python
class MessageRepository(ABC):
    @abstractmethod
    async def create_message(self, message: MessageCreate) -> Message:
        """Criar nova mensagem"""

    @abstractmethod
    async def get_message_by_id(self, message_id: str) -> Message | None:
        """Obter mensagem por ID"""

    @abstractmethod
    async def get_conversation_messages(self, conversation_id: str, limit: int | None, role: MessageRole | None) -> list[Message]:
        """Listar mensagens de conversa"""

    @abstractmethod
    async def get_conversation_history(self, conversation_id: str, max_runs: int) -> list[dict[str, Any]]:
        """Obter histórico formatado para LLM"""

    @abstractmethod
    async def update_message(self, message_id: str, updates: MessageUpdate) -> Message | None:
        """Atualizar mensagem"""

    @abstractmethod
    async def delete_message(self, message_id: str) -> bool:
        """Deletar mensagem"""

    @abstractmethod
    async def delete_conversation_messages(self, conversation_id: str) -> int:
        """Deletar todas mensagens de conversa"""
```

---

### `src/storage/sqlite_repository.py` - SQLite Implementation

Implementação SQLite com SQLAlchemy async.

**Classe:** `SQLiteRepository(ConversationRepository, MessageRepository)`

#### Inicialização

```python
repo = SQLiteRepository(database_url="sqlite:///data/botsalinha.db")
```

URL é convertida automaticamente para `sqlite+aiosqlite:///` para suporte async.

#### Otimizações SQLite

No método `initialize_database()`:

```python
PRAGMA journal_mode=WAL        # Write-Ahead Logging (melhor concorrência)
PRAGMA synchronous=NORMAL       # Balance performance/safety
PRAGMA cache_size=-64000        # 64MB cache
PRAGMA temp_store=memory        # Temp tables em memória
```

#### Session Management

```python
async with self.async_session_maker() as session:
    # Operações no banco
    result = await session.execute(stmt)
    await session.commit()
    await session.refresh(orm)
```

#### Histórico para LLM

O método `get_conversation_history()` formata mensagens para o Agno:

```python
# Retorna formato compatível com Agno/Gemini
[
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    # Até max_runs pares (user + assistant)
]
```

System messages são preservadas, mensagens user/assistant são limitadas.

#### Global Instance

```python
repo = get_repository()  # Singleton
set_repository(mock_repo)  # Dependency injection para testes
reset_repository()  # Limpar singleton
```

---

### `src/storage/repository_factory.py` - Repository Factory

Factory que seleciona repositório baseado em configuração.

```python
def get_configured_repository() -> ConversationRepository | MessageRepository:
    """
    Retorna ConvexRepository se BOTSALINHA_CONVEX__ENABLED=true
    Caso contrário, retorna SQLiteRepository (default)
    """
```

**Variáveis de Ambiente:**

- `BOTSALINHA_CONVEX__ENABLED`: "true" para habilitar Convex
- `BOTSALINHA_CONVEX__URL`: URL do deployment Convex

---

## Middleware

### `src/middleware/rate_limiter.py` - Rate Limiting

Rate limiting usando algoritmo **Token Bucket**.

#### Algoritmo Token Bucket

```
Bucket com capacidade C tokens
Refill rate: R tokens/segundo

Cada request consome 1 token
Se bucket vazio: request é limitado
```

#### Classes

**`TokenBucket`** - Bucket individual

```python
@dataclass
class TokenBucket:
    capacity: int              # Capacidade máxima
    refill_rate: float         # Tokens por segundo
    tokens: float              # Tokens atuais
    last_update: float         # Último refill timestamp

    def consume(self, tokens: int = 1) -> bool:
        """Consome tokens se disponíveis"""

    @property
    def wait_time(self) -> float:
        """Tempo até próximo token"""
```

**`UserBucket`** - Bucket com rate limit

```python
@dataclass
class UserBucket:
    bucket: TokenBucket
    limited_until: float       # Timestamp até quando está limitado

    @property
    def is_rate_limited(self) -> bool:
        """Verifica se está em rate limit"""

    def mark_rate_limited(self, duration: float) -> None:
        """Marca como rate limitado por N segundos"""
```

**`RateLimiter`** - Gerenciador principal

```python
class RateLimiter:
    def __init__(
        self,
        requests: int = 10,           # Requests por janela
        window_seconds: int = 60,     # Janela em segundos
        cleanup_interval: float = 300 # Cleanup a cada 5 min
    ):
        self.refill_rate = requests / window_seconds
        self._users: dict[str, UserBucket] = defaultdict(...)
```

#### Uso

```python
# Verificar rate limit
try:
    await rate_limiter.check_rate_limit(
        user_id=123,
        guild_id=456,  # opcional
    )
except RateLimitError as e:
    print(e.message)  # "Rate limit exceeded. Try again in 30.0 seconds."
    print(e.retry_after)  # 30.0
```

**Chave composta:** `"{user_id}:{guild_id or 'dm'}"`

Permite rate limit por usuário em cada guild separadamente.

#### Decorator

```python
@rate_limiter.check_decorator()
async def my_command(ctx: Context):
    await ctx.send("Not rate limited!")
```

#### Cleanup Automático

A cada `cleanup_interval` (default 300s), buckets não utilizados são removidos.

#### Stats

```python
stats = rate_limiter.get_stats()
# {
#     "tracked_users": 150,
#     "rate_limited_users": 5,
#     "requests_per_window": 10,
#     "window_seconds": 60
# }
```

---

## Utils

### `src/utils/retry.py` - Retry Logic

Lógica de retry com exponential backoff usando Tenacity.

#### Configuração

```python
@dataclass
class AsyncRetryConfig:
    max_attempts: int = 3               # Máximo de tentativas
    wait_min: float = 1.0               # Espera mínima (segundos)
    wait_max: float = 60.0              # Espera máxima (segundos)
    exponential_base: float = 2.0       # Base exponencial
    retryable_exceptions: tuple = (    # Exceções para retry
        APIError,
        ConnectionError,
        TimeoutError,
    )

    @classmethod
    def from_settings(cls, retry_settings):
        """Cria config de settings"""
```

#### Função `async_retry`

```python
async def async_retry(
    func: Callable[..., Awaitable[T]],
    config: AsyncRetryConfig | None = None,
    operation_name: str | None = None,
) -> T:
    """
    Executa função async com retry.

    Raises:
        RetryExhaustedError: Todas tentativas falharam
    """
```

**Exemplo de uso:**

```python
async def call_api() -> str:
    # Pode falhar
    return await external_api.call()

response = await async_retry(
    call_api,
    config=AsyncRetryConfig(max_attempts=5),
    operation_name="api_call",
)
```

#### Decorator

```python
@async_retry_decorator(max_attempts=5, operation_name="fetch_data")
async def fetch_data():
    return await api.get()
```

#### Circuit Breaker

```python
class CircuitBreaker:
    """
    Previne cascading failures.

    - Abre após N falhas
    - Permite recovery após timeout
    - Rejeita chamadas enquanto aberto
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):

    @property
    def is_open(self) -> bool:
        """Verifica se circuito está aberto"""

    async def call(self, func, *args, **kwargs):
        """Executa com proteção de circuit breaker"""
```

---

### `src/utils/errors.py` - Exception Hierarchy

Hierarquia de exceções customizadas.

#### Base Exception

```python
class BotSalinhaError(Exception):
    def __init__(self, message: str, *, details: dict | None = None):
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        """Serializa para logging"""
```

#### Tipos de Erro

| Exception | Uso | Campos Extras |
|-----------|-----|---------------|
| `APIError` | Falhas em APIs externas | `status_code`, `response_body` |
| `RateLimitError` | Rate limit excedido | `retry_after`, `limit`, `window_seconds` |
| `ValidationError` | Validação falhou | `field`, `value` |
| `DatabaseError` | Operações de DB | `query`, `table` |
| `ConfigurationError` | Config inválida/faltando | `config_key` |
| `RetryExhaustedError` | Todas tentativas de retry falharam | `last_error`, `attempts` |
| `RepositoryConfigurationError` | Config de repositório inválida | (herda de ConfigurationError) |

#### Exemplo

```python
raise APIError(
    "Google API failed",
    status_code=500,
    response_body="Internal Server Error",
)

raise RateLimitError(
    "Too many requests",
    retry_after=30.0,
    limit=10,
    window_seconds=60,
)
```

---

### `src/utils/logger.py` - Structlog Setup

Logging estruturado com contextvars.

#### Configuração

```python
def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",  # ou "text"
    log_file: str | None = None,
):
    """
    Configura structlog com processors:
    - merge_contextvars (request context)
    - add_log_level
    - TimeStamper (ISO UTC)
    - StackInfoRenderer
    - format_exc_info
    - UnicodeDecoder
    - JSONRenderer ou ConsoleRenderer
    """
```

#### Setup Completo

```python
log = setup_application_logging(
    log_level="INFO",
    log_format="json",
    app_version="1.0.0",
    app_env="production",
    debug=False,
    log_dir="/var/log/botsalinha",  # opcional
    max_bytes=10*1024*1024,          # 10MB
    backup_count=30,
    level_file="INFO",
    level_error_file="ERROR",
    sanitize=True,                    # sanitizar dados sensíveis
    sanitize_partial_debug=True,      # mascaramento parcial em DEBUG
)
```

#### Request Context

Bind context variables para todas logs no escopo:

```python
bind_request_context(
    request_id="req-123",
    user_id=456,
    guild_id=789,
    custom_field="value",
)

# Todos logs incluem contexto automaticamente
log.info("event_name", extra_data="...")
# {
#     "event": "event_name",
#     "request_id": "req-123",
#     "user_id": "456",
#     "guild_id": "789",
#     "custom_field": "value",
#     "extra_data": "...",
#     "timestamp": "2025-03-01T12:00:00Z",
#     "level": "info"
# }
```

#### Context Manager

```python
with RequestContextManager(request_id="123", user_id="456"):
    log.info("Inside context")
    # Contexto incluído automaticamente
# Contexto limpo automaticamente
```

#### Sanitização

```python
enable_sanitization(partial_debug=True)
# Logs DEBUG: user_id="u***456"
# Logs INFO+: user_id="[SANITIZED]"

disable_sanitization()
# Desabilita sanitização
```

---

## Services

### `src/services/conversation_service.py` - Conversation Service

Camada de serviço que orquestra conversas, mensagens e AI.

**Classe:** `ConversationService`

```python
class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        agent: AgentWrapper,
        message_splitter: MessageSplitter | None = None,
    ):
```

#### Métodos

**`get_or_create_conversation(user_id, guild_id, channel_id)`**

Obtém ou cria conversa para o canal:

```python
conversation = await service.get_or_create_conversation(
    user_id="123",
    guild_id="456",  # None para DMs
    channel_id="789",
)
# Returns: Conversation
```

**`process_question(question, conversation, user_id, guild_id, discord_message_id)`**

Processa pergunta completa:

1. Salva mensagem do usuário
2. Gera resposta via AI
3. Salva resposta do assistant
4. Split para Discord

```python
chunks = await service.process_question(
    question="Artigo 1º da CF?",
    conversation=conversation,
    user_id="123",
    guild_id="456",
    discord_message_id="msg-789",
)
# Returns: list[str] - chunks para enviar
```

**`clear_conversation(user_id, guild_id, channel_id)`**

Limpa conversa do usuário no canal:

```python
deleted = await service.clear_conversation(
    user_id="123",
    guild_id="456",
    channel_id="789",
)
# Returns: bool - True se deletou, False se não encontrou
```

**`get_conversation_info(conversation)`**

Retorna metadados da conversa:

```python
info = await service.get_conversation_info(conversation)
# {
#     "id": "...",
#     "user_id": "...",
#     "guild_id": "...",
#     "channel_id": "...",
#     "message_count": 10,
#     "created_at": "2025-03-01T12:00:00Z",
#     "updated_at": "2025-03-01T12:30:00Z"
# }
```

---

## RAG

### `src/rag/__init__.py` - RAG Module

Sistema completo de Retrieval-Augmented Generation.

#### Exportações Principais

**Models:**
- `Chunk`, `ChunkMetadata`, `Document`
- `ConfiancaLevel` (enum: baixa, media, alta, sem_rag)
- `RAGContext` (contexto completo de busca)

**Parsers:**
- `DOCXParser` - parsing de documentos Word

**Utils:**
- `MetadataExtractor` - extração de metadados jurídicos
- `ConfiancaCalculator` - cálculo de confiança de busca

**Services:**
- `EmbeddingService` - geração de embeddings
- `CachedEmbeddingService` - embedding com cache LRU
- `QueryService` - busca semântica e orquestração
- `CodeIngestionService` - ingestão de código
- `IngestionService` - ingestão de documentos

**Storage:**
- `VectorStore` - armazenamento e busca vetorial
- `cosine_similarity` - função de similaridade

---

### `src/rag/services/query_service.py` - Query Service

Orquestra pipeline de busca RAG.

**Classe:** `QueryService`

```python
def __init__(
    self,
    session: AsyncSession,
    embedding_service: EmbeddingService | None = None,
    vector_store: VectorStore | None = None,
    confianca_calculator: ConfiancaCalculator | None = None,
):
```

#### Pipeline de Query

```
1. Normalizar query text
2. Detectar query type (legal, code, general)
3. Gerar embedding
4. Buscar vetor store (candidate pool)
5. Aplicar fallback se necessário
6. Rerank (hybrid_lite)
7. Calcular confiança
8. Formatar fontes
9. Retornar RAGContext
```

#### Método Principal: `query`

```python
async def query(
    self,
    query_text: str,
    top_k: int | None = None,              # Default: settings.rag.top_k
    min_similarity: float | None = None,   # Default: settings.rag.min_similarity
    documento_id: int | None = None,       # Filtrar por documento
    filters: dict | None = None,           # Filtros de metadados
    retrieval_mode: str | None = None,     # hybrid_lite | semantic_only
    enable_rerank: bool | None = None,     # Habilitar rerank
    debug: bool = False,
) -> RAGContext:
```

**Retorna:**

```python
class RAGContext:
    chunks_usados: list[Chunk]        # Chunks recuperados
    similaridades: list[float]         # Scores de similaridade
    confianca: ConfiancaLevel          # Nível de confiança
    fontes: list[str]                  # Fontes formatadas
    retrieval_meta: dict               # Metadados da busca
    query_normalized: str              # Query normalizada
```

#### Query Types

**Legal Query Detection:**

```python
query_type = detect_query_type("artigo 1º CF")
# "legal" - contém termos jurídicos
```

**Code Query Detection:**

```python
query_type = detect_query_type("Python async function")
# "code" - contém termos de programação
```

#### Fallback Dinâmico

Se busca retorna poucos resultados:

```python
if len(chunks) < top_k:
    # Reduz min_similarity
    fallback_min = max(
        settings.rag.min_similarity_floor,
        min_similarity - settings.rag.min_similarity_fallback_delta,
    )
    # Busca novamente com threshold menor
```

#### Reranking (Hybrid Lite)

Combina scores semânticos, lexicais e boost de metadados:

```python
final_score = (
    alpha * semantic_score +      # Peso semântico
    beta * lexical_score +        # Peso lexical (BM25-like)
    gamma * metadata_boost        # Boost metadados
)
```

#### Métodos Especializados

**`query_by_tipo(query_text, tipo, top_k)`**

Busca com filtro por tipo de conteúdo jurídico:

- `artigo` - artigos de lei
- `jurisprudencia` - jurisprudência STF/STJ
- `questao` - questões de concurso
- `nota` - notas explicativas
- `todos` - sem filtro

```python
context = await query_service.query_by_tipo(
    query_text="direito administrativo",
    tipo="artigo",
    top_k=5,
)
```

**`query_code(query_text, language, layer, module, top_k)`**

Busca otimizada para código:

```python
context = await query_service.query_code(
    query_text="async function retry",
    language="python",
    layer="core",
    module="agent",
    top_k=5,
)
```

---

## Configurações RAG

### Settings para RAG

```python
# src/config/settings.py
class RAGSettings(BaseSettings):
    enabled: bool = True
    top_k: int = 5
    min_similarity: float = 0.5
    min_similarity_floor: float = 0.3
    min_similarity_fallback_delta: float = 0.1
    confidence_threshold: float = 0.6
    retrieval_mode: str = "hybrid_lite"
    retrieval_candidate_multiplier: int = 3
    retrieval_candidate_min: int = 10
    retrieval_candidate_cap: int = 50
    rerank_enabled: bool = True
    rerank_alpha: float = 0.7
    rerank_beta: float = 0.2
    rerank_gamma: float = 0.1
```

---

## Convenções de Código

### Nomenclatura

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Classes | PascalCase | `BotSalinhaBot`, `ConversationORM` |
| Funções/Métodos | snake_case | `generate_response`, `check_rate_limit` |
| Privados | _prefixo | `_ready_event`, `_cleanup_tasks` |
| Constantes | UPPER_SNAKE_CASE | `DISCORD_MAX_MESSAGE_LENGTH` |
| Type hints | Obrigatórios | `str | None` (não `Optional[str]`) |

### Import Order (Ruff/isort)

```python
# 1. Standard library
import asyncio
from typing import Any

# 2. Third-party
import structlog
import discord
from discord.ext import commands

# 3. Local (relative)
from ..config.settings import get_settings
from .utils.logger import setup_logging
```

### Error Handling

```python
# Sempre capturar exceções específicas
try:
    await operation()
except SpecificError as e:
    log.error("operation_failed", error=str(e))
    raise BotSalinhaError("Human message", details={"key": "value"}) from e

# NUNCA usar bare except
# except:  # ❌ RUIM
```

### Logging

```python
import structlog
log = structlog.get_logger(__name__)

# Sempre usar keyword args para contexto
log.info("event_name", user_id=user_id, guild_id=guild_id)
log.error("error_event", error_type=type(e).__name__, details=str(e))
```

### Async/Await

```python
# Sempre await coroutines
result = await async_function()  # ✓
result = async_function()        # ✗ NUNCA esqueça await

# Use async for em async iterators
async for item in async_iterator():
    process(item)
```

---

## Padrões de Design

### Repository Pattern

Interfaces abstratas em `repository.py`, implementações concretas em `sqlite_repository.py` e `convex_repository.py`.

**Benefícios:**
- Desacoplamento de código de DB
- Fácil troca de backend (SQLite ↔ Convex)
- Testabilidade com mocks

### Factory Pattern

`repository_factory.py` seleciona implementação baseado em configuração.

### Dependency Injection

Componentes recebem dependências no `__init__`:

```python
class AgentWrapper:
    def __init__(self, repository: MessageRepository):
        self.repository = repository
```

### Singleton com Cache

Settings usam `@lru_cache`:

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## Testes

### Fixtures Principais (`tests/conftest.py`)

| Fixture | Descrição |
|---------|-----------|
| `test_settings` | Settings configuradas para testes |
| `test_engine` | SQLAlchemy engine (in-memory SQLite) |
| `test_session` | Async session scoped |
| `test_repository` | SQLiteRepository in-memory |
| `rate_limiter` | RateLimiter instance |

### Exemplo de Teste

```python
@pytest.mark.asyncio
async def test_create_conversation(test_repository):
    conversation = await test_repository.create_conversation(
        ConversationCreate(
            user_id="123",
            guild_id="456",
            channel_id="789",
        )
    )

    assert conversation.id is not None
    assert conversation.user_id == "123"
```

---

## Performance

### Otimizações

1. **SQLite WAL Mode** - Melhora concorrência
2. **Connection Pooling** - SQLAlchemy async
3. **LRU Cache** - Embeddings cacheados
4. **Vector Indexing** - Busca vetorial otimizada
5. **Lazy Loading** - Relationships SQLAlchemy
6. **Token Bucket** - Rate limiting O(1)

### Monotoring

Logs estruturados permitem tracking de:

- Latência de AI calls
- Hit rate de RAG
- Quantidade de rate limits
- Erros por tipo
- Performance de queries

---

## Segurança

### Sanitização

Input sanitizado em `agent.py`:

```python
from ..utils.input_sanitizer import sanitize_user_input

sanitized = sanitize_user_input(user_prompt)
```

### Rate Limiting

Prevenção de abuse por usuário:

- Token bucket por usuário/guild
- Cleanup automático de entradas stale
- Cooldowns configuráveis

### Secrets

API keys em environment variables:

```python
google_api_key = settings.get_google_api_key()
# Never hardcoded
```

---

## Deploy

### Variáveis de Ambiente Obrigatórias

```bash
BOTSALINHA_DISCORD__TOKEN=seu_discord_token
BOTSALINHA_GOOGLE__API_KEY=sua_google_api_key
# OU
BOTSALINHA_OPENAI__API_KEY=sua_openai_api_key
```

### Docker

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

---

## Troubleshooting

### Problemas Comuns

**"repository is required for AgentWrapper"**

```python
# Sempre passar repository
agent = AgentWrapper(repository=repo)  # ✓
agent = AgentWrapper()  # ✗ ValueError
```

**"Circuit breaker is open"**

Circuit breaker aberto após muitas falhas. Aguarde `recovery_timeout`.

**"Rate limit exceeded"**

Aguarde `retry_after` segundos antes de tentar novamente.

### Debug Mode

```bash
# Habilitar debug
BOTSALINHA_DEBUG=true uv run botsalinha

# Logs em texto (não JSON)
BOTSALINHA_LOG_FORMAT=text uv run botsalinha
```

---

## Diagramas de Arquitetura

### 1. Fluxo de Mensagens Discord

Diagrama completo do fluxo de uma mensagem do usuário até a resposta do bot:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DISCORD MESSAGE FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ Discord User │
│  "!ask ..."  │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BotSalinhaBot                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 1. on_message()                                                     │  │
│  │    - Ignora bots                                                     │  │
│  │    - Bind request context (tracing)                                 │  │
│  │    - Verifica prefixo                                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 2. ask_command(ctx, question)                                        │  │
│  │    - await ctx.typing()                                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RateLimiter (Middleware)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Token Bucket Algorithm                                               │  │
│  │                                                                      │  │
│  │ key = "{user_id}:{guild_id}"                                        │  │
│  │                                                                      │  │
│  │ if bucket.tokens >= 1:                                              │  │
│  │     bucket.consume(1)                                               │  │
│  │     ✓ PASS                                                          │  │
│  │ else:                                                                │  │
│  │     ✗ RAISE RateLimitError                                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ConversationService (Service Layer)                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ get_or_create_conversation(user_id, guild_id, channel_id)            │  │
│  │                                                                      │  │
│  │ Repository: ──→ conversation_repo.get_or_create(...)                 │  │
│  │                 │                                                     │  │
│  │                 ▼                                                     │  │
│  │           ConversationORM                                             │  │
│  │           - id (UUID)                                                 │  │
│  │           - user_id                                                   │  │
│  │           - guild_id                                                  │  │
│  │           - channel_id                                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ process_question(question, conversation, ...)                        │  │
│  │                                                                      │  │
│  │ Step 1: Save user message                                            │  │
│  │   ──→ message_repo.create_message(role="user", content=question)     │  │
│  │                                                                      │  │
│  │ Step 2: Generate AI response                                         │  │
│  │   ──→ agent.generate_response_with_rag(prompt, conversation_id)     │  │
│  │                                                                      │  │
│  │ Step 3: Save assistant response                                      │  │
│  │   ──→ message_repo.create_message(role="assistant", content=resp)   │  │
│  │                                                                      │  │
│  │ Step 4: Split response for Discord                                   │  │
│  │   ──→ message_splitter.split(response)                               │  │
│  │       Returns: list[str] (chunks ≤ 2000 chars)                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AgentWrapper (AI Layer)                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ generate_response_with_rag(prompt, conversation_id, user_id, ...)    │  │
│  │                                                                      │  │
│  │ IF RAG enabled:                                                      │  │
│  │   ┌──────────────────────────────────────────────────────────────┐   │  │
│  │   │ 1. QueryService.query(prompt_text)                           │   │  │
│  │   │    - Normalize query                                         │   │  │
│  │   │    - Generate embedding                                      │   │  │
│  │   │    - Search vector store                                     │   │  │
│  │   │    - Rerank results                                          │   │  │
│  │   │    - Calculate confidence                                    │   │  │
│  │   │    Returns: RAGContext                                       │   │  │
│  │   └──────────────────────────────────────────────────────────────┘   │  │
│  │                                │                                       │  │
│  │                                ▼                                       │  │
│  │   ┌──────────────────────────────────────────────────────────────┐   │  │
│  │   │ 2. Build Prompt                                              │   │  │
│  │   │    - RAG context (if confidence >= média)                    │   │  │
│  │   │    - Conversation history (last N pairs)                     │   │  │
│  │   │    - Current user message                                    │   │  │
│  │   └──────────────────────────────────────────────────────────────┘   │  │
│  │                                │                                       │  │
│  │                                ▼                                       │  │
│  │   ┌──────────────────────────────────────────────────────────────┐   │  │
│  │   │ 3. Agno Agent.generate(prompt)                               │   │  │
│  │   │    │                                                         │   │  │
│  │   │    ├──→ Google Gemini 2.5 Flash Lite                         │   │  │
│  │   │    │    - Model ID: gemini-2.5-flash-lite                    │   │  │
│  │   │    │    - Streaming response                                 │   │  │
│  │   │    │                                                         │   │  │
│  │   │    └──→ OR OpenAI GPT (alternative)                          │   │  │
│  │   └──────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│                     Returns: str (response)                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Discord Response (send chunks)                          │
│                                                                              │
│  for chunk in response_chunks:                                              │
│      await ctx.send(chunk)                                                   │
│                                                                              │
│  User receives complete response in Discord channel                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 2. Pipeline RAG (Retrieval-Augmented Generation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RAG QUERY PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ User Query   │
│ "Artigo 1º   │
│  da CF?"      │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STEP 1: NORMALIZE                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ QueryService._normalize_query(query_text)                            │  │
│  │                                                                      │  │
│  │ - Trim whitespace                                                    │  │
│  │ - Remove excess spaces                                               │  │
│  │ - Normalize accents (UTF-8)                                         │  │
│  │ - Lowercase (optional)                                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 2: DETECT QUERY TYPE                                │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ QueryType Detection                                                  │  │
│  │                                                                      │  │
│  │ Legal Terms:     artigo, lei, decreto, jurisprudência, STF, STJ     │  │
│  │ Code Terms:      function, class, async, python, typescript         │  │
│  │ General:         (default)                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 3: GENERATE EMBEDDING                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ EmbeddingService (CachedEmbeddingService)                            │  │
│  │                                                                      │  │
│  │ 1. Check LRU cache                                                   │  │
│  │    key = f"embedding:{query_text}"                                   │  │
│  │    │                                                                 │  │
│  │    ├── HIT  → Return cached embedding                                │  │
│  │    │                                                                 │  │
│  │    └── MISS → Generate new embedding                                 │  │
│  │              │                                                       │  │
│  │              ├──→ Google Gemini Embeddings                           │  │
│  │              │    - Model: text-embedding-004                        │  │
│  │              │    - Dimension: 768                                   │  │
│  │              │                                                        │  │
│  │              └──→ Cache result (maxsize=1000)                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│                     Returns: vector[float]                                  │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 4: VECTOR SEARCH                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ VectorStore.similarity_search(embedding, top_k, min_similarity)      │  │
│  │                                                                      │  │
│  │ Algorithm:                                                           │  │
│  │   1. Load all chunks with embeddings from DB                         │  │
│  │   2. Calculate cosine_similarity(query_emb, chunk_emb)               │  │
│  │                                                                      │  │
│  │ cosine_similarity(A, B) = (A · B) / (||A|| * ||B||)                 │  │
│  │                                                                      │  │
│  │   3. Filter by min_similarity                                       │  │
│  │   4. Sort descending                                                │  │
│  │   5. Return top_k chunks                                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ DYNAMIC FALLBACK                                                     │  │
│  │                                                                      │  │
│  │ IF len(chunks) < top_k:                                              │  │
│  │     new_min = max(min_similarity_floor,                              │  │
│  │                  min_similarity - fallback_delta)                    │  │
│  │     Search again with lower threshold                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│                    Returns: list[Chunk + similarity]                        │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 5: RERANK (Hybrid Lite)                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ RetrievalRanker.rerank(query, chunks, mode="hybrid_lite")            │  │
│  │                                                                      │  │
│  │ For each chunk:                                                      │  │
│  │   ┌────────────────────────────────────────────────────────────┐     │  │
│  │   │ semantic_score = cosine_similarity (already computed)       │     │  │
│  │   │                                                             │     │  │
│  │   │ lexical_score = bm25_like(query, chunk.text)                │     │  │
│  │   │   - Term frequency                                          │     │  │
│  │   │   - Exact match bonus                                       │     │  │
│  │   │                                                             │     │  │
│  │   │ metadata_boost = 0.0                                        │     │  │
│  │   │   IF query_type == "legal" AND chunk.tipo == "artigo":      │     │  │
│  │   │       metadata_boost += 0.1                                 │     │  │
│  │   │   IF query_type == "code" AND chunk.language == "python":   │     │  │
│  │   │       metadata_boost += 0.1                                 │     │  │
│  │   │                                                             │     │  │
│  │   │ final_score = α*semantic + β*lexical + γ*metadata            │     │  │
│  │   │              = 0.7*semantic + 0.2*lexical + 0.1*metadata     │     │  │
│  │   └────────────────────────────────────────────────────────────┘     │  │
│  │                                                                      │  │
│  │ Sort by final_score DESC                                             │  │
│  │ Return top_k reranked chunks                                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 6: CALCULATE CONFIDENCE                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ ConfiancaCalculator.calculate(chunks, similaridades)                 │  │
│  │                                                                      │  │
│  │ mean_confidence = mean(similaridades)                                │  │
│  │ max_confidence = max(similaridades)                                  │  │
│  │                                                                      │  │
│  │ IF mean_confidence >= 0.75:   return ConfiancaLevel.ALTA            │  │
│  │ IF mean_confidence >= 0.60:   return ConfiancaLevel.MEDIA           │  │
│  │ IF mean_confidence >= 0.45:   return ConfiancaLevel.BAIXA           │  │
│  │                             return ConfiancaLevel.SEM_RAG            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 7: FORMAT SOURCES                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Format fontes for user display                                       │  │
│  │                                                                      │  │
│  │ sources = []                                                         │  │
│  │ FOR chunk IN chunks:                                                 │  │
│  │     IF chunk.tipo == "artigo":                                       │  │
│  │         source = f"Artigo {chunk.numero} - {chunk.documento_nome}"   │  │
│  │     ELIF chunk.tipo == "questao":                                    │  │
│  │         source = f"Questão {chunk.ano} - {chunk.banca}"              │  │
│  │     ELIF chunk.tipo == "code":                                       │  │
│  │         source = f"{chunk.file}:{chunk.line_start}-{chunk.line_end}" │  │
│  │     ELSE:                                                            │  │
│  │         source = chunk.documento_nome                                │  │
│  │     sources.append(source)                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 8: RETURN RAG CONTEXT                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ RAGContext                                                           │  │
│  │ {                                                                    │  │
│  │     chunks_usados: list[Chunk],          # Reranked chunks           │  │
│  │     similaridades: list[float],          # Final scores              │  │
│  │     confianca: ConfiancaLevel,           # ALTA/MEDIA/BAIXA/SEM_RAG  │  │
│  │     fontes: list[str],                   # Formatted sources         │  │
│  │     retrieval_meta: {                    # Debug metadata            │  │
│  │         "query_type": "legal",                                        │  │
│  │         "initial_count": 15,                                           │  │
│  │         "fallback_triggered": true,                                    │  │
│  │         "reranked_count": 5                                            │  │
│  │     },                                                                 │  │
│  │     query_normalized: str                                            │  │
│  │ }                                                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           │                                                 │
│                           ▼                                                 │
│              Passed to AgentWrapper.generate_response_with_rag()            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 3. Repository Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      REPOSITORY PATTERN                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────┐
                    │   Application Layer         │
                    │   (AgentWrapper,            │
                    │    ConversationService)     │
                    └────────────┬────────────────┘
                                 │ Depends on
                                 ▼
        ┌────────────────────────────────────────────────┐
        │         Abstract Interfaces (ABC)              │
        │  src/storage/repository.py                     │
        │                                                │
        │  ┌──────────────────────────────────────────┐  │
        │  │ ConversationRepository (ABC)             │  │
        │  │  + create_conversation(...)              │  │
        │  │  + get_conversation_by_id(...)           │  │
        │  │  + get_by_user_and_guild(...)            │  │
        │  │  + get_or_create_conversation(...)       │  │
        │  │  + update_conversation(...)              │  │
        │  │  + delete_conversation(...)              │  │
        │  │  + cleanup_old_conversations(...)        │  │
        │  └──────────────────────────────────────────┘  │
        │                                                │
        │  ┌──────────────────────────────────────────┐  │
        │  │ MessageRepository (ABC)                  │  │
        │  │  + create_message(...)                   │  │
        │  │  + get_message_by_id(...)                │  │
        │  │  + get_conversation_messages(...)         │  │
        │  │  + get_conversation_history(...)          │  │
        │  │  + update_message(...)                   │  │
        │  │  + delete_message(...)                   │  │
        │  │  + delete_conversation_messages(...)      │  │
        │  └──────────────────────────────────────────┘  │
        └────────────────┬───────────────────────────────┘
                         │ Implemented by
                         ▼
        ┌────────────────────────────────────────────────────────────────┐
        │              Concrete Implementations                          │
        └────────────────────────────────────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                │
         ▼                                ▼
┌──────────────────────┐      ┌──────────────────────────┐
│  SQLiteRepository    │      │  ConvexRepository        │
│  (default)           │      │  (optional)              │
├──────────────────────┤      ├──────────────────────────┤
│ src/storage/         │      │ src/storage/             │
│ sqlite_repository.py │      │ convex_repository.py     │
├──────────────────────┤      ├──────────────────────────┤
│ - SQLAlchemy async   │      │ - Convex SDK             │
│ - AsyncSession       │      │ - WebSocket client       │
│ - aiosqlite driver   │      │ - Real-time sync         │
├──────────────────────┤      ├──────────────────────────┤
│ DB: SQLite file      │      │ DB: Convex cloud         │
│      │               │      │      │                   │
│      ▼               │      │      ▼                   │
│ ┌─────────────────┐  │      │ ┌─────────────────────┐ │
│ │conversations    │  │      │ │conversations table  │ │
│ │messages         │  │      │ │messages table       │ │
│ │rag_documents    │  │      │ │rag_documents table  │ │
│ │rag_chunks       │  │      │ │rag_chunks table     │ │
│ └─────────────────┘  │      │ └─────────────────────┘ │
└──────────────────────┘      └──────────────────────────┘
         │                                │
         └────────────┬───────────────────┘
                      │ Selected by
                      ▼
        ┌──────────────────────────────────────┐
        │    Repository Factory                │
        │  src/storage/repository_factory.py   │
        │                                       │
        │  def get_configured_repository():    │
        │      IF settings.convex.enabled:     │
        │          return ConvexRepository()    │
        │      ELSE:                           │
        │          return SQLiteRepository()    │
        └──────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA FLOW: REPOSITORY PATTERN                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ USAGE EXAMPLE                                                               │
└─────────────────────────────────────────────────────────────────────────────┘

  # Application code depends on ABSTRACT interface
  repo: ConversationRepository = get_configured_repository()

  # Can switch implementations without changing application code
  conversation = await repo.create_conversation(
      ConversationCreate(user_id="123", guild_id="456", channel_id="789")
  )


┌─────────────────────────────────────────────────────────────────────────────┐
│ BENEFITS                                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

  ✓ Decoupling: Application logic independent of database implementation
  ✓ Testability: Easy to mock repositories in tests
  ✓ Flexibility: Switch between SQLite and Convex via configuration
  ✓ Maintainability: Clear separation of concerns
  ✓ Type Safety: Abstract methods enforce interface compliance
```

---

### 4. Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BOTSALINHA - SYSTEM ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: PRESENTATION (Discord Interface)                                   │
│ src/core/discord.py                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                    Discord Events                                    │
  │                                                                       │
  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │
  │  │ on_ready  │  │ on_message│  │ on_error  │  │ Commands  │        │
  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘        │
  │        │               │               │               │              │
  │        └───────────────┴───────────────┴───────────────┘              │
  │                            │                                          │
  │                            ▼                                          │
  │              BotSalinhaBot(commands.Bot)                              │
  │              - Prefix: "!"                                             │
  │              - Intents: message_content, guilds                        │
  │                                                                       │
  │  Commands:                                                            │
  │  - !ask <question>    → Main AI interaction                           │
  │  - !ping              → Health check                                  │
  │  - !ajuda / !help     → Show help                                     │
  │  - !limpar / !clear   → Clear conversation                            │
  │  - !info              → Bot information                               │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: MIDDLEWARE (Rate Limiting & Request Processing)                   │
│ src/middleware/rate_limiter.py                                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                        RateLimiter                                    │
  │                                                                       │
  │  Algorithm: Token Bucket                                             │
  │                                                                       │
  │  ┌──────────────────────────────────────────────────────────────┐   │
  │  │  IF check_rate_limit(user_id, guild_id):                      │   │
  │  │      PASS → Process request                                  │   │
  │  │  ELSE:                                                        │   │
  │  │      RAISE RateLimitError (retry_after)                       │   │
  │  └──────────────────────────────────────────────────────────────┘   │
  │                                                                       │
  │  Key: "{user_id}:{guild_id or 'dm'}"                                 │
  │  Config: requests/window_seconds from settings                       │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: SERVICE (Business Logic Orchestration)                            │
│ src/services/conversation_service.py                                        │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                   ConversationService                                 │
  │                                                                       │
  │  Responsibilities:                                                   │
  │  - Get/create conversations                                          │
  │  - Process questions (orchestrate AI flow)                           │
  │  - Manage conversation history                                       │
  │  - Split messages for Discord                                        │
  │                                                                       │
  │  ┌────────────────────────────────────────────────────────────┐     │
  │  │ process_question(question, conversation, user_id, ...)      │     │
  │  │                                                             │     │
  │  │  1. Save user message via MessageRepository                 │     │
  │  │  2. Generate AI response via AgentWrapper                   │     │
  │  │  3. Save assistant response via MessageRepository           │     │
  │  │  4. Split response into chunks (≤2000 chars)                │     │
  │  │  5. Return chunks for Discord sending                       │     │
  │  └────────────────────────────────────────────────────────────┘     │
  │                                                                       │
  │  Dependencies:                                                        │
  │  - ConversationRepository                                            │
  │  - MessageRepository                                                  │
  │  - AgentWrapper                                                       │
  │  - MessageSplitter                                                    │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: AI/AGGREGATION (Agno Agent + RAG)                                  │
│ src/core/agent.py + src/rag/                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                        AgentWrapper                                   │
  │                                                                       │
  │  Responsibilities:                                                   │
  │  - Load system prompt from file                                      │
  │  - Manage conversation history                                       │
  │  - Orchestrate RAG pipeline                                          │
  │  - Call Agno Agent (Gemini/OpenAI)                                   │
  │  - Save messages to repository                                       │
  │                                                                       │
  │  ┌────────────────────────────────────────────────────────────┐     │
  │  │ generate_response_with_rag(prompt, conversation_id, ...)    │     │
  │  │                                                             │     │
  │  │  IF RAG enabled:                                            │     │
  │  │    │                                                        │     │
  │  │    ├──→ QueryService.query(prompt_text)                     │     │
  │  │    │    - Normalize                                        │     │
  │  │    │    - Generate embedding (cached)                       │     │
  │  │    │    - Search vector store                              │     │
  │  │    │    - Rerank results                                   │     │
  │  │    │    - Calculate confidence                             │     │
  │  │    │    Returns: RAGContext                                 │     │
  │  │    │                                                        │     │
  │  │    ├──→ Build prompt with RAG context + history            │     │
  │  │    │                                                        │     │
  │  │    └──→ Agno Agent.generate(prompt)                         │     │
  │  │         │                                                   │     │
  │  │         ├──→ Google Gemini 2.5 Flash Lite (default)        │     │
  │  │         └──→ OpenAI GPT (alternative)                       │     │
  │  │                                                             │     │
  │  │  ELSE:                                                       │     │
  │  │    Generate without RAG (history only)                       │     │
  │  └────────────────────────────────────────────────────────────┘     │
  │                                                                       │
  │  Dependencies:                                                        │
  │  - MessageRepository (OBRIGATORY)                                    │
  │  - QueryService (if RAG enabled)                                     │
  │  - Agno Agent                                                        │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: DATA ACCESS (Repository Pattern)                                  │
│ src/storage/repository.py + sqlite_repository.py                            │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │              Repository Interfaces (ABC)                             │
  │                                                                       │
  │  ConversationRepository              MessageRepository               │
  │  - create_conversation                - create_message                │
  │  - get_conversation_by_id             - get_message_by_id             │
  │  - get_by_user_and_guild              - get_conversation_messages     │
  │  - get_or_create_conversation          - get_conversation_history      │
  │  - update_conversation                - update_message                │
  │  - delete_conversation                - delete_message                │
  │  - cleanup_old_conversations          - delete_conversation_messages  │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │ Implemented by
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                 SQLiteRepository (default)                           │
  │                                                                       │
  │  Technology:                                                         │
  │  - SQLAlchemy async ORM                                              │
  │  - aiosqlite driver                                                  │
  │  - WAL mode (Write-Ahead Logging)                                    │
  │  - Connection pooling                                                │
  │                                                                       │
  │  Tables:                                                             │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │ conversations                                             │    │
  │  │ - id: UUID (PK)                                            │    │
  │  │ - user_id: str (indexed)                                   │    │
  │  │ - guild_id: str | None (indexed)                           │    │
  │  │ - channel_id: str (indexed)                                │    │
  │  │ - created_at, updated_at                                   │    │
  │  │ - meta_data: JSON                                          │    │
  │  │                                                             │    │
  │  │  Relationship: messages (one-to-many)                       │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  │                                                                       │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │ messages                                                   │    │
  │  │ - id: UUID (PK)                                            │    │
  │  │ - conversation_id: UUID (FK → conversations)               │    │
  │  │ - role: "user" | "assistant" | "system"                    │    │
  │  │ - content: str                                             │    │
  │  │ - discord_message_id: str | None (indexed)                 │    │
  │  │ - created_at                                               │    │
  │  │ - meta_data: JSON                                          │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  │                                                                       │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │ rag_documents                                             │    │
  │  │ - id: int (PK, auto-increment)                             │    │
  │  │ - nome: str (indexed)                                      │    │
  │  │ - arquivo_origem: str                                      │    │
  │  │ - content_hash: str | None (unique, indexed)               │    │
  │  │ - chunk_count: int                                         │    │
  │  │ - token_count: int                                         │    │
  │  │ - created_at                                               │    │
  │  │                                                             │    │
  │  │  Relationship: chunks (one-to-many, cascade delete)         │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  │                                                                       │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │ rag_chunks                                                 │    │
  │  │ - id: str (PK)                                             │    │
  │  │ - documento_id: int (FK → rag_documents)                   │    │
  │  │ - texto: str                                               │    │
  │  │ - metadados: JSON                                          │    │
  │  │ - token_count: int                                         │    │
  │  │ - embedding: bytes | None (float32 serialized)             │    │
  │  │ - created_at                                               │    │
  │  │                                                             │    │
  │  │  Relationship: documento (many-to-one)                      │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 6: DATABASE (SQLite Local File)                                       │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                     SQLite Database File                             │
  │                                                                       │
  │  Path: {BOTSALINHA_DATABASE_URL}                                     │
  │  Default: sqlite:///data/botsalinha.db                               │
  │                                                                       │
  │  Optimizations:                                                      │
  │  - PRAGMA journal_mode=WAL        (better concurrency)               │
  │  - PRAGMA synchronous=NORMAL       (balance performance/safety)       │
  │  - PRAGMA cache_size=-64000        (64MB cache)                      │
  │  - PRAGMA temp_store=memory        (temp tables in RAM)              │
  │                                                                       │
  │  Migrations: Alembic                                                │
  │  - migrations/versions/                                             │
  │  - Auto-generate: alembic revision --autogenerate                    │
  │  - Apply: alembic upgrade head                                      │
  └──────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         CROSS-CUTTING CONCERNS                             │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                        Utilities                                      │
  │  src/utils/                                                           │
  │                                                                       │
  │  - logger.py          → Structured logging (JSON/text)               │
  │  - errors.py          → Exception hierarchy (BotSalinhaError)        │
  │  - retry.py           → Async retry with exponential backoff         │
  │  - input_sanitizer.py → User input sanitization                      │
  └───────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                      Configuration                                   │
  │  src/config/                                                          │
  │                                                                       │
  │  - settings.py      → Pydantic Settings (env vars)                   │
  │  - yaml_config.py   → YAML config loader                             │
  │                                                                       │
  │  Environment Variables (BOTSALINHA_ prefix):                         │
  │  - DISCORD__TOKEN                                                     │
  │  - GOOGLE__API_KEY                                                   │
  │  - DATABASE__URL                                                     │
  │  - RATE_LIMIT__REQUESTS                                              │
  │  - RAG__ENABLED                                                       │
  └───────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │                      Lifecycle Management                            │
  │  src/core/lifecycle.py                                                │
  │                                                                       │
  │  - GracefulShutdown signal handling                                  │
  │  - SIGINT (Ctrl+C)                                                   │
  │  - SIGTERM (kill)                                                    │
  │  - Cleanup tasks execution                                           │
  └───────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW SUMMARY                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  Discord Message → BotSalinhaBot → RateLimiter →
  ConversationService → AgentWrapper → (RAG: QueryService) →
  Agno Agent (Gemini) → Response → Split → Discord Send
                     │
                     └──→ Repository → SQLite Database
```

---

## Referências

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Agno Framework](https://github.com/agno-agi/agno)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Structlog](https://www.structlog.org/)
- [Tenacity](https://tenacity.readthedocs.io/)

---

**Última atualização:** 2025-03-01
**Versão:** 1.0.0
