# Implementation Plan: Atualização do docs/architecture.md

## [Overview]

Atualizar o documento de arquitetura do BotSalinha para refletir a implementação completa do sistema RAG (Retrieval-Augmented Generation), incluindo novos componentes, modelos de dados, dependências e fluxos de dados.

O documento atual (2026-02-27) está desatualizado e não documenta o módulo RAG que foi implementado, incluindo todo o pipeline de ingestão de documentos, busca semântica, e sistema de confiança. Esta atualização é essencial para que novos desenvolvedores e agentes de IA possam compreender a arquitetura completa do sistema.

## [Types]

Não há alterações em tipos de dados - este é um documento de documentação.

O documento deve refletir os seguintes tipos já existentes no código:

### Pydantic Models (RAG)
- `ChunkMetadata`: Metadados de chunks (documento, titulo, capitulo, secao, artigo, paragrafo, inciso, tipo, marcas)
- `Chunk`: Chunk de documento com texto, metadados, token_count, posicao_documento
- `Document`: Documento processado com id, nome, arquivo_origem, chunk_count, token_count
- `RAGContext`: Contexto RAG com chunks_usados, similaridades, confianca, fontes
- `ConfiancaLevel`: Enum com valores ALTA, MEDIA, BAIXA, SEM_RAG

### ORM Models (RAG)
- `DocumentORM`: Tabela rag_documents (id, nome, arquivo_origem, chunk_count, token_count, created_at)
- `ChunkORM`: Tabela rag_chunks (id, documento_id, texto, metadados, token_count, embedding, created_at)

### Configuration
- `RAGConfig`: Configurações RAG (enabled, top_k, min_similarity, max_context_tokens, documents_path, embedding_model, confidence_threshold)

## [Files]

### Arquivo Principal a Modificar
- `docs/architecture.md` - Documento principal de arquitetura

### Seções a Serem Atualizadas

1. **1. Project Structure**
   - Adicionar `src/rag/` com subdiretórios (parser/, services/, storage/, utils/)
   - Adicionar `tests/unit/rag/` e `tests/integration/rag/`
   - Adicionar novas migrações em `migrations/versions/`
   - Adicionar `docs/plans/RAG/` e `docs/plans/RAGV1.md`

2. **2. High-Level System Diagram**
   - Adicionar fluxo RAG no diagrama
   - Mostrar: User → Discord Bot → AgentWrapper → (RAG QueryService) → AI Provider

3. **3. Core Components (NOVA SEÇÃO)**
   - Adicionar seção 3.4 RAG Pipeline com:
     - Arquitetura do Pipeline (diagrama Mermaid)
     - Ingestion Service
     - Query Service
     - Confidence Calculator
     - Vector Store

4. **4. Data Stores**
   - Adicionar tabelas rag_documents e rag_chunks
   - Documentar relacionamento 1:N (DocumentORM → ChunkORM)
   - Descrever armazenamento de embeddings como BLOB (float32 array)

5. **5. External Integrations / APIs**
   - Adicionar OpenAI Embeddings API (text-embedding-3-small)

6. **9. Future Considerations / Roadmap**
   - Atualizar: RAG implementado ✅
   - Novos itens futuros (LGPD compliance, Vector DB dedicado, etc.)

## [Functions]

Não há funções a modificar - documento de documentação.

O documento deve documentar as seguintes funções/chaves do sistema RAG:

### QueryService (`src/rag/services/query_service.py`)
- `query(query_text, top_k, min_similarity, documento_id, filters) -> RAGContext`
- `query_by_tipo(query_text, tipo, top_k) -> RAGContext`
- `should_augment_prompt(context) -> bool`
- `get_augmentation_text(context) -> str`

### IngestionService (`src/rag/services/ingestion_service.py`)
- `ingest_document(file_path, document_name) -> Document`

### EmbeddingService (`src/rag/services/embedding_service.py`)
- `embed_text(text) -> list[float]`
- `embed_batch(texts) -> list[list[float]]`

