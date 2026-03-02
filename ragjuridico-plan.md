# Plan: Melhorias RAG Jurídico (BotSalinha)

**Generated**: 2026-03-02

## Overview
Fortalecer o RAG jurídico para aumentar precisão de recuperação, reduzir alucinação, melhorar robustez de ingestão de documentos legais (especialmente DOCX sem estilos de heading) e criar avaliação contínua separando qualidade de retrieval da geração.

Base de análise:
- `repomix-output.xml` (visão consolidada do repositório)
- Documento exemplo real: `docs/plans/RAG/regime_juridico_dos_servidores_civis_da_uniao_lei_8112.docx`

Achados críticos que guiam o plano:
- DOCX jurídico exemplo sem headings detectáveis (`style=Normal` em 1084 parágrafos).
- `CodeIngestionService` ainda em estratégia “um chunk por arquivo”.
- `VectorStore` limita candidatos no SQL antes da similaridade vetorial final.
- Inconsistência de tokenização (`tiktoken` em chunker vs heurística `len(text)//4` em embeddings).
- Hash de documento baseado em nome/caminho, não conteúdo real.

## Prerequisites
- `uv` e `.venv` ativos
- OpenAI API key para embeddings
- SQLite com suporte a FTS5 (ou fallback controlado)
- Fixtures de avaliação jurídica (Q/A com gabarito de artigo/parágrafo/inciso)

## Dependency Graph

```text
T1 ──┬── T4 ──┬── T7 ──┐
     │        │        ├── T10 ── T11
     │        └── T8 ──┘
T2 ────── T5 ──────────┘
T6 ─────────────────────┘
T3 ─────────────────────┘
T9 ─────────────────────┘
```

## Tasks

### T1: Baseline de Qualidade de Retrieval
- **depends_on**: []
- **location**: `tests/integration/rag/`, `metricas/`, `scripts/analizar_qualidade_rag.py`, `scripts/gerar_relatorio_rag.py`
- **description**: Criar baseline offline de retrieval com métricas `Recall@k`, `MRR`, `nDCG` e taxa de citação correta (artigo/parágrafo/inciso), separando retrieval de geração.
- **validation**: Script gera relatório versionado com métricas por tipo de consulta (`artigo`, `jurisprudencia`, `concurso`, `geral`) e salva snapshot comparável.
- **status**: Completed (2026-03-02)
- **log**:
  - Implementado baseline offline separado da geração em `metricas/baseline_retrieval.py` com métricas `Recall@1/3/5`, `MRR`, `nDCG@5` e taxa de citação correta.
  - Definido benchmark padrão com consultas rotuladas por tipo (`artigo`, `jurisprudencia`, `concurso`, `geral`) para avaliação reprodutível.
  - Reescrito `scripts/analizar_qualidade_rag.py` para executar avaliação de retrieval, gerar snapshots versionados (`CSV` + `JSON`) e manter arquivos `latest` comparáveis.
  - Reescrito `scripts/gerar_relatorio_rag.py` para produzir relatório Markdown consolidado por tipo e visão geral a partir do snapshot.
  - Adicionados testes em `tests/integration/rag/test_retrieval_baseline_metrics.py` validando cálculo de métricas e regra de citação correta por tipo.
- **files edited/created**:
  - `metricas/baseline_retrieval.py`
  - `scripts/analizar_qualidade_rag.py`
  - `scripts/gerar_relatorio_rag.py`
  - `tests/integration/rag/test_retrieval_baseline_metrics.py`

