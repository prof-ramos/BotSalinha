# PRD - BotSalinha v2.x

## 1. Visão Geral

BotSalinha é um assistente virtual para Discord especializado em direito e concursos públicos, utilizando o framework Agno com suporte multi-modelo (OpenAI padrão, Google Gemini opcional). A v2.x oferece persistência via SQLite, RAG (Retrieval-Augmented Generation) para documentos e codebase, rate limiting, logging estruturado e deployment via Docker.

### 1.1 Objetivo Principal
Fornecer respostas contextualizadas a perguntas sobre direito e concursos através do comando `!ask`, mantendo histórico de conversação persistente, entregando respostas formatadas em português brasileiro, e utilizando RAG para enriquecer respostas com documentos legais e código-fonte do projeto.

### 1.2 Escopo v2.x
- **Multi-modelo**: OpenAI (default) + Google Gemini
- **Persistência SQLite**: Conversações e mensagens armazenadas
- **RAG implementado**: Documentos jurídicos + codebase
- **Rate limiting**: Token bucket por usuário/servidor
- **Docker support**: Multi-stage build + docker-compose
- **CLI tooling**: Chat mode para desenvolvimento
- **Logging estruturado**: JSON/text com structlog
- **Migrations**: Alembic para schema versioning
- **Testes automatizados**: pytest com 70%+ cobertura

## 2. Funcionalidades

### 2.1 Comando !ask
| Descrição | Detalhes |
|-----------|----------|
| **Trigger** | `!ask <pergunta>` |
| **Resposta** | OpenAI (default) ou Gemini via Agno |
| **Histórico** | 3 runs anteriores (SQLite persistente) |
| **Formatação** | Markdown + data/hora |
| **Idioma** | Português-BR |
| **Domínio** | Direito e concursos públicos |
| **RAG** | Documentos + codebase indexados |

### 2.2 Comandos Adicionais
| Comando | Descrição |
|---------|-----------|
| `!ping` | Health check do bot |
| `!ajuda` | Exibe mensagem de ajuda |
| `!info` | Informações sobre o bot |
| `!limpar` | Limpa histórico do usuário |

### 2.3 Configuração Discord
- Token via variável de ambiente (`BOTSALINHA_DISCORD__TOKEN`)
- MESSAGE_CONTENT Intent habilitado
- Permissões: Send Messages, Read Message History
- Rate limiting configurável por usuário/servidor

### 2.4 RAG (Retrieval-Augmented Generation)
- **Documentos**: Ingestão de PDFs, TXT, MD
- **Codebase**: Indexação automática do código-fonte
- **Vector Store**: ChromaDB para embeddings
- **Chunking**: Estratégia de segmentação configurável
- **Metadata**: Extração de metadados de código (funções, classes)

### 2.5 Logging Estruturado
- Logs em JSON ou texto via structlog
- Níveis configuráveis (DEBUG, INFO, WARNING, ERROR)
- Correlation IDs para tracing
- Context binding para operações async

## 3. Instalação e Execução

### 3.1 Pré-requisitos
- Python 3.12+
- uv (package manager)
- Conta Discord com Developer Portal acessível
- OpenAI API Key (default) OU Google API Key (Gemini)
- Docker (opcional, para deployment)

### 3.2 Instalação Local

#### 1. Clonar e configurar
```bash
git clone <repository-url>
cd BotSalinha
cp .env.example .env
```

#### 2. Configurar variáveis de ambiente
Edite `.env` com suas credenciais:
```env
# Discord (obrigatório)
BOTSALINHA_DISCORD__TOKEN=your_discord_bot_token_here
BOTSALINHA_DISCORD__MESSAGE_CONTENT_INTENT=true

# AI Provider (escolha um ou ambos)
BOTSALINHA_OPENAI__API_KEY=your_openai_api_key_here
BOTSALINHA_GOOGLE__API_KEY=your_google_api_key_here

# Configurações opcionais
BOTSALINHA_HISTORY__RUNS=3
BOTSALINHA_RATE_LIMIT__REQUESTS=10
BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS=60
BOTSALINHA_DATABASE__URL=sqlite:///data/botsalinha.db
BOTSALINHA_LOG_LEVEL=INFO
BOTSALINHA_LOG_FORMAT=json
```

