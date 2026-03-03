# Guia do Desenvolvedor - BotSalinha

Este guia fornece informações completas para desenvolvedores que trabalham no BotSalinha.

## Sumário

1. [Instruções de Configuração](#1-instruções-de-configuração)
2. [Visão Geral da Estrutura do Projeto](#2-visão-geral-da-estrutura-do-projeto)
3. [Fluxo de Trabalho de Desenvolvimento](#3-fluxo-de-trabalho-de-desenvolvimento)
4. [Desenvolvimento RAG](#4-desenvolvimento-rag)
5. [ChromaDB Vector Store](#5-chromadb-vector-store)
6. [Abordagem de Teste](#6-abordagem-de-teste)
7. [Solução de Problemas](#7-solução-de-problemas)

---

## 1. Instruções de Configuração

### Pré-requisitos

- **Python**: 3.12 ou superior
- **uv**: Gerenciador de pacotes Python moderno
- **Git**: Para controle de versão
- **Docker** (opcional): Para desenvolvimento em container

### Configuração Inicial

#### 1. Clone o Repositório

```bash
git clone <repository-url>
cd BotSalinha
```

#### 2. Instale as Dependências

```bash
# Instalar uv se não tiver instalado
# **Security Note:** Download the script first, review it, then execute.
# Method 1: Two-step installation (recommended for production)
wget https://astral.sh/uv/install.sh -O /tmp/uv-install.sh
# Review the script: cat /tmp/uv-install.sh
sh /tmp/uv-install.sh

# Method 2: Direct pipe (development environments only)
# curl -LsSf https://astral.sh/uv/install.sh | sh

# Sincronizar dependências
uv sync
```

#### 3. Configure Variáveis de Ambiente

```bash
# Copiar template de ambiente
cp .env.example .env

# Editar .env com suas credenciais
# Variáveis obrigatórias:
# - DISCORD_BOT_TOKEN
# - GOOGLE_API_KEY
```

#### 4. Ative o Ambiente Virtual

```bash
# O uv cria o ambiente automaticamente
source .venv/bin/activate  # Linux/macOS
```

**Windows (CMD):**

```cmd
.venv\Scripts\activate
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

#### 5. Instale Hooks de Pre-commit

```bash
uv run pre-commit install
```

### Verificação da Configuração

Execute os seguintes comandos para verificar se tudo está funcionando:

```bash
# Verificar versão do Python
uv run python --version

# Executar testes
uv run pytest

# Verificar lint
uv run ruff check src/

# Verificar tipos
uv run mypy src/
```

---

## 2. Visão Geral da Estrutura do Projeto

### Diretórios Principais

```text
BotSalinha/
├── bot.py                      # Ponto de entrada principal
├── pyproject.toml              # Dependências e configuração do projeto
├── .env.example                # Template de variáveis de ambiente
│
├── src/                        # Código fonte principal
│   ├── __init__.py
│   ├── main.py                 # Função principal da aplicação
│   │
│   ├── config/                 # Configuração
│   │   └── settings.py         # Pydantic Settings com validação
│   │
│   ├── core/                   # Componentes centrais
│   │   ├── agent.py            # Wrapper do Agno AI Agent
│   │   ├── discord.py          # Bot Discord com comandos
│   │   └── lifecycle.py        # Gerenciamento de ciclo de vida
│   │
│   ├── models/                 # Modelos de dados
│   │   ├── conversation.py     # Modelo Conversação (SQLAlchemy + Pydantic)
│   │   ├── message.py          # Modelo Mensagem (SQLAlchemy + Pydantic)
│   │   └── rag_models.py       # Modelos RAG (Document, Chunk)
│   │
│   ├── rag/                    # Retrieval-Augmented Generation
│   │   ├── __init__.py
│   │   ├── models.py           # Modelos Pydantic RAG
│   │   ├── parser/             # Parsers de documentos
│   │   │   ├── chunker.py      # Extrator de chunks
│   │   │   ├── docx_parser.py  # Parser DOCX
│   │   │   ├── code_chunker.py # Chunker especializado para código
│   │   │   └── xml_parser.py   # Parser XML (Repomix)
│   │   ├── services/           # Serviços RAG
│   │   │   ├── ingestion_service.py  # Ingestão de documentos
│   │   │   ├── code_ingestion_service.py  # Ingestão de codebase
│   │   │   ├── embedding_service.py     # Geração de embeddings
│   │   │   └── query_service.py         # Consulta RAG
│   │   ├── storage/           # Persistência RAG
│   │   │   ├── rag_repository.py       # Repositório RAG
│   │   │   └── vector_store.py         # Vector store abstrato
│   │   └── utils/             # Utilitários RAG
│   │       └── code_metadata_extractor.py  # Extração de metadados de código
│   │
│   ├── storage/                # Camada de persistência
│   │   ├── repository.py       # Interfaces abstratas de repositório
│   │   └── sqlite_repository.py# Implementação SQLite
│   │
│   ├── utils/                  # Utilitários
│   │   ├── logger.py           # Configuração structlog
│   │   ├── errors.py           # Exceções customizadas
│   │   └── retry.py            # Lógica de retry com tenacity
│   │
│   └── middleware/             # Middleware
│       └── rate_limiter.py     # Limitação de taxa (token bucket)
│
├── tests/                      # Suíte de testes
│   ├── conftest.py             # Configuração pytest e fixtures
│   ├── unit/                   # Testes unitários
│   │   ├── test_rate_limiter.py
│   │   └── rag/                # Testes RAG unitários
│   │       ├── test_code_chunker.py
│   │       ├── test_code_metadata_extractor.py
│   │       ├── test_xml_parser.py
│   │       └── test_rag_repository.py
│   ├── integration/            # Testes de integração
│   │   └── rag/
│   │       └── test_code_ingestion.py
│   └── e2e/                    # Testes end-to-end
│       └── ...
│
├── migrations/                 # Migrações Alembic
│   ├── alembic.ini             # Configuração Alembic
│   ├── env.py                  # Ambiente de migração
│   └── versions/               # Arquivos de migração
│
├── scripts/                    # Scripts utilitários
│   ├── backup.py               # Script de backup do SQLite
│   └── ingest_codebase_rag.py  # Script de ingestão de codebase RAG
│
├── docs/                       # Documentação
│   ├── deployment.md           # Guia de implantação
│   └── operations.md           # Manual de operações
│
├── data/                       # Banco de dados SQLite (gitignore)
├── logs/                       # Logs da aplicação (gitignore)
└── backups/                    # Backups do banco (gitignore)
```

### Arquitetura em Camadas

```text
┌─────────────────────────────────────────────────┐
│           Camada de Apresentação                │
│  (Discord Bot, Comandos, Event Handlers)        │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Middleware                  │
│     (Rate Limiting, Error Handling)             │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│            Camada de Serviço                    │
│     (Agent Wrapper, Business Logic)             │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│         Camada de Acesso a Dados                │
│  (Repository Pattern, SQLAlchemy ORM)           │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│              Camada de Dados                    │
│           (SQLite Database)                     │
└─────────────────────────────────────────────────┘
```

### Fluxo de Dados

```text
Usuário Discord
    │
    ▼
!ask pergunta
    │
    ▼
Discord Bot → Rate Limiter → Agent Wrapper
                                   │
                                   ▼
                            Conversation History
                                   │
                                   ▼
                            Gemini 2.0 Flash
                                   │
                                   ▼
                            Resposta Formatada
                                   │
                                   ▼
                            Salvar no SQLite
                                   │
                                   ▼
                            Enviar para Discord
```

---

## 3. Fluxo de Trabalho de Desenvolvimento

### Branch Strategy

```text
main           ← Branch de produção
├── develop    ← Branch de desenvolvimento
│   ├── feature/feature-name    ← Novas funcionalidades
│   └── bugfix/bug-name         ← Correções de bugs
└── hotfix/issue-name           ← Correções urgentes (branch a partir de main)
```

### Processo de Desenvolvimento

#### 1. Crie uma Branch

```bash
git checkout -b feature/nova-funcionalidade
```

#### 2. Faça Suas Alterações

```bash
# Editar arquivos
# Executar testes
uv run pytest

# Formatar código
uv run ruff format src/

# Verificar lint
uv run ruff check src/

# Verificar tipos
uv run mypy src/
```

#### 3. Commit suas Mudanças

```bash
git add .
git commit -m "feat: adicionar nova funcionalidade"
```

**Convenções de Commit:**

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Mudanças na documentação
- `style:` Formatação, ponto e vírgula, etc.
- `refactor:` Refatoração de código
- `test:` Adiciona ou modifica testes
- `chore:` Atualização de tarefas, configs, etc.

#### 4. Push e Pull Request

```bash
git push origin feature/nova-funcionalidade
```

Crie um Pull Request no GitHub com descrição das mudanças.

### Comandos Comuns de Desenvolvimento

#### Executar o Bot Localmente

```bash
uv run bot.py
```

#### Executar Testes Específicos

```bash
# Todos os testes
uv run pytest

# Teste específico
uv run pytest tests/test_rate_limiter.py

# Com coverage
uv run pytest --cov=src --cov-report=html

# Verbose
uv run pytest -v
```

#### Trabalhar com Migrações

```bash
# Criar migração
uv run alembic revision --autogenerate -m "descricao"

# Aplicar migrações
uv run alembic upgrade head

# Reverter última migração
uv run alembic downgrade -1

# Ver histórico
uv run alembic history
```

#### Lint e Formatação

```bash
# Verificar problemas
uv run ruff check src/

# Auto-corrigir problemas
uv run ruff check --fix src/

# Formatar código
uv run ruff format src/

# Verificar formatação sem modificar
uv run ruff format --check src/
```

#### Type Checking

```bash
# Verificar tipos
uv run mypy src/

# Verificar arquivo específico
uv run mypy src/core/agent.py
```

#### Comandos RAG

```bash
# Ingerir codebase no RAG (substitui documento existente)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "botsalinha-codebase" --replace

# Ingestão seca (apenas parse, sem salvar no banco)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run

# Ingestão com nome customizado
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "meu-projeto"

# Testes RAG unitários
uv run pytest tests/unit/rag/ -v

# Testes RAG de integração
uv run pytest tests/integration/rag/ -v

# Teste específico RAG
uv run pytest tests/unit/rag/test_code_chunker.py -v

# Gerar XML da codebase (requer repomix)
repomix --output xml src/
```

### Debugging

#### Debug Local com VS Code

Crie `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: BotSalinha",
      "type": "debugpy",
      "request": "launch",
      "module": "bot",
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Pytest: Current File",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

#### Debug de Logs

```bash
# Habilitar logs debug no .env
LOG_LEVEL=DEBUG

# Executar com logs debug
uv run bot.py
```

---

## 4. Desenvolvimento RAG

O BotSalinha possui um sistema de Retrieval-Augmented Generation (RAG) para consultas contextuais sobre a base de código e documentação.

### Arquitetura RAG

```text
┌─────────────────────────────────────────────────┐
│           Camada de Ingestão                    │
│  (Repomix XML, DOCX, Código)                    │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Parsing                     │
│  (Code Chunker, XML Parser, DOCX Parser)        │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Metadados                   │
│  (Code Metadata Extractor)                      │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Embeddings                  │
│  (OpenAI Embedding Service)                     │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Storage                     │
│  (SQLite RAG Repository)                        │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Query                       │
│  (Vector Similarity Search)                     │
└─────────────────────────────────────────────────┘
```

### Componentes RAG

#### Parsers (`src/rag/parser/`)

- **`chunker.py`**: `ChunkExtractor` - Extrai chunks de texto com sobreposição
- **`code_chunker.py`**: `CodeChunker` - Chunker especializado para código-fonte com análise de estrutura
- **`xml_parser.py`**: `RepomixXMLParser` - Parser para XML gerado pelo Repomix
- **`docx_parser.py`**: `DOCXParser` - Parser para documentos Word

#### Serviços (`src/rag/services/`)

- **`ingestion_service.py`**: `IngestionService` - Serviço genérico de ingestão de documentos
- **`code_ingestion_service.py`**: `CodeIngestionService` - Serviço especializado para ingestão de codebase
- **`embedding_service.py`**: `EmbeddingService` - Geração de embeddings via OpenAI API
- **`query_service.py`**: `QueryService` - Consulta RAG com busca semântica

#### Storage (`src/rag/storage/`)

- **`rag_repository.py`**: `RAGRepository` - Repositório RAG com SQLAlchemy
- **`vector_store.py`**: `VectorStore` - Interface abstrata para vector stores

#### Utils (`src/rag/utils/`)

- **`code_metadata_extractor.py`**: `CodeMetadataExtractor` - Extrai metadados de código (funções, classes, imports, linguagem, layer)

### Fluxo de Trabalho RAG

#### 1. Preparar o Código (Repomix)

```bash
# Instalar repomix globalmente
npm install -g repomix

# Gerar XML da codebase
repomix --output xml src/

# Ou com filtros específicos
repomix --output xml --include "src/**/*.py" --exclude "tests/**" src/
```

#### 2. Ingerir no RAG

```bash
# Ingestão completa (substitui documento existente)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "botsalinha-codebase" --replace

# Ingestão seca (apenas parse, sem salvar)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run

# Ingestão com nome customizado
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "meu-projeto"
```

**Variáveis de Ambiente Necessárias:**

```bash
# .env
BOTSALINHA_OPENAI__API_KEY=sk-...  # Necessária para embeddings (formato canônico)
# OPENAI_API_KEY=sk-...             # Formato legado (funciona via fallback)
BOTSALINHA_DATABASE__URL=sqlite:///data/botsalinha.db
```

#### 3. Consultar o RAG

```python
from src.rag.services.query_service import QueryService
from src.rag.storage.rag_repository import RAGRepository
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def query_rag(question: str):
    engine = create_async_engine("sqlite+aiosqlite:///data/botsalinha.db")
    async with AsyncSession(engine) as session:
        repository = RAGRepository(session)
        query_service = QueryService(repository)

        results = await query_service.query(
            question=question,
            document_name="botsalinha-codebase",
            top_k=5
        )

        for result in results:
            print(f"Score: {result.score:.4f}")
            print(f"Content: {result.content[:200]}...")
            print(f"Metadata: {result.metadata}")
            print("---")
```

### Comandos CLI RAG

```bash
# Ingerir codebase
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --replace

# Listar documentos RAG (via Python REPL)
uv run python
>>> from src.rag.storage.rag_repository import RAGRepository
>>> import asyncio
>>> async def list_docs():
...     # ... código para listar documentos
```

### Estrutura de Dados RAG

#### DocumentORM

```python
class DocumentORM(Base):
    id: int
    nome: str                    # Nome do documento
    tipo: str                    # "codebase", "docx", etc.
    chunk_count: int             # Número de chunks
    total_tokens: int            # Total de tokens
    created_at: datetime
    content_hash: str            # Hash SHA-256 para deduplicação
    chunks: List["ChunkORM"]     # Relacionamento
```

#### ChunkORM

```python
class ChunkORM(Base):
    id: int
    document_id: int             # FK para DocumentORM
    content: str                 # Conteúdo do chunk
    embedding: bytes             # Embedding vetorial (compactado)
    metadata: JSON               # Metadados do chunk
    index: int                   # Índice do chunk no documento
    created_at: datetime
```

### Metadados de Código

O `CodeMetadataExtractor` extrai informações estruturais de código:

```python
{
    "file_path": "src/core/agent.py",
    "language": "python",
    "functions": ["generate_response", "load_history"],
    "classes": ["AgentWrapper"],
    "imports": ["asyncio", "structlog", "agno"],
    "layer": "core",
    "module": "agent",
    "is_test": false
}
```

### Configuração de Chunking

#### Code Chunker

- **Tamanho padrão**: 1000 tokens por chunk
- **Sobreposição**: 200 tokens
- **Respeita estrutura**: Mantém funções/classes intactas quando possível
- **Metadados ricos**: Extrai funções, classes, imports, layer

#### Chunker Genérico

- **Tamanho configurável**: Definido no construtor
- **Sobreposição configurável**: Para preservar contexto
- **Divisão inteligente**: Evita cortar palavras/frases

### Testes RAG

```bash
# Testes unitários RAG
uv run pytest tests/unit/rag/

# Testes de integração RAG
uv run pytest tests/integration/rag/

# Teste específico
uv run pytest tests/unit/rag/test_code_chunker.py -v

# Testes com coverage
uv run pytest tests/unit/rag/ --cov=src/rag --cov-report=html
```

### Boas Práticas RAG

1. **Deduplicação**: Use `content_hash` para evitar reingerir o mesmo conteúdo
2. **Chunking**: Ajuste tamanho/overhead baseado no seu caso de uso
3. **Metadados**: Inclua contexto máximo (layer, linguagem, funções)
4. **Versionamento**: Use nomes de documentos versionados (ex: "codebase-v1.0")
5. **Atomicidade**: Use `--replace` para updates atômicos

### Troubleshooting RAG

#### Erro: "OPENAI_API_KEY not configured"

```bash
# Adicionar ao .env
OPENAI_API_KEY=sk-...
```

#### Erro: "Failed to parse XML input"

```bash
# Verificar se o XML é válido
xmllint --noout repomix-output.xml

# Regenerar com repomix
repomix --output xml src/
```

#### Embeddings muito lentos

```bash
# Verificar uso da API
# O script mostra tokens e custo estimado
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run

# Ajustar chunk size para reduzir chamadas à API
# Editar src/rag/parser/code_chunker.py
```

---

## 5. ChromaDB Vector Store

BotSalinha suporta ChromaDB como backend de busca vetorial alternativa ao SQLite.

### Arquitetura

O sistema usa um `HybridVectorStore` que combina:
- **ChromaDB:** Busca vetorial primária (quando habilitado)
- **SQLite:** Fallback automático + armazenamento de metadata

### Configuração

Para ativar ChromaDB, defina no `.env`:

```bash
BOTSALINHA_RAG__CHROMA__ENABLED=true
BOTSALINHA_RAG__CHROMA__PATH=data/chroma
```

### Características

- **Hybrid Search:** Combina busca vetorial com BM25 lexical reranking
- **Dual-Write:** Escreve em ambos os backends durante migração
- **Fallback Automático:** Timeout de 200ms com fallback para SQLite
- **Zero Downtime:** Bot continua funcionando durante migração

### Migração

Para migrar embeddings do SQLite para ChromaDB:

```bash
# Validação (dry-run)
uv run python scripts/migrate_to_chroma.py --dry-run

# Migração completa
uv run python scripts/migrate_to_chroma.py --batch-size 100

# Validação pós-migração
uv run python scripts/migrate_to_chroma.py --validate
```

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `BOTSALINHA_RAG__CHROMA__ENABLED` | `false` | Ativar ChromaDB |
| `BOTSALINHA_RAG__CHROMA__PATH` | `data/chroma` | Caminho de persistência |
| `BOTSALINHA_RAG__CHROMA__HYBRID_SEARCH_ENABLED` | `true` | Hybrid search (BM25) |
| `BOTSALINHA_RAG__CHROMA__FALLBACK_TO_SQLITE` | `true` | Fallback em erro |
| `BOTSALINHA_RAG__CHROMA__DUAL_WRITE_ENABLED` | `false` | Dual-write migração |
| `BOTSALINHA_RAG__CHROMA__FALLBACK_TIMEOUT_MS` | `200` | Timeout fallback (ms) |

### Troubleshooting

**ChromaDB não inicia:**
- Verifique permissões de escrita em `data/chroma`
- Certifique-se que o caminho existe

**Fallback frequente:**
- Ajuste `FALLBACK_TIMEOUT_MS`
- Verifique logs para identificar erros

**Performance:**
- Use batch size de 100 para migração
- Monitore telemetria de fallback

---

## 6. Abordagem de Teste

### Pirâmide de Testes

```text
        ┌─────┐
       / E2E  \         ← Poucos, lentos (Playwright)
      /───────\
     / Integração \     ← Alguns, moderados
    /─────────────\
   /  Unitários    \    ← Muitos, rápidos (pytest)
  /─────────────────\
```

### Testes Unitários

**Localização:** `tests/`

**Exemplo:**

```python
import pytest
from src.middleware.rate_limiter import RateLimiter
from src.utils.errors import RateLimitError

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        limiter = RateLimiter(requests=10, window_seconds=60)

        # Não deve lançar exceção
        await limiter.check_rate_limit(user_id="123", guild_id="456")

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self):
        limiter = RateLimiter(requests=1, window_seconds=60)

        await limiter.check_rate_limit(user_id="123", guild_id="456")

        # Deve lançar exceção
        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(user_id="123", guild_id="456")
```

### Fixtures do Pytest

**Localização:** `tests/conftest.py`

```python
import pytest
import pytest_asyncio
from src.storage.sqlite_repository import SQLiteRepository

@pytest_asyncio.fixture
async def conversation_repository():
    """Repositório para testes."""
    repo = SQLiteRepository("sqlite+aiosqlite:///:memory:")
    await repo.initialize_database()
    await repo.create_tables()

    yield repo

    await repo.close()

@pytest.fixture
def mock_discord_context():
    """Contexto Discord simulado."""
    ctx = MagicMock()
    ctx.author.id = 123456789
    ctx.send = AsyncMock()
    return ctx
```

### Executar Testes

```bash
# Todos os testes
uv run pytest

# Testes específicos
uv run pytest tests/test_rate_limiter.py

# Teste específico
uv run pytest tests/test_rate_limiter.py::TestRateLimiter::test_check_rate_limit_allowed

# Com coverage
uv run pytest --cov=src --cov-report=html --cov-report=term

# Parar no primeiro erro
uv run pytest -x

# Mostrar print statements
uv run pytest -s
```

### Boas Práticas de Teste

1. **Testes Independentes**: Cada teste deve funcionar isoladamente
2. **AAA Pattern**: Arrange, Act, Assert
3. **Nomes Descritivos**: `test_<oque>_<quando>_<entao>`
4. **Mock External Services**: Use mocks para APIs externas
5. **Test Edge Cases**: Limite, vazio, nulo, etc.

---

## 7. Solução de Problemas

### Problemas Comuns de Desenvolvimento

#### 1. Erro: "No module named 'src'"

**Causa:** Python não encontra o módulo src.

**Solução:**

```bash
# Garantir que está executando com uv
uv run python bot.py

# Ou ativar o venv
source .venv/bin/activate
python bot.py
```

#### 2. Erro: "DATABASE_URL not set"

**Causa:** Variáveis de ambiente não configuradas.

**Solução:**

```bash
# Criar arquivo .env
cp .env.example .env

# Editar .env com valores corretos
```

#### 3. Erro: "discord.errors.LoginFailure"

**Causa:** Token do Discord inválido.

**Solução:**

1. Verifique o token em `.env`
2. Gere novo token no Discord Developer Portal
3. Certifique-se de copiar o token completo (59 caracteres)

#### 4. Erro: "sqlite3.OperationalError: database is locked"

**Causa:** Múltiplas instâncias acessando o SQLite.

**Solução:**

```bash
# Parar todas as instâncias
docker-compose down
pkill -f bot.py

# Verificar processos
ps aux | grep bot.py

# Deletar arquivo de lock se existir
rm data/botsalinha.db-wal
rm data/botsalinha.db-shm
```

#### 5. Erro: "mypy: error: invalid syntax"

**Causa:** Versão do Python incompatível.

**Solução:**

```bash
# Verificar versão do Python
python --version  # Deve ser 3.12+

# Reinstalar dependências
uv sync
```

### Problemas de Performance

#### Bot Lento para Responder

**Diagnosticar:**

```bash
# Verificar logs
tail -f logs/botsalinha.log | grep "duration"

# Verificar latência da API
curl -w "@curl-format.txt" -o /dev/null -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=YOUR_KEY"
```

**Soluções:**

- **Diminuir `HISTORY_RUNS`**: Recomendado quando há necessidade de reduzir latência ou uso de memória/tokens (ex.: ambientes com limite de tokens ou alta taxa de requisições). Valores típicos: 1-2.
- **Aumentar `HISTORY_RUNS`**: Indicado quando priorizamos qualidade contextual e continuidade de conversação (ex.: tarefas que dependem de histórico extenso). Valores típicos: 3-5.
- Verificar latência de rede
- Usar cache para respostas comuns

> **Trade-off**: Maior `HISTORY_RUNS` = melhor contexto, mas maior custo e latência.

#### Alto Uso de Memória

**Diagnosticar:**

```bash
# Verificar uso de memória
docker stats botsalinha

# Ou localmente
python -m memory_profiler bot.py
```

**Soluções:**

- Limpar conversas antigas: `!limpar` ou cleanup automático
- Reduzir tamanho do histórico
- Verificar memory leaks

### Problemas de Testes

#### Testes Falham com "asyncio"

**Erro:** `RuntimeError: This event loop is already running`

**Solução:**

```python
# Usar pytest-asyncio corretamente
@pytest.mark.asyncio
async def test_minha_funcao():
    resultado = await funcao_async()
    assert resultado is not None
```

#### Testes Lentos

**Soluções:**

```bash
# Usar banco em memória
TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:"

# Usar fixtures de escopo correto
@pytest.fixture(scope="session")  # Ao invés de function
def expensive_resource():
    ...
```

### Recursos de Debug

#### Logs Estruturados

```python
import structlog

log = structlog.get_logger()

# Adicionar contexto
log = log.bind(user_id="123", guild_id="456")

# Log com contexto
log.info("processando_requisicao", action="ask", length=100)

# Log de erro
log.error("falha_na_api", error_type="ConnectionError", retry=1)
```

#### Verificar Estado do Banco

```python
# Python shell interativo
uv run python

>>> from src.storage.sqlite_repository import get_repository
>>> import asyncio
>>>
>>> async def check_db():
...     repo = get_repository()
...     convs = await repo.get_by_user_and_guild("123", "456")
...     print(f"Conversas: {len(convs)}")
...     for conv in convs:
...         print(f"  - {conv.id}: {conv.created_at}")
...
>>> asyncio.run(check_db())
```

### Obter Ajuda

**Recursos Internos:**

- [PRD.md](PRD.md) - Requisitos do produto
- [docs/deployment.md](docs/deployment.md) - Guia de implantação
- [docs/operations.md](docs/operations.md) - Manual de operações

**Recursos Externos:**

- [Agno Documentation](https://github.com/agno-ai/agno)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

---

## Checklist de Desenvolvimento

### Antes de Commitar

- [ ] Testes passando: `uv run pytest`
- [ ] Lint clean: `uv run ruff check src/`
- [ ] Tipos ok: `uv run mypy src/`
- [ ] Código formatado: `uv run ruff format src/`
- [ ] Documentação atualizada
- [ ] Changelog atualizado (se aplicável)

### Antes de Criar PR

- [ ] Branch atualizada com `develop`
- [ ] Commits com mensagens claras
- [ ] CI/CD passando
- [ ] Revisor atribuído
- [ ] Descrição da PR completa

### Antes de Deploy

- [ ] Testes de integração passando
- [ ] Migrações testadas
- [ ] Backup do banco criado
- [ ] Documentação de deploy atualizada
- [ ] Rollback planejado

---

### Happy Coding! 🚀

Para mais informações, consulte os outros documentos do projeto ou abra uma issue no GitHub.