### T2: Parser DOCX Jurídico Orientado à Estrutura Legal
- **depends_on**: []
- **location**: `src/rag/parser/docx_parser.py`, `src/rag/utils/metadata_extractor.py`, `tests/unit/rag/`
- **description**: Evoluir parser para detectar estrutura legal mesmo sem headings (ex.: `Art.`, `§`, `Inciso`, `Capítulo`, `Título`) e gerar marcações estruturais explícitas no parsing.
- **validation**: Testes unitários usando amostras da Lei 8.112 validando extração consistente de `artigo/paragrafo/inciso` e blocos estruturais sem depender de estilos Word, cobrindo edge cases (`Art. 1º/1o`, incisos romanos, parágrafos multiline, revogações/notas, tabelas/rodapés).
- **status**: Completed (2026-03-02)
- **log**:
  - Parser DOCX evoluído para detectar estrutura legal sem depender de estilos Word (`TÍTULO`, `CAPÍTULO`, `SEÇÃO`, `SUBSEÇÃO`, `Art.`, `§`, `Inciso`).
  - Inclusão de parágrafos de tabelas e rodapés no parsing, com marcação de origem (`body/table/footer`).
  - Inclusão de flags para notas e revogações e heurística de continuação multiline para blocos legais.
  - `MetadataExtractor` ajustado para `Art. 1º/1o`, parágrafo único e incisos romanos em formatos jurídicos comuns.
  - Testes unitários adicionados cobrindo edge cases da Lei 8.112 (incisos romanos, parágrafos multiline, revogações/notas, tabelas/rodapés).
- **files edited/created**:
  - `src/rag/parser/docx_parser.py`
  - `src/rag/utils/metadata_extractor.py`
  - `tests/unit/rag/test_docx_parser.py`
  - `tests/unit/rag/test_metadata_extractor.py`

### T3: Governança de Configuração e Rollout Seguro
- **depends_on**: []
- **location**: `src/config/settings.py`, `config.yaml.example`, `docs/features/rag.md`
- **description**: Definir feature flags e parâmetros para rollout progressivo (novas estratégias de chunking/retrieval/rerank) com fallback rápido para modo estável atual.
- **validation**: Flags documentadas, defaults seguros, inicialização sem quebra em ambiente sem novas opções e smoke test com flags on/off (incluindo migração aplicada + flag desativada).
- **status**: Completed (2026-03-02)
- **log**:
  - Adicionadas feature flags de rollout seguro em `RAGConfig` para chunking/retrieval/rerank com defaults conservadores (`enable_experimental_* = false`).
  - Incluídas validações de valores suportados e propriedades `effective_*` para fallback rápido ao modo estável quando flags experimentais estão desligadas.
  - Documentação atualizada com variáveis `BOTSALINHA_RAG__*`, tabela de flags e smoke test on/off cobrindo cenário de "migração aplicada + flag off".
- **files edited/created**:
  - `src/config/settings.py`
  - `config.yaml.example`
  - `docs/features/rag.md`

### T4: Retrieval Stage-1 Híbrido (Léxico + Semântico)
- **depends_on**: [T1]
- **location**: `src/rag/storage/vector_store.py`, `src/models/rag_models.py`, `migrations/versions/`, `tests/unit/rag/test_vector_store.py`
- **description**: Reestruturar recuperação inicial para evitar corte cego de candidatos; introduzir busca híbrida com pré-filtro lexical (FTS5/BM25) + vetorial e união de candidatos antes do rerank, com detecção explícita de capability do banco.
- **validation**: `Recall@k` melhora versus baseline; teste garante que candidatos semanticamente relevantes não sejam descartados por ordem física de tabela; integração cobre cenários com e sem FTS5 (fallback funcional).
- **status**: Completed
- **log**:
  - 2026-03-02: Implementado stage-1 híbrido em `VectorStore` com união de candidatos semânticos + léxicos, removendo corte cego por ordem física.
  - 2026-03-02: Adicionada detecção explícita de capability FTS5 e fallback lexical com `LIKE` quando FTS não está disponível.
  - 2026-03-02: Criada migração para índice FTS5 (`rag_chunks_fts`) com triggers de sincronização.
  - 2026-03-02: Testes unitários cobrindo cenários com FTS5, sem FTS5 e proteção contra perda por ordem física.
- **files edited/created**:
  - `src/rag/storage/vector_store.py`
  - `src/models/rag_models.py`
  - `migrations/versions/20260302_1400_add_rag_chunks_fts5_index.py`
  - `tests/unit/rag/test_vector_store.py`