#### 3. Instalar dependências
```bash
uv sync
```

#### 4. Executar migrations do banco de dados
```bash
uv run alembic upgrade head
```

#### 5. Executar o bot
```bash
# Modo Discord
uv run botsalinha

# Modo CLI (para desenvolvimento)
uv run bot.py --chat
```

### 3.3 Docker Deployment

#### Development
```bash
docker-compose up -d
docker-compose logs -f
```

#### Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

Veja [docs/deployment.md](docs/deployment.md) para detalhes completos.

## 4. Configuração Discord

### 4.1 Criar Aplicação Discord
1. Acesse [Discord Developer Portal](https://discord.com/developers/applications)
2. Clique em "New Application"
3. Dê um nome ao bot (ex: "BotSalinha")
4. Clique em "Create"

### 4.2 Configurar Bot
1. Navegue para **Bot** > **Token**
2. Clique em "Reset Token" para gerar novo token
3. **Copie o token imediatamente** (não será exibido novamente)
4. Adicione ao `.env` como `DISCORD_BOT_TOKEN`

### 4.3 Configurar Intents
Em **Bot** > **Privileged Gateway Intents**:
- ✅ **MESSAGE_CONTENT** (obrigatório para ler mensagens)

### 4.4 Gerar URL de Convite
1. Navegue para **OAuth2** > **URL Generator**
2. Selecione scope:
   - ✅ **bot**
3. Selecione permissões:
   - ✅ Send Messages
   - ✅ Read Message History
4. Copie a URL gerada e acesse no navegador
5. Selecione o servidor e autorize

## 5. Requisitos Não-Funcionais

### 5.1 Plataforma e Ambiente
| Aspecto | Especificação |
|---------|---------------|
| Runtime | Python 3.12+ |
| Package Manager | uv |
| Execução | Local (`uv run`) ou Docker |
| Database | SQLite (async via aiosqlite) |
| Migrations | Alembic |

### 5.2 Persistência
- **SQLite**: Conversações e mensagens persistidas
- **Alembic**: Versionamento de schema
- **Backup**: Script em `scripts/backup.py`
- **Repository Pattern**: Interfaces abstratas + implementação SQLite

### 5.3 Segurança
- `.env` adicionado ao `.gitignore`
- Tokens nunca commitados ao repositório
- `BOTSALINHA_` prefix para todas as variáveis de ambiente
- Rate limiting por usuário/servidor
- Sanitização de inputs
- Pre-commit hooks para linting/type-checking

### 5.4 Performance e Disponibilidade
- **Latência**: Dependente do modelo (OpenAI ~1-2s, Gemini ~1-3s)
- **Disponibilidade**: Docker para deployment contínuo
- **Escalabilidade**: Stateless + SQLite (futuro PostgreSQL)
- **Rate Limiting**: Token bucket para prevenir abuse

### 5.5 Idioma e Localização
- Idioma primário: Português-BR
- Formatação de datas: PT-BR
- Domínio de conhecimento: Direito brasileiro e concursos públicos

### 5.6 Observabilidade
- **Logging**: structlog com JSON/text output
- **Níveis**: DEBUG, INFO, WARNING, ERROR
- **Context**: Correlation IDs para tracing
- **Métricas**: Futuro (Prometheus/Grafana)

## 6. Arquitetura Técnica

### 6.1 Componentes
```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Discord   │────▶│ BotSalinha  │────▶│ Agno Agent   │
│   Client    │     │     Bot      │     │  (Wrapper)   │
└─────────────┘     └─────────────┘     └──────────────┘
                            ▲                     │
                            │                     ▼
                     ┌──────┴──────┐     ┌─────────────┐
                     │ RateLimiter │     │  OpenAI /   │
                     │ Middleware  │     │  Gemini     │
                     └─────────────┘     └─────────────┘
                            ▲                     │
                            │                     ▼
                     ┌──────┴──────┐     ┌─────────────┐
                     │   SQLite    │     │  RAG Query  │
                     │ Repository  │     │  Service    │
                     └─────────────┘     └─────────────┘
                                                  │
                                                  ▼
                                          ┌─────────────┐
                                          │  Vector     │
                                          │  Store      │
                                          │  (Chroma)   │
                                          └─────────────┘
```

### 6.2 Fluxo de Dados
1. Usuário envia `!ask <pergunta>` no Discord
2. BotSalinhaBot recebe mensagem e verifica rate limit
3. AgentWrapper recupera histórico do SQLite
4. RAG Query Service busca contexto relevante
5. Agno Agent combina contexto + RAG + query
6. Request enviada ao modelo (OpenAI ou Gemini)
7. Resposta processada com formatação markdown
8. Conversa salva no SQLite
9. Resposta enviada ao Discord

### 6.3 Camadas da Arquitetura

#### Presentation Layer
- `src/core/discord.py`: BotSalinhaBot (commands, events)
- Rate limiting middleware

#### Service Layer
- `src/core/agent.py`: AgentWrapper (Agno + modelo)
- `src/rag/services/`: Query, Ingestion, Code Ingestion

#### Data Access Layer
- `src/storage/repository.py`: Interfaces abstratas
- `src/storage/sqlite_repository.py`: Implementação SQLite
- `src/rag/storage/rag_repository.py`: RAG persistence

#### Models
- `src/models/conversation.py`: Conversação ORM + schemas
- `src/models/message.py`: Mensagem ORM + schemas
- `src/models/rag_models.py`: RAG document models

Veja [docs/architecture.md](docs/architecture.md) para detalhes completos.

## 7. Estrutura de Arquivos

```
BotSalinha/
├── bot.py                        # Entry-point wrapper
├── pyproject.toml                # Dependências e metadados
├── config.yaml                   # Configuração de agentes/modelos
├── docker-compose.yml            # Orquestração Docker (dev)
├── docker-compose.prod.yml       # Orquestração Docker (prod)
├── Dockerfile                    # Multi-stage build
├── pytest.ini                    # Configuração pytest
├── mypy.ini                      # Type checking strict
├── ruff.toml                     # Linter/formatter config
├── .env.example                  # Template de variáveis de ambiente
├── .pre-commit-config.yaml       # Pre-commit hooks
│
├── src/                          # Código fonte principal
│   ├── main.py                   # CLI entry point
│   ├── config/
│   │   ├── settings.py           # Pydantic Settings (env vars)
│   │   └── yaml_config.py        # YAML config loader
│   ├── core/
│   │   ├── agent.py              # Agno AgentWrapper
│   │   ├── discord.py            # BotSalinhaBot
│   │   └── lifecycle.py          # Startup/shutdown
│   ├── models/
│   │   ├── conversation.py       # ConversationORM + schemas
│   │   ├── message.py            # MessageORM + schemas
│   │   └── rag_models.py         # RAG document models
│   ├── storage/
│   │   ├── repository.py         # Interfaces abstratas
│   │   ├── sqlite_repository.py  # SQLite implementation
│   │   └── rag/                  # RAG storage
│   ├── rag/
│   │   ├── services/             # Query, Ingestion services
│   │   ├── parser/               # Code chunker, XML parser
│   │   ├── utils/                # Metadata extractor
│   │   └── storage/              # RAG repository, vector store
│   ├── middleware/
│   │   └── rate_limiter.py       # Token bucket rate limiter
│   └── utils/
│       ├── logger.py             # structlog setup
│       ├── errors.py             # Custom exceptions
│       └── retry.py              # async_retry decorator
│
├── tests/
│   ├── conftest.py               # Fixtures compartilhadas
│   ├── unit/                     # Testes unitários
│   ├── integration/              # Testes de integração
│   └── e2e/                      # Testes end-to-end
│
├── migrations/                   # Alembic migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/                 # Migration scripts
│
├── scripts/
│   ├── backup.py                 # SQLite backup/restore
│   ├── run_tests.sh              # Test runner helper
│   └── ingest_codebase_rag.py    # RAG code ingestion
│
├── prompt/                       # System prompts
│   ├── prompt_v1.md              # Prompt simples (default)
│   ├── prompt_v2.json            # Few-shot examples
│   └── prompt_v3.md              # Chain-of-thought
│
├── docs/
│   ├── DEVELOPER_GUIDE.md        # Guia do desenvolvedor
│   ├── deployment.md             # Instruções de deployment
│   ├── operations.md             # Manual de operações
│   ├── architecture.md           # Arquitetura detalhada
│   └── CODE_DOCUMENTATION.md     # Documentação de código
│
├── .github/workflows/
│   └── test.yml                  # CI/CD pipeline
│
├── PRD.md                        # Product Requirements (este arquivo)
├── AGENTS.md                     # Convenções de agentes
└── README.md                     # Documentação principal
```

## 8. Roadmap

### v2.0 (Atual) - Multi-Model + RAG + Persistência
- ✅ Multi-modelo (OpenAI default, Gemini opcional)
- ✅ Persistência SQLite com Alembic migrations
- ✅ RAG implementado (documentos + codebase)
- ✅ Rate limiting por usuário/servidor
- ✅ Docker deployment (dev + prod)
- ✅ CLI tooling (chat mode)
- ✅ Logging estruturado (structlog)
- ✅ Testes automatizados (pytest, 70%+ cobertura)
- ✅ Pre-commit hooks (ruff, mypy)
- ✅ Repository pattern
- ✅ Commands: `!ask`, `!ping`, `!ajuda`, `!info`, `!limpar`

### v2.1 - Melhorias de RAG
- [ ] Interface web para ingestão de documentos
- [ ] Suporte a mais formatos (DOCX, PPTX)
- [ ] Re-ranking de resultados
- [ ] Citações de fontes nas respostas
- [ ] Multi-tenancy para RAG (por servidor)

### v2.2 - Observabilidade & Monitoramento
- [ ] Métricas Prometheus/Grafana
- [ ] Tracing distribuído (OpenTelemetry)
- [ ] Dashboards de utilização
- [ ] Alertas de erros e anomalias
- [ ] Health checks completos

### v3.0 - Escalabilidade & Multi-Provedores
- [ ] PostgreSQL para escalabilidade horizontal
- [ ] Claude/Anthropic support
- [ ] Redis para cache de respostas
- [ ] Queue system para async processing
- [ ] Kubernetes deployment
- [ ] Blue-green deployments

## 9. Considerações Futuras

### 9.1 Decisões Arquiteturais Tomadas (v2.x)
- ✅ **Persistência**: SQLite escolhido para simplicidade (futuro PostgreSQL)
- ✅ **Rate Limiting**: Token bucket implementado por usuário/servidor
- ✅ **Multi-modelo**: OpenAI como default, Gemini como alternativa
- ✅ **RAG**: ChromaDB para vector store, chunking configurável
- ✅ **Repository Pattern**: Interfaces abstratas para testabilidade
- ✅ **Migration Strategy**: Alembic para versionamento de schema
- ✅ **Deployment**: Docker multi-stage build para ambientes dev/prod

### 9.2 Melhorias Possíveis
- Sistema de citações de fontes jurídicas nas respostas
- Index de legislação e jurisprudência brasileira
- Multi-servidor com contexto isolado (RAG por servidor)
- Webhooks para notificações assíncronas
- Interface administrativa web
- Suporte a arquivos de áudio (transcrição + consulta)
- Modo de conversação por voz (TTS/STT)
- Integração com APIs de dados jurídicos (STF, STJ)

### 9.3 Decisões Arquiteturais Pendentes
- Estratégia de cache de respostas (Redis vs memcached)
- Rate limiting distribuído (Redis backend)
- Estratégia de backup automático (scheduling)
- Multi-region deployment para alta disponibilidade
- Estratégia de rollbacks para deployments

## 10. Apêndice

### 10.1 Comandos Úteis
```bash
# Instalar dependências
uv sync

# Executar bot (Discord)
uv run botsalinha

# Executar bot (CLI chat mode)
uv run bot.py --chat

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
uv run ruff format src/

# Testes
uv run pytest                    # Todos os testes
uv run pytest tests/unit         # Apenas unitários
uv run pytest --cov=src --cov-report=html  # Com coverage

# Migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1

# Backup
uv run python scripts/backup.py backup
uv run python scripts/backup.py list
uv run python scripts/backup.py restore --restore-from <file>

# RAG Ingestion
uv run python scripts/ingest_codebase_rag.py
```

### 10.2 Troubleshooting

#### Bot não responde
1. Verifique `BOTSALINHA_DISCORD__TOKEN` no `.env`
2. Confirme que MESSAGE_CONTENT Intent está habilitado
3. Verifique permissões do bot no servidor
4. Confirme que o bot está online (Discord Developer Portal)
5. Verifique logs: `docker-compose logs -f` ou `tail -f data/botsalinha.log`

#### Erro de API (OpenAI/Gemini)
1. Verifique `BOTSALINHA_OPENAI__API_KEY` ou `BOTSALINHA_GOOGLE__API_KEY`
2. Confirme que a API key tem quota disponível
3. Verifique conectividade com a internet
4. Confirme provider selecionado em `config.yaml`

#### Problemas no banco de dados
1. Execute migrations: `uv run alembic upgrade head`
2. Verifique caminho do banco em `BOTSALINHA_DATABASE__URL`
3. Para SQLite, confirme permissões de escrita no diretório
4. Restaure backup se necessário: `uv run python scripts/backup.py restore`

#### Rate limiting bloqueando usuários
1. Ajuste `BOTSALINHA_RATE_LIMIT__REQUESTS` no `.env`
2. Ajuste `BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS`
3. Use `!limpar` para resetar histórico manualmente

#### RAG não retorna resultados
1. Verifique se documentos foram ingeridos: `scripts/ingest_codebase_rag.py`
2. Confirme ChromaDB está acessível
3. Verifique configuração de chunking em `config.yaml`
4. Ajuste `similarity_threshold` se necessário

### 10.3 Links Úteis

#### Documentação do Projeto
- [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) - Guia completo do desenvolvedor
- [architecture.md](docs/architecture.md) - Arquitetura detalhada
- [CODE_DOCUMENTATION.md](docs/CODE_DOCUMENTATION.md) - Documentação de código
- [deployment.md](docs/deployment.md) - Instruções de deployment
- [operations.md](docs/operations.md) - Manual de operações

#### Links Externos
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Agno Framework](https://github.com/agno-agi/agno)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [uv Documentation](https://github.com/astral-sh/uv)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [ChromaDB Documentation](https://docs.trychroma.com/)

### 10.4 Glossário

| Termo | Descrição |
|-------|-----------|
| **Agno** | Framework Python para construção de agentes AI |
| **OpenAI/Gemini** | Modelos LLM suportados (multi-modelo) |
| **RAG** | Retrieval-Augmented Generation (busca + geração) |
| **ChromaDB** | Vector store para embeddings e busca semântica |
| **SQLite** | Banco de dados embedded para persistência |
| **Alembic** | Tool de migrations para SQLAlchemy |
| **Intent** | Permissão para receber eventos do Discord |
| **Message Content** | Permissão para ler conteúdo de mensagens |
| **uv** | Package manager Python moderno e rápido |
| **structlog** | Logging estruturado para Python |
| **Token Bucket** | Algoritmo de rate limiting |
| **Repository Pattern** | Padrão de abstração de acesso a dados |
| **Pydantic** | Validação de dados e settings |
| **AsyncIO** | Programação assíncrona em Python |

### 10.5 Variáveis de Ambiente

Veja `.env.example` para a lista completa. Todas usam prefixo `BOTSALINHA_`:

| Variável | Descrição | Default |
|----------|-----------|---------|
| `BOTSALINHA_DISCORD__TOKEN` | Token do bot Discord | *obrigatório* |
| `BOTSALINHA_OPENAI__API_KEY` | API Key OpenAI | *obrigatório* |
| `BOTSALINHA_GOOGLE__API_KEY` | API Key Google | opcional |
| `BOTSALINHA_DATABASE__URL` | URL do banco SQLite | `sqlite:///data/botsalinha.db` |
| `BOTSALINHA_HISTORY__RUNS` | Pares de mensagens no histórico | `3` |
| `BOTSALINHA_RATE_LIMIT__REQUESTS` | Max requests por janela | `10` |
| `BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS` | Janela de rate limit | `60` |
| `BOTSALINHA_LOG_LEVEL` | Nível de log | `INFO` |
| `BOTSALINHA_LOG_FORMAT` | Formato de log (json/text) | `json` |

---

**Documento Versão**: 2.0
**Última Atualização**: 2026-03-01
**Status**: Implementado (v2.x)
