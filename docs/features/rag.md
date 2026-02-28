# Feature RAG (Retrieval-Augmented Generation)

## Visão Geral

O BotSalinha implementa um sistema RAG que permite respostas jurídicas fundamentadas em documentos reais (Constituição Federal de 1988 e Lei 8.112/90), com citações precisas e indicadores de confiança.

## Arquitetura

```
DOCX/PDF → Parser → MetadataExtractor → ChunkExtractor → EmbeddingService → SQLite/Qdrant
                                                                   ↓
Usuario → Discord → QueryService → VectorStore (SQLite ou Qdrant) → Agno → Resposta com Fontes
```

## Componentes

### 1. Modelos de Dados

#### DocumentORM
- Representa um documento indexado (CF/88, Lei 8.112/90)
- Campos: `nome`, `arquivo_origem`, `chunk_count`, `token_count`

#### ChunkORM
- Representa um fragmento de texto com embedding
- Campos: `id`, `documento_id`, `texto`, `metadados` (JSON), `embedding` (BLOB)

### 2. Serviços RAG

#### IngestionService (`src/rag/services/ingestion_service.py`)
Responsável por ingerir documentos DOCX no sistema RAG.

**Pipeline:**
1. Parse DOCX com `DOCXParser`
2. Extrair metadados com `MetadataExtractor`
3. Criar chunks com `ChunkExtractor`
4. Gerar embeddings com `EmbeddingService`
5. Salvar no banco SQLite

**Método principal:**
```python
await ingestion_service.ingest_document(
    file_path="docs/plans/RAG/cf_de_1988_atualiz_ate_ec_138.docx",
    document_name="CF/88"
)
```

#### QueryService (`src/rag/services/query_service.py`)
Orquestra a busca semântica e retorna contexto RAG.

**Método principal:**
```python
rag_context = await query_service.query(
    query_text="Quais são os direitos fundamentais?",
    top_k=5,
    min_similarity=0.6
)
```

**Retorna:**
- `chunks_usados`: Lista de chunks relevantes
- `similaridades`: Scores de similaridade (0-1)
- `confianca`: Nível de confiança (ALTA/MÉDIA/BAIXA/SEM_RAG)
- `fontes`: Lista de citações formatadas

#### VectorStore (`src/rag/storage/vector_store.py`)
Implementa busca vetorial com similaridade de cosseno em SQLite.

**Características:**
- Armazena embeddings como BLOB (float32 arrays)
- Busca por similaridade de cosseno com numpy
- Suporte a filtros por documento e metadados

#### ConfiancaCalculator (`src/rag/utils/confianca_calculator.py`)
Calcula nível de confiança baseado na similaridade média.

**Níveis:**
- **ALTA** (≥0.85): Resposta baseada em documentos
- **MÉDIA** (0.70-0.84): Parcialmente baseada
- **BAIXA** (0.60-0.69): Informações limitadas
- **SEM_RAG** (<0.60): Conhecimento geral

## Comandos Discord

### `!fontes`
Lista documentos jurídicos indexados no RAG.

**Uso:**
```
!fontes
```

**Resposta:**
```
📚 Fontes RAG Indexadas

CF/88
2450 chunks | 125000 tokens

Lei 8.112/90
850 chunks | 42000 tokens

Total: 2 documentos
```

### `!reindexar` (Admin apenas)
Recria o índice RAG do zero. Deleta todos chunks e documentos, então reingesta todos os arquivos DOCX.

**Uso:**
```
!reindexar
```

**Requisitos:**
- Apenas o dono do bot pode executar
- Documentos DOCX devem estar em `data/documents/`

**Resposta:**
```
✅ Reindexação RAG Concluída!

📄 Documentos processados: 2
📦 Chunks criados: 3300
⏱️ Tempo total: 12.5s

O índice RAG foi reconstruído com sucesso.
```

## Configurações

### Variáveis de Ambiente