### T5: Chunking Semântico para Documentos Jurídicos
- **depends_on**: [T2]
- **location**: `src/rag/parser/chunker.py`, `src/rag/models.py`, `tests/unit/rag/test_chunker*.py`
- **description**: Implementar chunking por fronteiras semânticas e legais (caput/incisos/parágrafos), com overlap contextual e preservação de hierarquia normativa.
- **validation**: Testes garantem que chunks não quebram no meio de incisos/§; distribuição de tamanhos estável e cobertura de contexto superior ao baseline.
- **status**: Completed (2026-03-02)
- **log**:
  - Refatorado `ChunkExtractor` para agrupar por blocos semânticos jurídicos (artigo/parágrafo/inciso), evitando quebra no meio de `§` e incisos com continuação.
  - Overlap passou a preservar fronteira de bloco e manter ao menos um parágrafo de contexto entre chunks adjacentes.
  - Enriquecido metadata com `hierarquia_normativa` e fallback de contexto legal (`artigo/paragrafo/inciso`) quando ausente no texto do chunk.
  - Criada suíte `tests/unit/rag/test_chunker_semantic.py` cobrindo integridade de fronteira legal, overlap/hierarquia e comparação de cobertura/contexto versus baseline.
- **files edited/created**:
  - `src/rag/parser/chunker.py`
  - `src/rag/models.py`
  - `tests/unit/rag/test_chunker_semantic.py`

### T6: Chunking de Código Real por Fronteiras de Função/Classe
- **depends_on**: []
- **location**: `src/rag/services/code_ingestion_service.py`, `src/rag/parser/code_chunker.py`, `tests/integration/rag/test_code_ingestion.py`
- **description**: Integrar de fato `CodeChunkExtractor` no serviço de ingestão para abandonar modo “um arquivo = um chunk” e melhorar granularidade de consultas técnicas.
- **validation**: Arquivos grandes geram múltiplos chunks com metadados de linha/função; precisão em consultas por função/classe aumenta.
- **status**: Completed (2026-03-02)
- **log**:
  - Integrado `CodeChunkExtractor` no `CodeIngestionService` (remoção do fluxo “1 arquivo = 1 chunk”).
  - `CodeIngestionService._extract_chunks_from_files` agora usa extração assíncrona centralizada e mantém recomputação de posição global dos chunks.
  - `CodeChunkExtractor` evoluído para quebrar preferencialmente em fronteiras de `def/class` (e equivalentes comuns), além do limite de tokens.
  - Teste de integração adicionado para validar split de arquivo grande em múltiplos chunks com metadados de `line_start/line_end`, `functions` e `classes`.
- **files edited/created**:
  - `src/rag/services/code_ingestion_service.py`
  - `src/rag/parser/code_chunker.py`
  - `tests/integration/rag/test_code_ingestion.py`

### T7: Reranking e Calibração por Intenção de Consulta
- **depends_on**: [T4, T5]
- **location**: `src/rag/utils/retrieval_ranker.py`, `src/rag/services/query_service.py`, `tests/unit/rag/test_query_service.py`
- **description**: Refinar pesos do rerank por tipo de consulta e normalizar `retrieval_meta` como estrutura tipada (sem serialização em string), habilitando tuning orientado a dados com compatibilidade retroativa (dual-read/dual-write temporário).
- **validation**: Melhor `MRR` por intenção, metadados estruturados em logs/debug e compatibilidade mantida durante janela de depreciação.
- **status**: Completed (2026-03-02)
- **log**:
  - Calibração de pesos de rerank por intenção (`artigo`, `jurisprudencia`, `concurso`, `geral`) implementada com normalização para soma 1.0.
  - `QueryService` passou a aplicar pesos calibrados por intenção e expor os pesos efetivos em `retrieval_meta`.
  - `retrieval_meta` de debug migrado para formato estruturado tipado (`rerank_v2_*`) com dual-write temporário do campo legado serializado (`rerank_components`).
  - Compatibilidade dual-read adicionada para contagem de componentes de rerank em logs, priorizando v2 e caindo para legado quando necessário.
  - Testes unitários atualizados para cobrir intenção/weights e dual-write/dual-read de metadados de rerank.
- **files edited/created**:
  - `src/rag/utils/retrieval_ranker.py`
  - `src/rag/services/query_service.py`
  - `tests/unit/rag/test_query_service.py`

