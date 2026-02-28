# Auditoria de Planos Markdown

**Data da auditoria:** 2026-02-28  
**Escopo aplicado:** apenas `docs/plans/**/*.md` e `plans/**/*.md` (conforme definido)  
**Política de limpeza:** agressiva (com aviso de dependências de links)

## 1) Inventário analisado

| Arquivo | Tipo | Situação atual | Recomendação |
|---|---|---|---|
| `docs/plans/alinhamento-multi-model.md` | plano de implementação | checklist 100% concluído (`[x]`) | candidato a remoção |
| `docs/plans/mcp-integration.md` | plano de implementação | parcialmente implementado | manter (plano ainda aberto) |
| `docs/plans/RAGV1.md` | plano inicial/legado | desalinhado da implementação atual | candidato a remoção |
| `docs/plans/RAG/README.md` | status de milestones | status defasado em relação ao código | candidato a remoção |
| `docs/plans/RAG/decisoes_arquiteturais.md` | decisões e histórico técnico | contém pendências já superadas e partes defasadas | candidato a remoção |
| `docs/plans/RAG/melhorias_sugeridas.md` | backlog de melhorias | checklist aberto, mas várias partes já foram implementadas | candidato a remoção |
| `docs/plans/AGENTS.md` | instruções operacionais | referência ativa para os planos | manter |
| `plans/analise_revisao_codigo.md` | análise pontual de revisão | parcialmente absorvido, sem vínculo ativo formal | candidato a remoção |
| `plans/AGENTS.md` | instruções operacionais | arquivo de instrução, não plano de entrega | manter |

## 2) Propostas que **não foram criadas** ou estão **parciais**

| Origem | Proposta | Status | Evidência no código | Ação sugerida |
|---|---|---|---|---|
| `docs/plans/mcp-integration.md` (seção "Integração com AgentWrapper") | criar `initialize_mcp()` e `cleanup_mcp()` no `AgentWrapper` | **não criado** | `src/core/agent.py` possui `_mcp_manager`, mas não possui esses métodos (busca sem ocorrências por `initialize_mcp`/`cleanup_mcp`) | implementar métodos de lifecycle MCP **ou** atualizar plano para refletir estratégia final |
| `docs/plans/RAG/README.md` (M4) + `docs/plans/RAG/melhorias_sugeridas.md` | comandos `!reindexar` e `!fontes` | **não criado** | `src/core/discord.py` não registra comandos `fontes`/`reindexar`; `tests/e2e/test_rag_reindex.py:88` e `:111` têm `pytest.skip("Command !reindexar not yet implemented")` | implementar comandos e remover `skip`, ou retirar dos planos |
| `docs/plans/RAG/melhorias_sugeridas.md` | `formatador.py` para prefixos visuais de chunk | **não criado** | arquivo citado no plano não existe; não há uso de `formatador.py` no código | implementar formatter dedicado **ou** consolidar no fluxo atual de resposta |
| `plans/analise_revisao_codigo.md` | `ErrorRegistry` para centralizar mensagens de erro de UI | **parcial** | existe `src/utils/ui_errors.py` (`get_user_friendly_message`), mas sem referências de uso no fluxo principal | integrar mapper no tratamento de exceções do bot e padronizar rota de erro |
| `plans/analise_revisao_codigo.md` | concluir migração de Singleton para DI (`create_repository`) | **parcial** | uso legado de `get_repository()` ainda em `src/core/lifecycle.py`, `src/facade.py`, `src/storage/repository_factory.py` | migrar chamadas remanescentes para factory/context manager |
| `plans/analise_revisao_codigo.md` | contagem de tokens precisa (evitar heurística) | **parcial** | há `tiktoken` no `chunker`, mas `src/rag/services/embedding_service.py` e `src/rag/services/code_ingestion_service.py` ainda usam `len(text) // 4` | unificar tokenização real para ingestão/embeddings |

## 3) Itens propostos que já existem (checklists defasados)

Esses itens aparecem abertos em planos, mas já estão no código:

- **Normalização de texto/consulta RAG:** `src/rag/utils/normalizer.py` e uso no parser/serviços.
- **Campo `tipo` em metadados:** `src/rag/models.py` (`ChunkMetadata.tipo`).
- **Filtro por tipo na consulta:** `QueryService.query_by_tipo(...)` em `src/rag/services/query_service.py`.
- **Categorias de confiança:** `ConfiancaLevel` e mensagens de confiança em `src/rag/utils/confianca_calculator.py`.

## 4) Arquivos antigos/planos que podem ser apagados (modo agressivo)

### 4.1) Candidatos diretos

1. `docs/plans/RAGV1.md`  
2. `docs/plans/RAG/README.md`  
3. `docs/plans/RAG/decisoes_arquiteturais.md`  
4. `docs/plans/RAG/melhorias_sugeridas.md`  
5. `docs/plans/alinhamento-multi-model.md`  
6. `plans/analise_revisao_codigo.md`  

### 4.2) Não apagar agora (ainda úteis/ativos)

1. `docs/plans/mcp-integration.md` (plano ainda aberto com pendências reais).  
2. `docs/plans/AGENTS.md` e `plans/AGENTS.md` (instruções operacionais, não backlog de entrega).  

## 5) Dependências antes da remoção

Para evitar links quebrados ao apagar os candidatos:

1. Atualizar `docs/README.md:16` (remove referência para `docs/plans/alinhamento-multi-model.md`).  
2. Atualizar `llms.txt:29` (remove referência para `docs/plans/RAGV1.md`).  
3. Se remover `docs/plans/alinhamento-multi-model.md`, ajustar `docs/plans/AGENTS.md:23`.  
4. Se remover parcialmente a pasta `docs/plans/RAG` (e não tudo), revisar links internos em:
   - `docs/plans/RAG/README.md:18` e `:26`
   - `docs/plans/RAG/decisoes_arquiteturais.md:368`

## 6) Resumo executivo

- O escopo de planos contém documentos concluídos e legados misturados com apenas 1 plano ainda ativo (`mcp-integration.md`).
- Há pendências técnicas reais não implementadas (MCP lifecycle no `AgentWrapper`, comandos RAG de administração, integração efetiva de UI error mapping, migração completa para DI).
- Em política agressiva, é seguro preparar limpeza dos planos legados, desde que os links de `docs/README.md` e `llms.txt` sejam ajustados antes.
