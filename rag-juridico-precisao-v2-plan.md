# Plan: RAG Jurídico de Precisão v2 (Swarm)

**Generated**: 2026-03-03

## Overview
Este plano transforma a proposta de RAG jurídico profissional em execução incremental dentro da arquitetura atual do BotSalinha, priorizando precisão normativa, controle temporal (vigência/alteração), rastreabilidade de fontes e mitigação de alucinação.

Foco do v2:
- enriquecer metadados jurídicos (concurso, vigência, alteração, revogação/vetos);
- consolidar chunking estrutural parent-child para legislação e blocos autossuficientes para questões;
- reforçar recuperação híbrida com filtros fortes de metadados e rerank jurídico;
- endurecer grounding no prompt com citação obrigatória (Lei/Art./data);
- validar com suíte temporal-jurídica (pré/pós-alteração legislativa).

## Prerequisites
- Ambiente com `uv` e `.venv` operacionais.
- Banco de dados SQLite com migrações aplicáveis.
- Corpus jurídico em `docs/plans/RAG/` e diretório de ingestão configurado.
- Chaves de API válidas para embeddings/modelo.
- Dependências externas com documentação atualizada consultada (Context7):
  - Chroma: filtros por metadados e documento (`where`/`where_document`).
  - LlamaIndex: parsing hierárquico e pipeline de metadados para parent-child.
  - SentenceTransformers: `CrossEncoder.rank()` para reranking de top-k.

## Dependency Graph

```text
T1 ──┬── T2 ──┬── T4 ───────────────┐
     │        └── T8a ──────────┐   │
     ├── T3 ─┐                  ├── T8b ─┐
     ├── T5 ─┼── T6 ──┐         │        │
T10 ─┘       └── T7 ──┴── T9 ───┴── T11 ─┤
                                          ├── T12 ── T13
                                          └── T12a
```

## Tasks