### T8: Montagem de Contexto e Orçamento de Tokens
- **depends_on**: [T4]
- **location**: `src/rag/services/query_service.py`, `src/rag/services/embedding_service.py`, `src/rag/utils/confianca_calculator.py`
- **description**: Unificar contagem de tokens (remover heurística `len/4`), controlar budget de contexto por relevância marginal e reduzir redundância entre chunks próximos, com estratégia explícita por provider/modelo (OpenAI/Gemini).
- **validation**: Contexto final respeita limite de tokens com menor perda de evidência relevante; logs mostram budget e motivo de corte; testes parametrizados por provider/modelo.
- **status**: Completed (2026-03-02)
- **log**:
  - Unificada contagem de tokens no `EmbeddingService` com estratégia por provider/modelo (OpenAI via `tiktoken`; Gemini via fallback lexical determinístico).
  - `QueryService` passou a selecionar contexto por orçamento de tokens com utilidade marginal e filtro de redundância.
  - `retrieval_meta` enriquecido com métricas de budget (`tokens_used`, `skipped_*`, provider/modelo/context budget).
  - `ConfiancaCalculator` ganhou utilitários para cálculo de redundância e utilidade marginal.
  - Testes unitários parametrizados por provider/modelo e cobertura do novo budget de contexto.
- **files edited/created**:
  - `src/rag/services/embedding_service.py`
  - `src/rag/services/query_service.py`
  - `src/rag/utils/confianca_calculator.py`
  - `tests/unit/rag/test_embedding_service.py`
  - `tests/unit/rag/test_query_service.py`

### T9: Refresh Incremental de Embeddings por Conteúdo
- **depends_on**: []
- **location**: `src/rag/services/ingestion_service.py`, `src/rag/services/code_ingestion_service.py`, `src/models/rag_models.py`, `migrations/versions/`
- **description**: Trocar deduplicação por hash de caminho/nome para hash de conteúdo real (documento/chunk), com migração + backfill de legado (`hash` nulo/antigo), atualização incremental e reindex seletivo idempotente.
- **validation**: Alterar conteúdo sem alterar path dispara re-embed apenas dos chunks afetados; sem duplicação incorreta; backfill mantém unicidade e reindex repetido não cria divergência.
- **status**: Completed (2026-03-02)
- **log**:
  - Hash de documento migrado para conteúdo real do arquivo (`SHA-256` dos bytes), removendo dependência de nome/caminho.
  - Adicionado `content_hash` por chunk (`rag_chunks`) com backfill de legado e índice dedicado.
  - Migração aplica backfill de `rag_documents.content_hash` a partir da assinatura dos chunks (com resolução determinística de colisões para manter unicidade).
  - `IngestionService` e `CodeIngestionService` passaram a usar refresh incremental idempotente:
    - detectam documento inalterado e pulam re-embed;
    - reaproveitam embeddings de chunks inalterados por hash de conteúdo;
    - re-embedam somente chunks novos/alterados;
    - mantêm backfill automático para hashes legados nulos.
  - Reexecuções sucessivas com mesmo conteúdo não geram divergência nem custo adicional de embeddings.
- **files edited/created**:
  - `src/rag/services/ingestion_service.py`
  - `src/rag/services/code_ingestion_service.py`
  - `src/models/rag_models.py`
  - `migrations/versions/20260302_1800_refresh_content_hash_for_incremental_ingestion.py`

### T10: Avaliação Integrada (Retrieval + Resposta Final)
- **depends_on**: [T1, T7, T8, T9]
- **location**: `tests/e2e/test_rag_search.py`, `tests/integration/rag/test_recall.py`, `metricas/`
- **description**: Criar suíte de avaliação completa com métricas de retrieval e de resposta fundamentada (citação correta, cobertura normativa, taxa de “sem base”).
- **validation**: Pipeline CI produz relatório comparando baseline e candidato; critérios mínimos de aprovação definidos com SLOs (`P95` latência, custo por consulta e taxa de timeout/erro).
- **status**: Completed (2026-03-02)
- **log**:
  - Implementado módulo `metricas/integrated_evaluation.py` unificando avaliação de retrieval + resposta final, com métricas de:
    - `Recall@5` e citação correta de retrieval;
    - citação correta da resposta final, cobertura normativa e taxa de “sem base”;
    - SLOs operacionais (`P95` latência, custo médio por consulta, taxa de timeout e erro).
  - Implementada comparação baseline vs candidato com deltas e gate de aprovação (`candidate_beats_baseline` + `all_pass`).
  - Adicionado teste E2E para validar comparação baseline/candidato e aplicação de SLOs com cenário sintético controlado.
  - Adicionado teste de integração executando consultas reais de retrieval e avaliando baseline/candidato de resposta sobre o mesmo conjunto de queries.
