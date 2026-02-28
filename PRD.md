# PRD — BotSalinha v2.1

**Última Atualização:** 2026-02-28
**Status:** Produção

---

## 1. Visão Geral

BotSalinha é um assistente Discord especializado em **direito brasileiro** e **concursos públicos**, alimentado por OpenAI GPT-4o-mini via framework Agno. Oferece conversas contextuais com histórico persistente, RAG jurídico com citação de fontes, rate limiting por usuário e logs estruturados.

### 1.1 Objetivo Principal

Fornecer respostas jurídicas fundamentadas, precisas e com citação de fontes a perguntas sobre direito e concursos públicos, via Discord, em português brasileiro.

### 1.2 Escopo v2.1

- Multi-provider: OpenAI (padrão) e Google AI
- RAG jurídico com busca semântica (CF/88, Lei 8.112/90)
- Histórico persistente em SQLite
- Rate limiting por usuário/guild (Token Bucket)
- Três modos de interação: comandos prefixados, Canal IA, DM
- Deploy via Docker (dev e prod)

---

## 2. Funcionalidades

### 2.1 Comandos Discord

| Comando               | Descrição                                            | Exemplo                              |
| --------------------- | ---------------------------------------------------- | ------------------------------------ |
| `!ask <pergunta>`     | Pergunta com RAG e histórico                         | `!ask O que é habeas corpus?`        |
| `!buscar <query>`     | Busca semântica nos documentos indexados             | `!buscar estágio probatório`         |
| `!buscar <q> <tipo>`  | Busca filtrada por tipo jurídico                     | `!buscar greve artigo`               |
| `!fontes`             | Lista documentos indexados                           | `!fontes`                            |
| `!reindexar`          | Reconstrói o índice RAG (admin)                      | `!reindexar`                         |
| `!limpar`             | Apaga histórico de conversa do usuário               | `!limpar`                            |
| `!ping`               | Health check                                         | `!ping`                              |
| `!ajuda`              | Ajuda do bot                                         | `!ajuda`                             |
| `!info`               | Informações do bot                                   | `!info`                              |

### 2.2 Modos de Interação

| Modo               | Trigger                           | Configuração                     |
| ------------------ | --------------------------------- | -------------------------------- |
| Comandos prefixados | `!ask`, `!buscar`, etc.          | Nenhuma                          |
| Canal IA           | Qualquer mensagem no canal        | `DISCORD__CANAL_IA_ID` no `.env` |
| DM automático      | Mensagem direta para o bot        | Nenhuma (sempre ativo)           |

### 2.3 RAG Jurídico

- **Documentos indexados**: CF/88 (687 chunks, ~303K tokens), Lei 8.112/90 (88 chunks, ~41K tokens)
- **Embedding**: OpenAI `text-embedding-3-small` (1536 dims)
- **Armazenamento**: SQLite BLOB (float32, 6.144 bytes/chunk)
- **Busca**: similaridade cosseno em Python, top-K = 5 (configurável)
- **Deduplicação**: SHA-256 do arquivo — rejeita re-ingestão acidental

#### Níveis de Confiança

| Nível   | avg similarity | Comportamento               |
| ------- | -------------- | --------------------------- |
| ALTA    | ≥ 0.85         | Resposta com fontes         |
| MÉDIA   | ≥ 0.70         | Resposta parcial            |
| BAIXA   | ≥ 0.60         | Aviso de baixa certeza      |
| SEM_RAG | < 0.60         | Conhecimento geral da IA    |

### 2.4 Configuração Discord

- TOKEN via variável de ambiente `DISCORD_BOT_TOKEN`
- MESSAGE_CONTENT Intent habilitado (obrigatório)
- Permissões: Send Messages, Read Message History

---

## 3. Instalação

### 3.1 Pré-requisitos

| Requisito         | Versão  |
| ----------------- | ------- |
| Python            | 3.12+   |
| uv                | latest  |
| Discord Bot Token | —       |
| OpenAI API Key    | —       |

### 3.2 Passo a Passo

```bash
# 1. Clone e instale
git clone https://github.com/prof-ramos/BotSalinha.git
cd BotSalinha
uv sync

# 2. Configure credenciais
cp .env.example .env
# Edite .env com DISCORD_BOT_TOKEN e OPENAI_API_KEY

# 3. Aplique migrações
uv run alembic upgrade head

# 4. Inicie o bot
uv run botsalinha run
```

### 3.3 Docker (Produção)

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## 4. Configuração

### 4.1 Variáveis de Ambiente (`.env`)

