# RAG Jurídico - Documentação de Planejamento

Diretório contendo documentação de planejamento, decisões arquiteturais e melhorias para o sistema RAG (Retrieval-Augmented Generation) do BotSalinha.

## Contexto

O BotSalinha é um bot Discord especializado em direito brasileiro e preparação para concursos públicos. O sistema RAG permite que o bot responda perguntas jurídicas com base em documentos legais indexados, fornecendo citações precisas e indicadores de confiança.

## Documentos Indexados

| Documento | Chunks | Tokens | Arquivo |
|-----------|--------|--------|---------|
| Lei 8.112/90 | 88 | 41K | `regime_juridico_dos_servidores_civis_da_uniao_lei_8112.docx` |
| CF/88 (até EC 138) | 687 | 303K | `cf_de_1988_atualiz_ate_ec_138.docx` |

## Documentação

### [melhorias_sugeridas.md](./melhorias_sugeridas.md)
Melhorias e descobertas obtidas a partir da análise de implementação de referência. Inclui:
- Normalização de encoding para documentos jurídicos brasileiros
- Prefixos visuais para tipos de chunk
- Filtragem por tipo de metadado
- Comandos Discord adicionais
- Categorização de confiança

### [decisoes_arquiteturais.md](./decisoes_arquiteturais.md)
Registro de decisões técnicas e trade-offs analisados. Inclui:
- Stack tecnológico (SQLite, OpenAI, Agno)
- Estratégias de chunking e embeddings
- Trade-offs analisados (SQLite vs ChromaDB, OpenAI vs local)
- Problemas resolvidos (Alembic async, API key, limite de tokens)
- Decisões pendentes

## Progresso

| Milestone | Status | Descrição |
|-----------|--------|-----------|
| **M0: Fundação** | ✅ Completo | Infraestrutura, modelos, configs, 134 testes |
| **M1: Ingestão** | ✅ Completo | Parsing, chunking, embeddings, 2 docs indexados |
| **M2: Busca** | ✅ Completo | VectorStore (cosseno), QueryService, ConfiancaCalculator |
| **M3: Integração** | ✅ Completo | AgentWrapper com RAG, augment de prompts, RAGContext |
| **M4: Comandos** | ✅ Completo | `!buscar`, `!reindexar`, `!fontes`; deduplicação SHA-256 |

## Stack Tecnológico

- **Vector Store:** SQLite + índice customizado (0 dependências)
- **Embeddings:** OpenAI text-embedding-3-small ($0.02/1M tokens)
- **ORM:** SQLAlchemy 2.0 Async
- **Parsing:** python-docx
- **Orchestration:** Agno Framework

## Links Úteis

- [Plano de Implementação Principal](../../../../.omc/plans/rag-feature-implementation.md)
- [CLAUDE.md - Convenções do Projeto](../../../../CLAUDE.md)
- [Código Fonte](../../../../src/rag/)

## Comandos Úteis

```bash
# Ingerir documento
uv run bot.py ingest data/documents/lei_8112.docx --name "Lei 8.112/90"

# Rodar tests RAG
uv run pytest tests/rag/ -v

# Ver chunks no banco
sqlite3 data/botsalinha.db "SELECT COUNT(*) FROM rag_chunks;"

# Buscar (quando implementado)
uv run bot.py query "o que é estágio probatório?"
```

## Próximos Passos (Pós-MVP)

- [ ] Suporte a PDF nativo (PyMuPDF)
- [ ] Re-ranking por relevância jurídica
- [ ] Hybrid search (cosseno + BM25)
- [ ] Schema técnico: [`docs/rag_schema.md`](../../rag_schema.md)