- **files edited/created**:
  - `metricas/integrated_evaluation.py`
  - `tests/e2e/test_rag_search.py`
  - `tests/integration/rag/test_recall.py`

### T11: Operação, Comandos de Administração e Runbooks
- **depends_on**: [T10]
- **location**: `src/core/discord.py`, `scripts/ingest_all_rag.py`, `docs/features/rag.md`, `docs/backup_restore.md`
- **description**: Consolidar comandos de operação (`!fontes`, `!reindexar`, reindex incremental), observabilidade e runbooks de recuperação para produção.
- **validation**: Comandos funcionam em ambiente de teste e documentação operacional cobre cenários de falha e rollback.
- **status**: Completed (2026-03-02)
- **log**:
  - Implementado `!fontes` no Discord para listar catálogo RAG com totais de documentos/chunks/tokens.
  - Implementado `!reindexar [completo|incremental]` (owner only) com:
    - `completo`: rebuild total do índice via `IngestionService.reindex`;
    - `incremental`: refresh por hash de conteúdo com contagem de atualizados/inalterados/falhas.
  - Adicionada observabilidade operacional com logs estruturados de início/fim e métricas de execução:
    - `LogEvents.RAG_REINDEXACAO_INICIADA` / `LogEvents.RAG_REINDEXACAO_CONCLUIDA`;
    - eventos operacionais `rag_fontes_consultadas`, `rag_reindex_command_started`, `rag_reindex_command_completed`, `rag_reindex_incremental_document_failed`.
  - Reescrito `scripts/ingest_all_rag.py` para operação em produção:
    - CLI com `--mode incremental|completo`, `--docs-dir`, `--pattern`, `--recursive`;
    - incremental idempotente por hash de conteúdo e CSV de métricas;
    - completo com rebuild total via `IngestionService.reindex`.
  - Atualizados runbooks e documentação operacional em `docs/features/rag.md` e `docs/backup_restore.md` com procedimentos de recuperação, observabilidade e rollback operacional.
- **files edited/created**:
  - `src/core/discord.py`
  - `scripts/ingest_all_rag.py`
  - `docs/features/rag.md`
  - `docs/backup_restore.md`

## Parallel Execution Groups

| Wave | Tasks | Can Start When |
|------|-------|----------------|
| 1 | T1, T2, T3, T6, T9 | Immediately |
| 2 | T4, T5 | T4 após T1; T5 após T2 |
| 3 | T7, T8 | T4 + T5 (T7) / T4 (T8) |
| 4 | T10 | T1 + T7 + T8 + T9 complete |
| 5 | T11 | T10 complete |

## Testing Strategy
- Unit: parser, metadata extraction, chunking, token counting, ranking components.
- Integration: ingestão DOCX + query com filtros + comparação baseline.
- E2E: fluxo Discord com contexto RAG e fontes.
- Offline eval: benchmark fixo com Lei 8.112 e documentos já indexados.

## Risks & Mitigations
- **Risco**: FTS5 indisponível no ambiente SQLite.
  - **Mitigação**: fallback para índice léxico simplificado e flag de capability.
- **Risco**: aumento de latência com pipeline híbrido + rerank.
  - **Mitigação**: candidate caps dinâmicos por tipo de query e cache de embeddings/query.
- **Risco**: regressão na qualidade por mudança agressiva de chunking.
  - **Mitigação**: rollout por feature flag + A/B offline com baseline congelado.
- **Risco**: custo maior de embeddings.
  - **Mitigação**: incremental refresh por hash de conteúdo + batching com orçamento de tokens.

## Assumptions
- O foco principal é RAG jurídico em DOCX normativo (não apenas codebase RAG).
- `repomix-output.xml` é artefato de análise, não fonte oficial única de ingestão de produção.
- O documento Lei 8.112 é representativo de outros documentos jurídicos do projeto.