### VectorStore (`src/rag/storage/vector_store.py`)
- `search(query_embedding, limit, min_similarity, documento_id, filters) -> list[tuple[Chunk, float]]`
- `get_chunk_by_id(chunk_id) -> Chunk | None`
- `count_chunks(documento_id) -> int`

### ConfiancaCalculator (`src/rag/utils/confianca_calculator.py`)
- `calculate(chunks_with_scores) -> ConfiancaLevel`
- `format_sources(chunks_with_scores) -> list[str]`

### DOCXParser (`src/rag/parser/docx_parser.py`)
- `parse() -> list[dict[str, Any]]`

### ChunkExtractor (`src/rag/parser/chunker.py`)
- `extract_chunks(parsed_doc, metadata_extractor, document_name, documento_id) -> list[Chunk]`

## [Classes]

Não há classes a modificar - documento de documentação.

O documento deve documentar as seguintes classes do sistema RAG:

### Services
- `QueryService`: Orquestra busca RAG (embedding → vector search → confidence)
- `IngestionService`: Pipeline de ingestão (parse → chunk → embed → store)
- `EmbeddingService`: Geração de embeddings via OpenAI API

### Storage
- `VectorStore`: Busca semântica com cosine similarity
- `RagRepository`: Interface de repositório RAG (stub)

### Parser
- `DOCXParser`: Parsing de documentos Word (.docx)
- `ChunkExtractor`: Extração de chunks com contexto hierárquico

### Utils
- `ConfiancaCalculator`: Cálculo de nível de confiança
- `MetadataExtractor`: Extração de metadados de documentos jurídicos brasileiros

## [Dependencies]

### Novas Dependências a Documentar

| Pacote | Versão | Propósito |
|--------|--------|-----------|
| `python-docx` | >=1.1.2,<2.0.0 | Parsing de documentos Word (.docx) |
| `numpy` | >=2.0.0,<3.0.0 | Operações vetoriais (cosine similarity) |

### Dependências Existentes Relevantes para RAG
- `openai` - API de embeddings (text-embedding-3-small)
- `sqlalchemy` - ORM para tabelas RAG
- `structlog` - Logging estruturado de eventos RAG

## [Testing]

### Testes Existentes a Documentar
- `tests/e2e/test_rag_search.py` - Testes E2E de busca RAG
- `tests/unit/rag/test_confianca_calculator.py` - Testes unitários do calculador de confiança
- `tests/unit/rag/test_vector_store.py` - Testes unitários do vector store
- `tests/integration/rag/test_recall.py` - Testes de integração de recall

### Cobertura
- RAG deve ter cobertura mínima de 70% (conforme padrão do projeto)

## [Implementation Order]

1. **Backup do documento atual**
   - Criar backup de `docs/architecture.md`

2. **Atualizar Seção 1 - Project Structure**
   - Adicionar estrutura completa de `src/rag/`
   - Adicionar testes RAG em `tests/`
   - Adicionar migrações RAG em `migrations/versions/`
   - Adicionar documentação RAG em `docs/plans/`

3. **Atualizar Seção 2 - High-Level System Diagram**
   - Adicionar fluxo RAG no diagrama ASCII
   - Mostrar integração com AgentWrapper

4. **Criar Seção 3.4 - RAG Pipeline**
   - Diagrama Mermaid do pipeline de ingestão
   - Diagrama Mermaid do pipeline de query
   - Descrição detalhada de cada componente
   - Fluxo de confiança (ALTA/MEDIA/BAIXA/SEM_RAG)

5. **Atualizar Seção 4 - Data Stores**
   - Adicionar tabelas rag_documents e rag_chunks
   - Documentar schema e relacionamentos
   - Documentar armazenamento de embeddings

6. **Atualizar Seção 5 - External Integrations**
   - Adicionar OpenAI Embeddings API

7. **Atualizar Seção 9 - Future Considerations**
   - Marcar RAG como implementado ✅
   - Adicionar próximos passos (Vector DB dedicado, PDF support, etc.)

8. **Atualizar metadados**
   - Data de última atualização
   - Revisar seção de glossário se necessário

9. **Validação final**
   - Verificar consistência com código atual
   - Verificar links e referências