| Variável                     | Obrigatório | Padrão                         | Descrição                          |
| ---------------------------- | ----------- | ------------------------------ | ---------------------------------- |
| `DISCORD_BOT_TOKEN`          | Sim         | —                              | Token do bot Discord               |
| `OPENAI_API_KEY`             | Sim¹        | —                              | Chave OpenAI                       |
| `GOOGLE_API_KEY`             | Sim²        | —                              | Chave Google AI                    |
| `DISCORD__CANAL_IA_ID`       | Não         | None                           | Canal IA dedicado (opcional)       |
| `HISTORY_RUNS`               | Não         | `3`                            | Pares de mensagens no histórico    |
| `RATE_LIMIT__REQUESTS`       | Não         | `10`                           | Max requisições por janela         |
| `RATE_LIMIT__WINDOW_SECONDS` | Não         | `60`                           | Janela de rate limit (seg)         |
| `DATABASE__URL`              | Não         | `sqlite:///data/botsalinha.db` | URL do banco (apenas SQLite)       |
| `LOG_LEVEL`                  | Não         | `INFO`                         | Nível de log                       |
| `RAG__ENABLED`               | Não         | `true`                         | Habilitar RAG                      |
| `RAG__TOP_K`                 | Não         | `5`                            | Chunks recuperados por busca       |
| `RAG__MIN_SIMILARITY`        | Não         | `0.6`                          | Similaridade mínima                |

¹ Obrigatório quando `model.provider = openai` (padrão).
² Obrigatório quando `model.provider = google`.

### 4.2 `config.yaml`

```yaml
model:
  provider: openai          # openai | google
  id: gpt-4o-mini

rag:
  enabled: true
  top_k: 5
  min_similarity: 0.6
  confidence_threshold: 0.70
```

---

## 5. Arquitetura

```
Discord (discord.py)
    ↓
Middleware (RateLimiter — Token Bucket por usuário/guild)
    ↓
QueryService (RAG — embed → busca → RAGContext)
    ↓
AgentWrapper (Agno + OpenAI/Google — prompt aumentado)
    ↓
Repository (SQLite — histórico de conversas + índice RAG)
```

### Componentes Principais

| Componente          | Arquivo                             | Responsabilidade                          |
| ------------------- | ----------------------------------- | ----------------------------------------- |
| `BotSalinhaBot`     | `src/core/discord.py`               | Comandos Discord, on_message              |
| `AgentWrapper`      | `src/core/agent.py`                 | Geração de resposta + integração RAG      |
| `QueryService`      | `src/rag/services/query_service.py` | Busca semântica e RAGContext              |
| `IngestionService`  | `src/rag/services/ingestion_service.py` | Pipeline de ingestão de documentos    |
| `VectorStore`       | `src/rag/storage/vector_store.py`   | Busca vetorial por cosseno em SQLite      |
| `SQLiteRepository`  | `src/storage/sqlite_repository.py`  | CRUD de conversas e mensagens             |
| `DatabaseGuard`     | `src/storage/db_guard.py`           | Backup e integridade do banco             |
| `RateLimiter`       | `src/middleware/rate_limiter.py`    | Token Bucket por usuário/guild            |

---

## 6. Requisitos Não-Funcionais

| Aspecto          | Especificação                                        |
| ---------------- | ---------------------------------------------------- |
| Latência         | ~1-3s (embedding + LLM); < 100ms para busca vetorial |
| Banco de dados   | SQLite exclusivo (validado no startup)               |
| Cobertura testes | ≥ 70% (enforced em CI)                               |
| Segurança        | TLS para APIs externas; tokens em `.env`             |
| Escalabilidade   | Single instance; migrar para Postgres para multi-replica |
| Plataforma       | Linux/macOS, Python 3.12+, Docker                    |

---

## 7. Troubleshooting

### Bot não responde

1. Verifique `MESSAGE_CONTENT Intent` no [Discord Developer Portal](https://discord.com/developers/applications)
2. Confirme permissões `Send Messages` e `Read Message History`
3. Verifique `DISCORD_BOT_TOKEN` no `.env`

### RAG sem resultados

1. `!fontes` — verifique se há documentos indexados
2. `!reindexar` — reconstrói o índice
3. Verifique `OPENAI_API_KEY` para geração de embeddings

### Banco corrompido

```bash
sqlite3 data/botsalinha.db "PRAGMA integrity_check;"
uv run python scripts/backup.py list
uv run python scripts/backup.py restore --restore-from data/backups/<arquivo>.db
```

---

## 8. Roadmap

Veja [ROADMAP.md](ROADMAP.md).

---

## 9. Links

- [Discord Developer Portal](https://discord.com/developers/applications)
- [OpenAI Platform](https://platform.openai.com/)
- [Agno Framework](https://github.com/agno-agi/agno)
- [Documentação Técnica](docs/architecture.md)
- [Schema RAG](docs/rag_schema.md)
