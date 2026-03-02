# Schema RAG — BotSalinha

Referência técnica completa do sistema de Retrieval-Augmented Generation (RAG).

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Schema do Banco de Dados](#2-schema-do-banco-de-dados)
3. [Modelos Pydantic](#3-modelos-pydantic)
4. [Serviços](#4-serviços)
5. [Pipeline de Ingestão](#5-pipeline-de-ingestão)
6. [Pipeline de Consulta](#6-pipeline-de-consulta)
7. [Embeddings](#7-embeddings)
8. [Configuração](#8-configuração)
9. [Thresholds e Limites](#9-thresholds-e-limites)
10. [Erros e Exceções](#10-erros-e-exceções)

---

## 1. Visão Geral

O RAG do BotSalinha indexa documentos jurídicos (`.docx`) em fragmentos de texto
(_chunks_) com embeddings vetoriais, e usa busca semântica por similaridade cosseno
para enriquecer as respostas do agente com referências reais às leis e jurisprudência.

```
Arquivo .docx
    ↓  DOCXParser
Parágrafos estruturados
    ↓  ChunkExtractor
Chunks com metadata (art., inciso, §, marcadores…)
    ↓  EmbeddingService (OpenAI text-embedding-3-small)
Vetores 1536-dim
    ↓  SQLite (LargeBinary)
VectorStore
    ↑  QueryService (busca cosseno)
Pergunta do usuário → RAGContext → Prompt aumentado → Resposta com fontes
```

---

## 2. Schema do Banco de Dados

### 2.1 Tabela `rag_documents`

```sql
CREATE TABLE rag_documents (
    id           INTEGER  PRIMARY KEY AUTOINCREMENT,
    nome         VARCHAR(255) NOT NULL,
    arquivo_origem VARCHAR(500) NOT NULL,
    chunk_count  INTEGER  NOT NULL DEFAULT 0,
    token_count  INTEGER  NOT NULL DEFAULT 0,
    file_hash    VARCHAR(64)  DEFAULT NULL,       -- SHA-256 hex (64 chars)
    created_at   DATETIME NOT NULL
);

CREATE INDEX ix_rag_documents_nome      ON rag_documents (nome);
CREATE INDEX ix_rag_documents_file_hash ON rag_documents (file_hash);

-- UNIQUE permite múltiplos NULL (linhas legadas sem hash)
CREATE UNIQUE INDEX uq_rag_documents_file_hash ON rag_documents (file_hash)
    WHERE file_hash IS NOT NULL;
```

#### Colunas

| Coluna           | Tipo         | Nulável | Padrão | Descrição                                         |
| ---------------- | ------------ | ------- | ------ | ------------------------------------------------- |
| `id`             | INTEGER      | NÃO     | auto   | Chave primária                                    |
| `nome`           | VARCHAR(255) | NÃO     | —      | Nome legível do documento (ex.: `"CF/88"`)        |
| `arquivo_origem` | VARCHAR(500) | NÃO     | —      | Caminho do arquivo de origem                      |
| `chunk_count`    | INTEGER      | NÃO     | 0      | Número de chunks indexados                        |
| `token_count`    | INTEGER      | NÃO     | 0      | Total de tokens estimados                         |
| `file_hash`      | VARCHAR(64)  | SIM     | NULL   | SHA-256 hex do arquivo (deduplicação)             |
| `created_at`     | DATETIME     | NÃO     | —      | Timestamp UTC da criação                          |

---

### 2.2 Tabela `rag_chunks`

```sql
CREATE TABLE rag_chunks (
    id           VARCHAR(255) PRIMARY KEY,     -- ex.: "CF_88-0001"
    documento_id INTEGER  NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    texto        TEXT     NOT NULL,
    metadados    TEXT     NOT NULL,            -- JSON serializado de ChunkMetadata
    token_count  INTEGER  NOT NULL,
    embedding    BLOB     DEFAULT NULL,        -- float32[1536] serializado
    created_at   DATETIME NOT NULL
);

CREATE INDEX ix_rag_chunks_documento_id ON rag_chunks (documento_id);
```

#### Colunas

| Coluna         | Tipo        | Nulável | Padrão | Descrição                                          |
| -------------- | ----------- | ------- | ------ | -------------------------------------------------- |
| `id`           | VARCHAR(255)| NÃO     | —      | PK no formato `"<nome_doc>-<seq:04d>"`             |
| `documento_id` | INTEGER     | NÃO     | —      | FK → `rag_documents.id` (CASCADE DELETE)           |
| `texto`        | TEXT        | NÃO     | —      | Conteúdo textual do chunk                          |
| `metadados`    | TEXT        | NÃO     | —      | JSON de `ChunkMetadata` (artigo, marcadores, etc.) |
| `token_count`  | INTEGER     | NÃO     | —      | Tokens estimados (`len(texto) / 4`)                |
| `embedding`    | BLOB        | SIM     | NULL   | 1536 × float32 = 6.144 bytes                       |
| `created_at`   | DATETIME    | NÃO     | —      | Timestamp UTC da criação                           |

---

### 2.3 Diagrama Entidade-Relacionamento

```
┌─────────────────────────────────────┐
│            rag_documents             │
├─────────────────────────────────────┤
│ PK  id           INTEGER            │
│     nome         VARCHAR(255)       │
│     arquivo_origem VARCHAR(500)     │
│     chunk_count  INTEGER            │
│     token_count  INTEGER            │
│     file_hash    VARCHAR(64) UNIQUE │  ← SHA-256, NULL = legado
│     created_at   DATETIME           │
└───────────────────┬─────────────────┘
                    │ 1
                    │
                    │ N
┌───────────────────▼─────────────────┐
│              rag_chunks              │
├─────────────────────────────────────┤
│ PK  id           VARCHAR(255)       │  ← "CF_88-0001"
│ FK  documento_id INTEGER            │  → rag_documents.id
│     texto        TEXT               │
│     metadados    TEXT (JSON)        │  ← ChunkMetadata serializado
│     token_count  INTEGER            │
│     embedding    BLOB               │  ← float32[1536]
│     created_at   DATETIME           │
└─────────────────────────────────────┘
```

### 2.4 Migrações Alembic

| Revisão                                            | Descrição                                          |
| -------------------------------------------------- | -------------------------------------------------- |
| `20260228_0236_…_add_rag_documents_and_chunks`     | Cria as tabelas `rag_documents` e `rag_chunks`     |
| `20260228_1000_add_embedding_column_to_rag_chunks` | Adiciona coluna `embedding BLOB` em `rag_chunks`   |
| `20260228_1100_add_file_hash_to_rag_documents`     | Adiciona `file_hash VARCHAR(64)` com UNIQUE e índice |

---

## 3. Modelos Pydantic

Todos em `src/rag/models.py`.

### 3.1 `ChunkMetadata`

Metadados estruturais e semânticos de um chunk de texto jurídico.

```python
class ChunkMetadata(BaseModel):
    # Localização no documento
    documento:    str           # ex.: "CF/88"      — obrigatório
    titulo:       str | None    # Título de seção
    capitulo:     str | None    # Capítulo
    secao:        str | None    # Seção
    artigo:       str | None    # ex.: "5"
    paragrafo:    str | None    # ex.: "único" ou "1"
    inciso:       str | None    # ex.: "I", "II", "III"
    tipo:         str | None    # "caput" | "inciso" | "heading" | "content"

    # Marcadores de atenção (extraídos por regex)
    marca_atencao:    bool = False   # Texto marcado com #Atenção:
    marca_stf:        bool = False   # Menção ao STF / Supremo Tribunal Federal
    marca_stj:        bool = False   # Menção ao STJ / Superior Tribunal de Justiça
    marca_concurso:   bool = False   # Relevante para concursos públicos
    marca_crime:      bool = False   # Direito penal — tipificação
    marca_pena:       bool = False   # Pena / sanção aplicável
    marca_hediondo:   bool = False   # Crimes hediondos (Lei 8.072)
    marca_acao_penal: bool = False   # Ação penal pública ou privada
    marca_militar:    bool = False   # Código Penal Militar / legislação militar

    # Informações de prova/questão
    banca: str | None    # ex.: "CEBRASPE", "FCC", "VUNESP", "FGV"
    ano:   str | None    # ex.: "2024"
```

### 3.2 `Chunk`

```python
class Chunk(BaseModel):
    chunk_id:          str           # ex.: "CF_88-0001"
    documento_id:      int           # FK → DocumentORM.id
    texto:             str           # Conteúdo textual
    metadados:         ChunkMetadata
    token_count:       int           # ≥ 0
    posicao_documento: float         # 0.0 (início) a 1.0 (fim)
```

### 3.3 `Document`

```python
class Document(BaseModel):
    id:             int
    nome:           str
    arquivo_origem: str
    chunk_count:    int       # ≥ 0
    token_count:    int       # ≥ 0
    file_hash:      str | None  # SHA-256 hex ou None (legado)
```

### 3.4 `ConfiancaLevel`

```python
class ConfiancaLevel(StrEnum):
    ALTA   = "alta"     # avg_similarity ≥ 0.85
    MEDIA  = "media"    # avg_similarity ≥ 0.70
    BAIXA  = "baixa"    # avg_similarity ≥ 0.60
    SEM_RAG = "sem_rag" # Nenhum resultado ou abaixo de 0.60
```

### 3.5 `RAGContext`

Resultado da busca semântica — injetado no prompt do agente.

```python
class RAGContext(BaseModel):
    chunks_usados:  list[Chunk]   # Chunks recuperados
    similaridades:  list[float]   # Score por chunk (mesma ordem)
    confianca:      ConfiancaLevel
    fontes:         list[str]     # Citações formatadas

    # Invariante: len(chunks_usados) == len(similaridades)
```

**Exemplo de `fontes`:**

```python
[
    "CF/88, Art. 5, § 1, Inciso I, Título: Dos Direitos e Garantias Fundamentais",
    "CF/88, Art. 6, Capítulo: Dos Direitos Sociais",
]
```

---

## 4. Serviços

### 4.1 `EmbeddingService` — `src/rag/services/embedding_service.py`

Gera vetores via OpenAI `text-embedding-3-small` (1536 dimensões).

```
embed_text(text: str) → list[float]           # 1 requisição
embed_batch(texts: list[str]) → list[list[float]]   # Batching automático
```

- Texto vazio → vetor zero `[0.0] * 1536`
- Lotes > 200.000 tokens são divididos automaticamente
- Estimativa de tokens: `len(text) / 4`
- Retry automático (3 tentativas com backoff)

### 4.2 `IngestionService` — `src/rag/services/ingestion_service.py`

Orquestra o pipeline completo de ingestão.

```
ingest_document(file_path, document_name) → Document
reindex(documents_dir, pattern="*.docx")  → dict[str, int | float]
```

**`reindex` retorna:**

```python
{
    "chunks_count":      int,
    "documents_count":   int,
    "duration_seconds":  float,
    "success":           bool,
}
```

### 4.3 `QueryService` — `src/rag/services/query_service.py`

Busca semântica e construção do contexto para o agente.

```
query(query_text, top_k?, min_similarity?, documento_id?, filters?) → RAGContext
query_by_tipo(query_text, tipo, top_k?)                             → RAGContext
should_augment_prompt(context: RAGContext)                          → bool
get_augmentation_text(context: RAGContext)                          → str
```

**Valores de `tipo` em `query_by_tipo`:**

| Valor           | Filtro aplicado                      |
| --------------- | ------------------------------------ |
| `"artigo"`      | `tipo = "caput"` ou `"inciso"`       |
| `"jurisprudencia"` | `marca_stf = true` ou `marca_stj = true` |
| `"questao"`     | `marca_concurso = true`              |
| `"nota"`        | `tipo = "content"` sem marcadores    |
| `"todos"`       | Sem filtro                           |

### 4.4 `VectorStore` — `src/rag/storage/vector_store.py`

Armazena e recupera embeddings diretamente no SQLite.

```
search(query_embedding, limit?, min_similarity?, documento_id?, filters?) → list[(Chunk, float)]
add_embeddings(chunks_with_embeddings)                                     → None
get_chunk_by_id(chunk_id)                                                  → Chunk | None
count_chunks(documento_id?)                                                → int
```

**Algoritmo de busca:**

1. Carrega todos os `ChunkORM` com `embedding IS NOT NULL`
2. Aplica filtros de `documento_id` e `metadados` (via `JSON_EXTRACT`)
3. Calcula similaridade cosseno em Python para cada candidato
4. Filtra por `min_similarity`
5. Ordena por score desc, aplica `limit`

### 4.5 `ConfiancaCalculator` — `src/rag/utils/confianca_calculator.py`

```
calculate(chunks_with_scores)              → ConfiancaLevel
calculate_from_context(context)            → ConfiancaLevel
get_confidence_message(level)              → str   # com emoji
should_use_rag(level)                      → bool
format_sources(chunks_with_scores)         → list[str]
```

**Mensagens por nível:**

| Nível     | Mensagem                                                                 |
| --------- | ------------------------------------------------------------------------ |
| `ALTA`    | `✅ [ALTA CONFIANÇA] Resposta baseada em documentos jurídicos verificados` |
| `MEDIA`   | `⚠️ [MÉDIA CONFIANÇA] Resposta parcialmente baseada em documentos`        |
| `BAIXA`   | `❌ [BAIXA CONFIANÇA] Informações limitadas encontradas`                  |
| `SEM_RAG` | `ℹ️ [SEM RAG] Não encontrei informações específicas nos documentos`       |

---

## 5. Pipeline de Ingestão

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PIPELINE DE INGESTÃO                                │
└─────────────────────────────────────────────────────────────────────────┘

[0] DEDUPLICAÇÃO
    • Calcular SHA-256 do arquivo (blocos de 64 KiB)
    • SELECT DocumentORM WHERE file_hash = <hash>
    • Se encontrado → DuplicateDocumentError(existing_id, existing_nome, file_hash)

[1] PARSE
    • DOCXParser.parse() → list[dict]
    • Extrai: text, style, is_heading (nível 1-9), is_bold, is_italic
    • Normaliza encoding UTF-8 / mojibake latin-1

[2] CRIAR DOCUMENTO
    • INSERT DocumentORM (nome, arquivo_origem, file_hash, created_at)
    • FLUSH para obter ID autogerado

[3] CHUNKING
    • ChunkExtractor.extract_chunks()
    • Algoritmo greedy bin-packing:
      - Acumula parágrafos até max_tokens (500)
      - Quebra em headings nível 1-2 ou ao atingir limite
      - Adiciona overlap de 50 tokens do chunk anterior
    • Preserva contexto hierárquico: titulo → capitulo → secao
    • MetadataExtractor.extract() por chunk (regex para art., §, incisos, marcadores)
    • chunk_id = "{nome_sanitizado}-{seq:04d}"
    • posicao_documento = (posição do chunk) / (total de parágrafos)

[4] EMBEDDINGS
    • EmbeddingService.embed_batch([chunk.texto for chunk in chunks])
    • Um único batch por documento (dividido se > 200.000 tokens)
    • Retorna list[list[float]] — 1536 floats por chunk

[5] CRIAR CHUNKS
    • Para cada (chunk, embedding):
      - serialize_embedding(embedding) → bytes (float32, 6.144 bytes)
      - INSERT ChunkORM (id, documento_id, texto, metadados JSON, token_count, embedding)

[6] ATUALIZAR ESTATÍSTICAS
    • UPDATE DocumentORM SET chunk_count = N, token_count = sum(tokens)

[7] COMMIT
    • session.commit()

[8] RETORNAR
    • Document Pydantic com file_hash preenchido
```

---

## 6. Pipeline de Consulta

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PIPELINE DE CONSULTA                                │
└─────────────────────────────────────────────────────────────────────────┘

[1] EMBEDDING DA QUERY
    • EmbeddingService.embed_text(query_text)
    • → list[float] de 1536 dimensões

[2] BUSCA VETORIAL
    • VectorStore.search(query_embedding, limit=top_k, min_similarity=0.6)
    • Carrega ChunkORMs com embedding IS NOT NULL
    • Aplica filtros opcionais (documento_id, tipo, marcadores)
    • cosine_similarity(query_vec, chunk_vec) para cada candidato
    • Filtra scores < min_similarity
    • Ordena desc, retorna top_k

[3] CÁLCULO DE CONFIANÇA
    • avg_similarity = mean([score for _, score in resultados])
    • ALTA   : avg ≥ 0.85
    • MEDIA  : avg ≥ 0.70
    • BAIXA  : avg ≥ 0.60
    • SEM_RAG: avg < 0.60 ou nenhum resultado

[4] FORMATAR FONTES
    • ConfiancaCalculator.format_sources(chunks_with_scores)
    • Gera strings: "CF/88, Art. 5, § 1, Inciso II, Título: Fundamentais"

[5] MONTAR RAGContext
    • chunks_usados, similaridades, confianca, fontes

[6] AUMENTAR PROMPT (se confianca ≠ SEM_RAG)
    • QueryService.get_augmentation_text(context)
    • Formato injetado:
        [ALTA CONFIANÇA] Resposta baseada em documentos jurídicos verificados.

        === Contexto Jurídico Relevante ===
        📄 [Similaridade: 0.92] CF/88, Art. 5, caput
        "Todos são iguais perante a lei, sem distinção de qualquer natureza..."

        ⚖️ [Similaridade: 0.87] CF/88, Art. 5, Inciso I
        "homens e mulheres são iguais em direitos e obrigações..."

        Instruções: Use apenas as informações acima para fundamentar sua resposta.
        Cite as fontes fornecidas com precisão.
```

---

## 7. Embeddings

### 7.1 Modelo

| Atributo         | Valor                       |
| ---------------- | --------------------------- |
| Provedor         | OpenAI                      |
| Modelo           | `text-embedding-3-small`    |
| Dimensões        | 1536                        |
| Tipo             | `float32`                   |
| Tamanho em bytes | 1536 × 4 = **6.144 bytes**  |
| Similaridade     | Cosseno                     |

### 7.2 Serialização

```python
# float list → bytes (armazenamento SQLite BLOB)
def serialize_embedding(embedding: list[float]) -> bytes:
    return np.array(embedding, dtype=np.float32).tobytes()

# bytes → float list (recuperação)
def deserialize_embedding(blob: bytes) -> list[float]:
    return np.frombuffer(blob, dtype=np.float32).tolist()
```

### 7.3 Similaridade Cosseno

```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
    # Range: [-1.0, 1.0] — vetores idênticos = 1.0
```

---

## 8. Configuração

Seção `rag` em `src/config/settings.py` (lida via `YAML` + `Pydantic Settings`):

```python
class RAGConfig(BaseSettings):
    enabled:             bool  = True
    top_k:               int   = 5          # 1–20
    min_similarity:      float = 0.6        # 0.0–1.0
    max_context_tokens:  int   = 2000       # 100–8000
    documents_path:      str   = "data/documents"
    embedding_model:     str   = "text-embedding-3-small"
    confidence_threshold: float = 0.70      # threshold para nível ALTA
```

Variáveis de ambiente correspondentes (prefixo `RAG__`):

```env
RAG__ENABLED=true
RAG__TOP_K=5
RAG__MIN_SIMILARITY=0.6
RAG__MAX_CONTEXT_TOKENS=2000
RAG__DOCUMENTS_PATH=data/documents
RAG__EMBEDDING_MODEL=text-embedding-3-small
RAG__CONFIDENCE_THRESHOLD=0.70
```

---

## 9. Thresholds e Limites

| Parâmetro                       | Valor           | Fonte                            |
| ------------------------------- | --------------- | -------------------------------- |
| Dimensão do embedding           | **1536**        | `EmbeddingService.EMBEDDING_DIM` |
| Max tokens por chunk            | **500**         | `ChunkExtractor` (configurável)  |
| Overlap entre chunks            | **50 tokens**   | `ChunkExtractor`                 |
| Tamanho mínimo do chunk         | **100 tokens**  | `ChunkExtractor`                 |
| Top K resultados (padrão)       | **5**           | `RAGConfig.top_k`                |
| Similaridade mínima (padrão)    | **0.60**        | `RAGConfig.min_similarity`       |
| Threshold ALTA confiança        | **≥ 0.85**      | `ConfiancaCalculator`            |
| Threshold MÉDIA confiança       | **≥ 0.70**      | `ConfiancaCalculator`            |
| Threshold BAIXA confiança       | **≥ 0.60**      | `ConfiancaCalculator`            |
| Max tokens por batch OpenAI     | **200.000**     | `EmbeddingService` (seguro)      |
| Limite real da API OpenAI       | 300.000         | Referência interna               |
| Estimativa tokens (português)   | **4 chars/tok** | `EmbeddingService`, `ChunkExtractor` |
| Max contexto injetado no prompt | **2.000 tokens**| `RAGConfig.max_context_tokens`   |
| Backups automáticos mantidos    | **5**           | `DatabaseGuard._MAX_BACKUPS`     |
| Tamanho bloco hash SHA-256      | 64 KiB          | `IngestionService._compute_file_hash` |

---

## 10. Erros e Exceções

### Hierarquia

```
BotSalinhaError
└── IngestionError
    └── DuplicateDocumentError
```

### `DuplicateDocumentError`

Lançada quando um arquivo com o mesmo SHA-256 já está indexado.

```python
class DuplicateDocumentError(IngestionError):
    existing_id:   int   # ID do DocumentORM existente
    existing_nome: str   # Nome do documento existente
    file_hash:     str   # SHA-256 em hex (64 chars)

# Mensagem automática:
# "Arquivo já indexado como 'CF/88' (id=1). Hash: e3b0c4…
#  Para substituir, use !reindexar."
```

**Tratamento recomendado:**

```python
try:
    doc = await ingestion_service.ingest_document(path, nome)
except DuplicateDocumentError as e:
    # Informa o usuário sem re-processar
    await ctx.send(
        f"⚠️ **Arquivo já indexado** como `{e.existing_nome}` (id={e.existing_id}).\n"
        f"Use `!reindexar` para reconstruir o índice completo."
    )
```

### Outras exceções relevantes

| Exceção            | Quando                                               |
| ------------------ | ---------------------------------------------------- |
| `IngestionError`   | Falha em qualquer etapa do pipeline (parse, embed…)  |
| `APIError`         | Falha na API da OpenAI (embedding ou timeout)        |
| `ValidationError`  | Embedding com dimensão ≠ 1536 (detectado no ChunkORM)|

---

## Referências Cruzadas

| Componente              | Arquivo                                        |
| ----------------------- | ---------------------------------------------- |
| ORM `DocumentORM`       | `src/models/rag_models.py`                     |
| ORM `ChunkORM`          | `src/models/rag_models.py`                     |
| Pydantic `RAGContext`   | `src/rag/models.py`                            |
| Pydantic `ChunkMetadata`| `src/rag/models.py`                            |
| `IngestionService`      | `src/rag/services/ingestion_service.py`        |
| `QueryService`          | `src/rag/services/query_service.py`            |
| `EmbeddingService`      | `src/rag/services/embedding_service.py`        |
| `VectorStore`           | `src/rag/storage/vector_store.py`              |
| `ConfiancaCalculator`   | `src/rag/utils/confianca_calculator.py`        |
| `MetadataExtractor`     | `src/rag/utils/metadata_extractor.py`          |
| `ChunkExtractor`        | `src/rag/parser/chunker.py`                    |
| `DOCXParser`            | `src/rag/parser/docx_parser.py`                |
| `RAGConfig`             | `src/config/settings.py`                       |
| `DatabaseGuard`         | `src/storage/db_guard.py`                      |
| Migrações RAG           | `migrations/versions/20260228_*`               |
