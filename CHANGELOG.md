# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

## [Não lançado]

### Adicionado

- `docs/rag_schema.md` — schema técnico completo do RAG (DDL, Pydantic, pipelines, thresholds, erros)
- Deduplicação de documentos por SHA-256 (`file_hash` em `rag_documents`, `DuplicateDocumentError`)
- Migração Alembic `add_file_hash_to_rag_documents` com índice único (permite NULL para retrocompatibilidade)
- `DatabaseGuard` — backup automático + `PRAGMA integrity_check` a cada startup

### Alterado

- `FEATURES.md` — RAG atualizado de "Planejado" → "Estável"; CLI de "Beta" → "Estável"
- `ROADMAP.md` — RAG marcado como concluído; seção de stack obsoleta removida
- `docs/plans/RAG/README.md` e `decisoes_arquiteturais.md` — milestones atualizados para concluídos

### Removido

- `implementation_plan.md` — plano de tarefa concluída
- `docs/plans/alinhamento-multi-model.md` — plano 100% concluído
- `docs/plans/RAGV1.md` — plano inicial substituído pela implementação real

---

## [2.1.0] - 2026-02-28

### Adicionado

- RAG completo com embeddings OpenAI `text-embedding-3-small` (1536 dims, BLOB float32)
- Pipeline de ingestão DOCX: parse → chunking hierárquico (500 tokens, overlap 50) → metadata → embed → SQLite
- Pipeline de consulta: embed query → similaridade cosseno → `ConfiancaCalculator` → prompt aumentado
- Modelos ORM: `DocumentORM` (`rag_documents`) e `ChunkORM` (`rag_chunks`)
- Modelos Pydantic: `ChunkMetadata` (9 marcadores booleanos), `RAGContext`, `ConfiancaLevel`
- Comandos Discord: `!buscar`, `!fontes`, `!reindexar`
- Modo Canal IA automático via `DISCORD__CANAL_IA_ID`
- Modo DM automático (sempre ativo)
- Integração MCP via `MCPToolsManager` (stdio/sse/streamable-http)
- CLI `uv run botsalinha ingest` para indexar documentos DOCX

### Alterado

- `AgentWrapper` integrado com `QueryService` para augmentação automática de prompts
- `docs/architecture.md` — documentação completa do RAG (seção 3.4)

---

## [2.0.0] - 2026-02-26

### Adicionado

- Suporte multi-model (`openai` + `google`) com OpenAI como padrão
- Seleção de provider via `config.yaml` e credenciais em `.env`