```bash
# .env (formato aninhado com __ é obrigatório para RAG)
RAG__ENABLED=true                    # Habilitar/desabilitar RAG
RAG__TOP_K=5                         # Número de chunks a recuperar
RAG__MIN_SIMILARITY=0.6              # Similaridade mínima aceitável
RAG__MAX_CONTEXT_TOKENS=2000         # Máximo de tokens no contexto
RAG__CONFIDENCE_THRESHOLD=0.70       # Limiar para confiança média
RAG__VECTOR_BACKEND=sqlite            # sqlite (padrao) ou qdrant
RAG__QDRANT_URL=http://localhost:6333 # URL do Qdrant
RAG__QDRANT_COLLECTION=botsalinha_chunks
OPENAI_API_KEY=sk-...                # Usada para embeddings
```

### Configuração YAML (`config.yaml`)

```yaml
rag:
  enabled: true
  top_k: 5
  min_similarity: 0.6
  confidence_threshold: 0.70
```

## Estratégia de Chunking

### Configuração

```python
CHUNK_CONFIG = {
    "max_tokens": 500,           # Tamanho máximo por chunk (~2000 chars)
    "overlap_tokens": 50,        # Overlap entre chunks (~200 chars)
    "respect_boundaries": True,  # Não quebrar artigos/incisos
    "min_chunk_size": 100,       # Tamanho mínimo válido
}
```

### Metadados Extraídos

| Campo | Fonte | Exemplo |
|-------|-------|---------|
| `documento` | Nome do arquivo | "CF/88" |
| `titulo` | Estilo "Heading 1-9" | "TÍTULO II" |
| `capitulo` | Estilo "Heading 1-9" | "CAPÍTULO I" |
| `artigo` | Regex "Art\.?\s+\d+" | "Art. 5o" |
| `paragrafo` | Regex "[§\d]+" | "§ 1o" |
| `inciso` | Regex "[IVX]+" | "Inciso I" |
| `tipo` | Estrutura do chunk | "caput", "inciso" |
| `banca` | Regex "CEBRASPE\|FCC" | "CEBRASPE" |
| `ano` | Regex "\d{4}" | "2023" |

## Como Indexar Novos Documentos

### 1. Preparar o Documento

- Formato: DOCX (Microsoft Word)
- Estrutura: Usar estilos deHeading (Heading 1-9) para títulos
- Metadados: Incluir marcadores como `#Atenção:`, `#STF:`, `#Concurso:`

### 2. Adicionar ao Diretório

Coloque o arquivo DOCX em:
```
data/documents/novo_documento.docx
```

### 3. Indexar via CLI ou Discord

```bash
# Via CLI
uv run botsalinha ingest data/documents/novo_documento.docx --name "Nome do Documento"

# Via Discord (admin) — reindexar tudo
!reindexar
```

### 4. Verificar

```
!fontes
```

## Estrutura de Código

```
src/rag/
├── __init__.py
├── models.py                    # Pydantic schemas (Document, Chunk)
├── parser/
│   ├── docx_parser.py          # Parser de DOCX
│   ├── chunker.py              # Extrator de chunks
│   └── __init__.py
├── services/
│   ├── embedding_service.py    # OpenAI text-embedding-3-small
│   ├── ingestion_service.py    # Pipeline de ingestão
│   └── query_service.py        # Busca semântica
├── storage/
│   └── vector_store.py         # SQLite + busca vetorial
└── utils/
    └── metadata_extractor.py   # Extração de metadados
```

## Integração com AgentWrapper

O `AgentWrapper` integra RAG automaticamente quando habilitado:

```python
# src/core/agent.py
response, rag_context = await self.agent.generate_response_with_rag(
    prompt=message.content,
    conversation_id=conversation.id,
    user_id=str(user_id),
    guild_id=str(guild_id),
)

# rag_context contém:
# - chunks_usados: Lista de chunks
# - similaridades: Scores de similaridade
# - confianca: Nível de confiança
# - fontes: Lista de citações
```

## Formato de Resposta