### T1: Modelo de Metadados Jurídicos v2
- **depends_on**: []
- **location**: `src/rag/models.py`, `docs/rag_schema.md`
- **description**: Expandir `ChunkMetadata` e contratos de schema com campos jurídicos: `law_name`, `law_number`, `article`, `content_type`, `exam_references[]`, `valid_from`, `valid_to`, `updated_by_law`, `is_revoked`, `is_vetoed`, `is_exam_focus`, `jurisprudence_linked[]`.
- **validation**: Testes de modelo aceitam payloads novos/legados sem quebra, com serialização/deserialização consistente.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T2: Migrações e Compatibilidade de Dados
- **depends_on**: [T1]
- **location**: `migrations/versions/`, `src/models/rag_models.py`
- **description**: Criar migrações para suportar os campos v2 e estratégia de compatibilidade retroativa (dual-read de metadados legados + normalização para novo shape).
- **validation**: Migração sobe e desce sem perda crítica; leitura de chunks antigos continua funcional.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T3: Extração de Metadados de Concurso/Legenda
- **depends_on**: [T1]
- **location**: `src/rag/utils/metadata_extractor.py`, `tests/unit/rag/test_metadata_extractor.py`
- **description**: Implementar extração robusta de padrões de prova (`(PCPR-2013)`, banca/ano múltiplos, siglas tribunal) e mapear para `exam_references[]` + `is_exam_focus`.
- **validation**: Suite de regex cobre múltiplos formatos reais de marcação e evita falso positivo em números de artigo/lei.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T4: Normalização Temporal e Vigência Legislativa
- **depends_on**: [T1, T2]
- **location**: `src/rag/utils/metadata_extractor.py`, `src/rag/parser/docx_parser.py`, `tests/unit/rag/test_docx_parser.py`
- **description**: Extrair `valid_from`, `updated_by_law`, marcadores de alteração (ex.: “Incluído pela Lei ...”), revogação e veto, com regras de precedência temporal e escopo (`revocation_scope`, `veto_scope`, `temporal_confidence`, `effective_text_version`).
- **validation**: Casos de teste distinguem texto vigente, revogado/vetado total e parcial; datas são parseadas em formato ISO consistente.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T5: Classificação de Tipo de Conteúdo Jurídico
- **depends_on**: [T1]
- **location**: `src/rag/utils/metadata_extractor.py`, `src/rag/parser/docx_parser.py`, `tests/unit/rag/test_chunker_semantic.py`
- **description**: Classificar cada chunk em `content_type` (`legal_text`, `jurisprudence`, `exam_question`, `doctrine`) com heurísticas auditáveis.
- **validation**: Classificador atinge precisão mínima definida em conjunto de validação rotulado manualmente.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T6: Chunking Parent-Child Jurídico
- **depends_on**: [T1, T3, T5]
- **location**: `src/rag/parser/chunker.py`, `src/rag/models.py`, `tests/unit/rag/test_chunker_semantic.py`
- **description**: Consolidar estratégia parent-child: pai = artigo/caput consolidado; filhos = incisos/parágrafos/juris vinculada; preservar referências de parent no child.
- **validation**: Nenhum chunk filho sem parent; recuperação de child reconstrói contexto do parent sem truncar sentido normativo; `exam_question` permanece bloco autossuficiente.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T7: Ingestão Idempotente v2 com Enriquecimento
- **depends_on**: [T2, T4, T5, T6]
- **location**: `src/rag/services/ingestion_service.py`, `scripts/ingest_all_rag.py`, `tests/integration/rag/test_recall.py`
- **description**: Atualizar pipeline de ingestão para preencher metadados v2, manter deduplicação por hash de conteúdo e registrar lineage (`source_doc`, `ingested_at`, `parser_version`, `embedding_model`, `schema_version`), com política de reembed por versão.
- **validation**: Reingestão não duplica dados, atualiza chunks alterados e dispara reembed quando `parser_version`, `embedding_model` ou `schema_version` mudarem.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T8a: Recuperação Híbrida com Filtro Jurídico Forte (Implementação)
- **depends_on**: [T2, T4, T5, T10]
- **location**: `src/rag/storage/vector_store.py`, `src/rag/services/query_service.py`, `tests/unit/rag/test_vector_store.py`
- **description**: Expandir filtros estruturados (lei, artigo, período, tribunal, conteúdo) na busca híbrida e garantir prioridade de termo exato para artigos/leis/siglas; atualizar whitelist de filtros v2 com bloqueio explícito de chave inválida.
- **validation**: Consultas com filtros retornam apenas candidatos compatíveis; cenário “Art. 17-A” não degrada para resultados sem correspondência legal; chaves não permitidas são rejeitadas.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T8b: Recuperação Híbrida com Filtro Jurídico Forte (Validação Integrada)
- **depends_on**: [T7, T8a]
- **location**: `tests/integration/rag/test_recall.py`, `tests/integration/rag/test_retrieval_baseline_metrics.py`
- **description**: Validar recuperação híbrida com dados reais já enriquecidos na ingestão v2, garantindo comportamento estável fora de cenários unitários.
- **validation**: Testes de integração aprovam filtros e prioridade lexical em corpus real reingerido.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T9: Reranking Jurídico e Desambiguação Temporal
- **depends_on**: [T6, T7, T8b]
- **location**: `src/rag/utils/retrieval_ranker.py`, `src/rag/services/query_service.py`, `tests/unit/rag/test_query_service.py`
- **description**: Integrar perfil de rerank jurídico (opcional CrossEncoder) privilegiando vigência e compatibilidade temporal (pré/pós lei alteradora), com fallback determinístico local.
- **validation**: Ganho em MRR/nDCG nos cenários com conflito temporal e redução de citações de entendimento superado.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T10: Query Rewriting e Dicionário Jurídico
- **depends_on**: []
- **location**: `src/rag/utils/normalizer.py`, `src/rag/services/query_service.py`, `tests/unit/rag/test_normalizer.py`
- **description**: Criar camada de reescrita de consulta e sinonímia jurídica (`LIA -> Lei 8.429`, `Nova Lei de Licitações -> Lei 14.133/2021`) com rastreabilidade no `retrieval_meta`.
- **validation**: Reescritas são explicáveis, reversíveis no log e melhoram recall em consultas coloquiais.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T11: Grounding Estrito e Citação Obrigatória
- **depends_on**: [T9]
- **location**: `src/core/agent.py`, `prompt/prompt_v4_rag_first.md`, `tests/e2e/test_rag_search.py`
- **description**: Endurecer instruções do agente: responder apenas com contexto recuperado, citar Lei/Artigo/ano de atualização e sinalizar conflito temporal quando houver; definir fallback para ausência de fonte, conflito forte ou inconsistência de contexto.
- **validation**: Testes E2E falham se resposta sem citação jurídica mínima, sem fallback quando faltar base, ou sem alerta em conflito pré/pós alteração.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T12a: Curadoria do Gold Set Jurídico Versionado
- **depends_on**: [T9, T10, T11]
- **location**: `tests/fixtures/`, `metricas/`, `docs/plans/RAG/`
- **description**: Criar e versionar dataset ouro com casos anotados (revogação, veto, conflito temporal, citações esperadas) para validação contínua.
- **validation**: Dataset possui versão, critérios de aceitação por cenário e rastreabilidade de atualização.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T12: Avaliação de Precisão Jurídica e Gate de Produção
- **depends_on**: [T9, T10, T11]
- **location**: `metricas/integrated_evaluation.py`, `tests/integration/rag/test_retrieval_baseline_metrics.py`, `tests/e2e/test_rag_search.py`
- **description**: Definir benchmark jurídico final com casos críticos: revogação, veto e conflito temporal (pré/pós-2021), e criar gate de aprovação para rollout.
- **validation**: Pipeline gera relatório com `Recall@k`, `MRR`, `nDCG`, taxa de citação correta e taxa de erro temporal; gate bloqueia regressão.
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T13: Rollout Canário e Rollback Automático
- **depends_on**: [T12, T12a]
- **location**: `src/config/settings.py`, `docs/features/rag.md`, `docs/operations/chromadb-runbook.md`
- **description**: Definir rollout por fases (5%/25%/100%), alarmes de regressão temporal/citação e rollback automático por SLO.
- **validation**: Procedimento de canary e rollback testado em ambiente de staging com simulação de regressão.
- **status**: Not Completed
- **log**:
- **files edited/created**:

