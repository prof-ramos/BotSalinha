# 🛠️ Features

Este documento cataloga as funcionalidades do BotSalinha com base no estado real do código.

Atualizado em: 2026-03-01

## 📊 Matriz de Funcionalidades

| Funcionalidade | Estado | Categoria | Evidência Principal |
| :--- | :--- | :--- | :--- |
| Comandos Discord (`!ask`, `!ping`, `!ajuda`, `!limpar`, `!info`) | ✅ Estável | Core | `src/core/discord.py` |
| Modo automático Canal IA + DM | ✅ Estável | Core | `src/core/discord.py` |
| Multi-model provider (`openai` / `google`) | ✅ Estável | IA | `src/core/agent.py`, `src/config/yaml_config.py` |
| Histórico contextual persistente (SQLite) | ✅ Estável | Memória | `src/storage/sqlite_repository.py` |
| Rate limiting (token bucket) | ✅ Estável | Segurança | `src/middleware/rate_limiter.py` |
| RAG de consulta com confiança e fontes | ✅ Estável | IA/RAG | `src/rag/services/query_service.py` |
| Ingestão de DOCX para RAG | ✅ Estável | IA/RAG | `src/rag/services/ingestion_service.py` |
| Ingestão de codebase para RAG (via script) | ✅ Estável | IA/RAG | `scripts/ingest_codebase_rag.py` |
| CLI de operação/dev (prompt, config, db, logs, mcp, backup, ingest, chat, run) | 🛠️ Beta | Tooling | `src/core/cli.py` |
| Integração MCP (ferramentas externas) | ⚙️ Opcional | Extensibilidade | `src/tools/mcp_manager.py`, `config.yaml` |
| Testes de carga RAG e métricas | 🧪 Experimental | Qualidade | `tests/load/` |

## 💎 Funcionalidades Core

### 1) Comandos Discord e interação automática

- Comandos implementados: `!ask`, `!ping`, `!ajuda`/`!help`, `!limpar`/`!clear`, `!info`.
- Modo automático em Canal IA dedicado e em DMs.
- Limite de tamanho para entrada de usuário (10.000 caracteres).
- Respostas longas são fragmentadas para respeitar limite do Discord.

Verificação sugerida:

```bash
uv run pytest tests/e2e/test_commands.py -v
uv run pytest tests/unit/test_discord_on_message.py -v
```

### 2) Multi-model provider

- Seleção de provider via `config.yaml` (`openai` ou `google`).
- Validação de provider e fallback para `openai`.
- Erro explícito quando API key necessária não está configurada.

Verificação sugerida:

```bash
uv run pytest tests/unit/test_provider_selection.py -v
```

### 3) Persistência e contexto

- Conversas e mensagens persistidas com SQLAlchemy async em SQLite.
- Recuperação de histórico para contexto do agente.
- Criação/recuperação de conversa por usuário + guild/canal.

Verificação sugerida:

```bash
uv run pytest tests/unit/test_factory.py -v
uv run pytest tests/integration/test_discord_chat_flow.py -v
```

## 🧠 Funcionalidades RAG

### 1) Consulta semântica com contexto jurídico

- `QueryService` gera embeddings, consulta vetor, calcula confiança e formata fontes.
- Filtro por tipo jurídico (`artigo`, `jurisprudencia`, `questao`, `nota`, `todos`).
- Níveis de confiança (`ALTA`, `MEDIA`, `BAIXA`, `SEM_RAG`) exibidos na resposta.

Verificação sugerida:

```bash
uv run pytest tests/e2e/test_rag_search.py -v
uv run pytest tests/integration/rag/test_recall.py -v
```

### 2) Ingestão e reindexação de documentos

- Pipeline implementado: DOCXParser -> MetadataExtractor -> ChunkExtractor ->
  EmbeddingService -> SQLite (`rag_documents`, `rag_chunks`).
- **Ingestão de codebase**: Script `scripts/ingest_codebase_rag.py` para ingerir código-fonte
  do repositório usando XML do repomix. Suporta chunking inteligente, extração de metadados
  (linguagem, framework, caminho), e cálculo de custo de embeddings.

Verificação sugerida:

```bash
# Testar ingestão de codebase
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "botsalinha-codebase" --dry-run

# Testes de integração RAG
uv run pytest tests/e2e/test_rag_integration.py -v
uv run pytest tests/integration/rag/test_code_ingestion.py -v
```

## 🔧 Tooling e Operação

### 1) CLI de desenvolvedor/operação (beta)

Comandos presentes na CLI:

**Prompt Management:**
- `prompt list/show/use` - Gerenciar arquivos de prompt do sistema

**Config Management:**
- `config show/set/export` - Validar e exportar configuração YAML
- `config` (sem subcomando) - Diagnóstico de chaves de API e ambiente

**Database:**
- `db status/clear` - Verificar status e limpar banco de dados

**Logs:**
- `logs show/export` - Visualizar e exportar logs estruturados

**MCP:**
- `mcp list` - Listar servidores MCP configurados

**Operations:**
- `backup` (backup/list/restore) - Utilitários de backup do banco
- `ingest` - Ingerir documentos DOCX para RAG
- `chat` - Modo CLI interativo (sem Discord)
- `run/start` - Iniciar bot Discord (padrão)
- `stop` - Parar bot em execução
- `restart` - Reiniciar bot

Verificação sugerida:

```bash
uv run pytest tests/e2e/test_cli.py -v
```

### 2) Integração MCP (opcional)

- Gerenciador de servidores MCP implementado com suporte a transports
  `stdio`, `sse` e `streamable-http`.
- Inicialização controlada por configuração (`mcp.enabled` em `config.yaml`).
- Por padrão está desabilitado no `config.yaml` atual.

## 🛡️ Observabilidade e Resiliência

- Logging estruturado com eventos padronizados.
- Correlation ID por requisição para rastreabilidade.
- Sanitização de dados sensíveis em logs.
- Retry assíncrono com backoff para chamadas externas.

Verificação sugerida:

```bash
uv run pytest tests/unit/test_log_correlation.py -v
uv run pytest tests/unit/test_log_sanitization.py -v
uv run pytest tests/unit/test_log_events.py -v
```

## 📈 Qualidade e Performance

- Cobertura unitária, integração e e2e para fluxos centrais.
- Suite de carga para RAG com cenários de baseline, concorrência, sustained load e spike.
- Métricas de carga em `tests/load/metrics.py` e execução por `tests/load/load_test_runner.py`.

Verificação sugerida:

```bash
uv run pytest tests/load/test_rag_load.py -v -m "rag_load"
```

## 🔭 Próximas Evoluções

- Consolidar a migração total para injeção de dependência (reduzir uso legado de singleton).
- Endurecer fluxo de inicialização/cleanup do MCP em todo ciclo de vida do bot.
- Transformar suite de carga RAG em pipeline contínuo de regressão de performance.
