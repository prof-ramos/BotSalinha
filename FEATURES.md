# Features

Este documento cataloga as funcionalidades do BotSalinha, detalhando seu estado atual, capacidades técnicas e critérios de verificação.

## Visão Geral de Estabilidade

| Funcionalidade             | Estado       | Categoria | Descrição                                                          |
| :------------------------- | :----------- | :-------- | :----------------------------------------------------------------- |
| **Comando !ask**           | ✅ Estável   | Core      | Interface principal de conversação via Discord                     |
| **Canal IA / DM**          | ✅ Estável   | Core      | Resposta automática em canal dedicado e mensagens diretas          |
| **Multi-Model Provider**   | ✅ Estável   | Core      | Suporte a OpenAI (padrão) e Google Gemini via `config.yaml`        |
| **Histórico Contextual**   | ✅ Estável   | Memória   | Retenção de até 3 pares de mensagens via SQLite persistente        |
| **Rate Limiting**          | ✅ Estável   | Segurança | Algoritmo Token Bucket por usuário/guild                           |
| **RAG Jurídico**           | ✅ Estável   | IA/RAG    | Busca semântica em documentos (CF/88, Lei 8.112/90) via embeddings |
| **Citação de Fontes**      | ✅ Estável   | IA/RAG    | Referência automática a artigos, incisos e parágrafos              |
| **Nível de Confiança RAG** | ✅ Estável   | IA/RAG    | Indicadores ALTA/MÉDIA/BAIXA/SEM_RAG por similaridade cosseno      |
| **Deduplicação SHA-256**   | ✅ Estável   | IA/RAG    | Rejeição de documentos duplicados via hash de arquivo              |
| **DatabaseGuard**          | ✅ Estável   | Dados     | Backup automático + integridade SQLite a cada inicialização        |
| **CLI Developer**          | ✅ Estável   | Tooling   | Interface rica para DB, sessões, RAG e prompts                     |
| **MCP Integration**        | ✅ Estável   | Tooling   | Suporte a servidores MCP (stdio/sse/streamable-http)               |
| **Dashboard Analytics**    | 🔭 Planejado | Futuro    | Interface web para visualizar uso, tokens e tópicos                |

---

## Execução Core

### 1. Comando `!ask`

- **Trigger**: `!ask <pergunta>`
- **Capacidades**:
  - Respostas formatadas em Markdown com divisão automática (limite Discord 2.000 chars)
  - Injeção de data/hora no contexto
  - Histórico de até 3 pares de mensagens (persistente em SQLite)
  - Prompt aumentado com contexto RAG quando relevante
- **Verificação**: `uv run pytest tests/unit -k ask`

### 2. Modos de Interação

| Modo               | Trigger                                 | Configuração                     |
| ------------------ | --------------------------------------- | -------------------------------- |
| Comandos prefixados | `!ask`, `!buscar`, `!fontes`, etc.    | Nenhuma                          |
| Canal IA           | Qualquer mensagem no canal configurado  | `DISCORD__CANAL_IA_ID` no `.env` |
| DM automático      | Mensagem direta para o bot             | Nenhuma (sempre ativo)           |

### 3. Multi-Model (Agno Framework)

- Provedores: `openai` (GPT-4o-mini, padrão) e `google` (Gemini 2.0 Flash)
- Provider definido exclusivamente em `config.yaml` → `model.provider`
- Credenciais em `.env` (`OPENAI_API_KEY` / `GOOGLE_API_KEY`)
- Falha rápida no startup se API key do provider ativo estiver ausente

---

## RAG — Retrieval-Augmented Generation

### Comandos Discord

| Comando              | Descrição                                                                  |
| -------------------- | -------------------------------------------------------------------------- |
| `!buscar <query>`    | Busca semântica nos documentos indexados                                   |
| `!buscar <q> <tipo>` | Busca filtrada: `artigo`, `jurisprudencia`, `questao`, `nota`, `todos`     |
| `!fontes`            | Lista documentos indexados com contagem de chunks                          |
| `!reindexar`         | Reconstrói o índice RAG completo (apenas admin)                            |

### Documentos Indexados

| Documento           | Chunks | Tokens |
| ------------------- | ------ | ------ |
| CF/88 (até EC 138)  | 687    | ~303K  |
| Lei 8.112/90        | 88     | ~41K   |

### Pipeline

1. **Ingestão**: `DOCXParser` → `ChunkExtractor` (max 500 tokens, overlap 50) → `MetadataExtractor` → `EmbeddingService` (OpenAI `text-embedding-3-small`) → SQLite BLOB (float32, 1536 dims)
2. **Consulta**: `embed_text(query)` → `cosine_similarity` em Python → top-K chunks → `ConfiancaCalculator` → `RAGContext` → prompt aumentado

### Nível de Confiança

| Nível   | Threshold avg similarity | Comportamento              |
| ------- | ------------------------ | -------------------------- |
| ALTA    | ≥ 0.85                   | Resposta com fontes        |
| MÉDIA   | ≥ 0.70                   | Resposta parcial           |
| BAIXA   | ≥ 0.60                   | Aviso de baixa certeza     |
| SEM_RAG | < 0.60 ou sem resultado  | Conhecimento geral da IA   |

> 📋 Schema técnico completo: [`docs/rag_schema.md`](docs/rag_schema.md)

---

## Dados e Segurança

### DatabaseGuard

- Backup automático no startup em `data/backups/` (mantém 5 mais recentes)
- `PRAGMA integrity_check` a cada inicialização
- Proteção contra corrupção com instrução de restauração

### Rate Limiter (Token Bucket)

- 10 requisições/minuto por usuário (configurável via `.env`)
- Proteção contra abuso e custos excessivos de API

---

## Observabilidade

- Logs estruturados JSON via `structlog` com correlation IDs
- Eventos RAG rastreáveis: `rag_ingestion_started`, `rag_busca_iniciada`, `rag_confidence_calculada`
- Scripts de métricas em `metricas/` (qualidade, performance, RAG, acesso)

---

## Como Testar uma Feature?

Cada feature nova deve acompanhar:

1. Um teste unitário em `tests/unit/`.
2. Uma entrada neste `FEATURES.md`.
3. Atualização no `ROADMAP.md` caso altere a visão de longo prazo.

```bash
uv run pytest tests/unit -v
uv run pytest tests/integration -v
uv run pytest tests/e2e -v
```