## Parallel Execution Groups

| Wave | Tasks | Can Start When |
|------|-------|----------------|
| 1 | T1, T10 | Imediatamente |
| 2 | T2, T3, T5 | T1 concluído |
| 3 | T4, T6 | T4 após T1+T2; T6 após T1+T3+T5 |
| 4 | T7, T8a | T7 após T2+T4+T5+T6; T8a após T2+T4+T5+T10 |
| 5 | T8b | T7+T8a concluídos |
| 6 | T9 | T6+T7+T8b concluídos |
| 7 | T11 | T9 concluído |
| 8 | T12, T12a | T9+T10+T11 concluídos |
| 9 | T13 | T12+T12a concluídos |

## Testing Strategy
- Unit: regex/extração/classificação de metadados e rewriting jurídico.
- Integration: ingestão incremental + filtros híbridos + rerank temporal.
- E2E: respostas com citação obrigatória e alertas de mudança legislativa.
- Benchmark jurídico: cenários fixos de revogação, veto e conflito temporal.

## Risks & Mitigations
- **Risco**: Heurísticas de extração temporal gerarem falso positivo.
  - **Mitigação**: validação por corpus anotado + flags de baixa confiança para revisão.
- **Risco**: Reranker externo aumentar latência e custo.
  - **Mitigação**: rerank condicional apenas no top-k e fallback para perfil local.
- **Risco**: Backward compatibility quebrar consultas antigas.
  - **Mitigação**: dual-read de metadados e migração em fases com canary.
- **Risco**: Resposta excessivamente restrita virar “não sei” em excesso.
  - **Mitigação**: ajustes graduais do prompt com testes A/B internos.

## Assumptions
- O objetivo deste plano é evolução do RAG jurídico já existente (não reescrever stack completa).
- Chroma e LlamaIndex permanecem opcionais/plugáveis; o caminho principal mantém compatibilidade com SQLite atual.
- O fluxo de execução será multiagente por ondas conforme dependências acima.