### Alta Confiança

```
✅ [ALTA CONFIANÇA]

Conforme a Constituição Federal de 1988, todos são iguais
perante a lei, sem distinção de qualquer natureza...

📎 CF/88, Art. 5, caput
```

### Baixa Confiança

```
❌ [BAIXA CONFIANÇA]

Encontrei informações limitadas sobre este tema na base de documentos.
A resposta abaixo pode não ser completa ou precisa.

[Resposta parcial...]
```

### SEM RAG

```
ℹ️ [SEM RAG]

Não encontrei informações específicas sobre este tema na base de
documentos (Constituição Federal e Lei 8.112/90).

Posso oferecer uma resposta baseada em conhecimento geral, mas recomendo
verificar em fontes oficiais atualizadas.

[Resposta genérica...]
```

## Logs Estruturados

Eventos de log RAG disponíveis em `src/utils/log_events.py`:

```python
LogEvents.RAG_INGESTAO_INICIADA       # Início da ingestão
LogEvents.RAG_INGESTAO_CONCLUIDA       # Fim da ingestão
LogEvents.RAG_BUSCA_INICIADA           # Início da busca
LogEvents.RAG_BUSCA_CONCLUIDA          # Fim da busca
LogEvents.RAG_CHUNKS_RETORNADOS        # Chunks encontrados
LogEvents.RAG_CONFIDENCE_CALCULADA     # Confiança calculada
LogEvents.RAG_REINDEXACAO_INICIADA     # Início da reindexação
LogEvents.RAG_REINDEXACAO_CONCLUIDA    # Fim da reindexação
```

## Testes

### Rodar Testes RAG

```bash
# Todos os testes RAG
uv run pytest tests/ -k "rag" -v

# Apenas unitários
uv run pytest tests/unit/rag/ -v

# Apenas E2E
uv run pytest tests/e2e/test_rag_*.py -v

# Com coverage
uv run pytest tests/ -k "rag" --cov=src/rag --cov-report=html
```

### Testes de Recall

```bash
# Testa Recall@5 com 20 perguntas jurídicas
uv run pytest tests/integration/rag/test_recall.py -v
```

## Troubleshooting

### RAG Não Retorna Resultados

**Problema:** Consultas retornam SEM_RAG ou BAIXA confiança

**Soluções:**
1. Verificar se documentos estão indexados: `!fontes`
2. Reindexar: `!reindexar`
3. Verificar `RAG_MIN_SIMILARITY` (muito alto?)
4. Verificar se OPENAI_API_KEY está configurada

### Erro de Ingestão

**Problema:** Documentos não são indexados

**Soluções:**
1. Verificar formato do documento (deve ser DOCX)
2. Verificar estrutura (usar Heading styles)
3. Verificar logs: `tail logs/botsalinha.log | grep rag_ingestion`
4. Testar parser isoladamente

### Latência Alta

**Problema:** Respostas demoram > 2 segundos

**Soluções:**
1. Reduzir `RAG_TOP_K` (padrão: 5)
2. Verificar latência da API OpenAI
3. Considerar cache de embeddings

## Custos

### Embeddings

| Operação | Tokens | Custo USD |
|----------|--------|-----------|
| CF/88 (ingestão) | ~150K | $0.003 |
| Lei 8.112 (ingestão) | ~30K | $0.0006 |
| Query (pergunta) | ~50 | $0.00001 |
| **Total (one-time)** | ~180K | **$0.004** |

### Operacional

| Operação | Por Query | 1000 queries | 10K queries |
|----------|-----------|--------------|-------------|
| RAG (embedding + LLM) | ~$0.001 | ~$0.15 | ~$1.50 |

## Referências

- [Schema Técnico Completo do RAG](../rag_schema.md)
- [Modelos ORM RAG](../../src/models/rag_models.py)
- [Configurações RAG](../../src/config/settings.py)
- [Decisões Arquiteturais](../plans/RAG/decisoes_arquiteturais.md)
