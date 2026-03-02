# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

## [Não lançado]

### Adicionado

- **RAG Codebase Ingestion**: Sistema completo de ingestão de código para RAG:
  - `src/rag/parser/code_chunker.py`: Chunker inteligente para código Python com detecção de estruturas (classes, funções, imports)
  - `src/rag/parser/xml_parser.py`: Parser XML para estruturação de documentos RAG
  - `src/rag/utils/code_metadata_extractor.py`: Extrator de metadados de código (assinaturas, decorators, docstrings)
  - `src/rag/services/code_ingestion_service.py`: Serviço de ingestão de codebase para RAG
  - `scripts/ingest_codebase_rag.py`: Script CLI para ingestão de codebase
  - `tests/integration/rag/test_code_ingestion.py`: Testes de integração para ingestão
  - `tests/unit/rag/test_code_chunker.py`: Testes unitários do code chunker
  - `tests/unit/rag/test_code_metadata_extractor.py`: Testes unitários do extrator de metadados
  - `tests/unit/rag/test_xml_parser.py`: Testes unitários do parser XML
  - `tests/unit/rag/test_rag_repository.py`: Testes unitários do repositório RAG

- **Fast Path para Cache Semântico**: Otimização massiva de latência em cache hits
  - Cache hit latência: 518ms → 1ms (99.8% melhoria)
  - SLO ≤100ms atingido (1ms)
  - Speedup de 11,583x em cache hits
  - `src/core/agent.py`: generate_response_with_rag() reordenado para check cache PRIMEIRO
  - `tests/unit/test_agent_fast_path.py`: 3 testes para validar Fast Path
  - `scripts/test_semantic_cache_latency.py`: Script de teste de latência
  - Fases 2 e 3 (serialização/prompt build) canceladas - SLO já atingido

- **CLI Commands**:
  - Comando `ingest`: Ingestão de codebase para RAG via CLI
  - Comando `mcp list`: Listagem de servidores MCP disponíveis

- **Dependencies**: `aiofiles>=24.1.0` adicionado para operações de I/O assíncrono

- **Documentation**:
  - `docs/architecture.md`: Documentação completa da arquitetura (1002 linhas)
  - `docs/CODE_DOCUMENTATION.md`: Documentação detalhada do código (2135 linhas)
  - Templates de documentação em `docs/templates/`:
    - `README_TEMPLATE.md`
    - `API_COMMAND_TEMPLATE.md`
    - `PYTHON_DOCSTRING_TEMPLATE.md`
    - `CHANGELOG_TEMPLATE.md`
    - `ADR_TEMPLATE.md`
    - `LLMS_TEMPLATE.md`

- **Database Migration**: `migrations/versions/20260301_1200_add_content_hash_to_rag_documents.py` adiciona campo `content_hash` para deduplicação de documentos RAG

### Alterado

- **Multi-model Provider Support**: Suporte a múltiplos providers (OpenAI + Google Gemini) com OpenAI como padrão
  - Seleção de provider via `config.yaml` e credenciais em `.env`
  - `src/config/settings.py`: Novas configurações para providers
  - `src/models/rag_models.py`: Modelos atualizados para suporte multi-provider
  - `src/rag/__init__.py`: Inicialização do módulo RAG
  - `src/rag/models.py`: Modelos RAG atualizados
  - `src/rag/parser/__init__.py`: Inicialização do submódulo parser
  - `src/rag/services/__init__.py`: Inicialização do submódulo services
  - `src/rag/services/ingestion_service.py`: Serviço de ingestão atualizado
  - `src/rag/services/query_service.py`: Serviço de query atualizado
  - `src/rag/storage/rag_repository.py`: Repositório RAG atualizado
  - `src/rag/storage/vector_store.py`: Vector store atualizado
  - `src/utils/retry.py`: Utilitário de retry melhorado

- **20 CodeRabbit Fixes**: Melhorias de qualidade, refatoração e correções aplicadas
- `docs/api.md` reestruturado em formato padronizado por comando Discord
- `docs/architecture.md` atualizado para refletir a arquitetura real atual do repositório
- `docs/README.md` atualizado com índice de templates de documentação
- `.coderabbit.yaml` atualizado com instruções/path filters e ferramentas alinhadas ao projeto
- `pytest.ini` configurado para testes RAG

## [2.0.0] - 2026-02-26

### Adicionado

- Suporte multi-model (`openai` + `google`) com OpenAI como padrão.
- Seleção de provider via `config.yaml` e credenciais em `.env`.

