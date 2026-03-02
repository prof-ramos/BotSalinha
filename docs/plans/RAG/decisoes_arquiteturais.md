# Decisões Arquiteturais - RAG Jurídico BotSalinha

**Data:** 2026-02-28
**Status:** ✅ Todos os milestones concluídos — RAG em produção

## Índice

1. [Stack Tecnológico](#stack-tecnológico)
2. [Decisões de Design](#decisões-de-design)
3. [Trade-offs Analisados](#trade-offs-analisados)
4. [Problemas Resolvidos](#problemas-resolvidos)
5. [Decisões Pendentes](#decisões-pendentes)

---

## Stack Tecnológico

### Escolhas Confirmadas

| Componente | Tecnologia | Justificativa |
|-----------|------------|---------------|
| **Vector Store** | SQLite + índice customizado | Menos dependências, controle total, SQLite já em uso |
| **Embeddings** | OpenAI text-embedding-3-small | 1536 dim, $0.02/1M tokens, alta qualidade para pt-BR |
| **ORM** | SQLAlchemy 2.0 Async | Já em uso no projeto, suporte async nativo |
| **Migrações** | Alembic | Padrão de mercado para SQLAlchemy |
| **Parsing DOCX** | python-docx | Preserva formatação e estrutura hierárquica |
| **Chunking** | Customizado (hierárquico) | Preserva estrutura jurídica (artigo, parágrafo, inciso) |
| **AI Orchestration** | Agno Framework | Já em uso no projeto |
| **Validação** | Pydantic v2 | Já em uso, type hints, validação automática |

### Tecnologias Consideradas e Rejeitadas

| Tecnologia | Motivo da Rejeição |
|------------|-------------------|
| **ChromaDB** | Dependência adicional, SQLite suficiente para volume atual |
| **LangChain** | Agno já fornece orquestração, evita overhead |
| **sentence-transformers** | Requer GPU para bom desempenho, OpenAI API mais simples |
| **LlamaIndex** | Muito complexo para caso de uso atual |
| **pgvector** | Requer PostgreSQL, SQLite já em uso |

---

## Decisões de Design

### 1. Estrutura de Metadados Jurídicos

**Decisão:** Metadados hierárquicos com campos especializados

```python
class ChunkMetadata(BaseModel):
    documento: str           # Nome do documento fonte
    titulo: str | None       # Título principal (Livro, Título)
    capitulo: str | None     # Capítulo
    secao: str | None        # Seção
    artigo: str | None       # Número do artigo (ex: "37")
    paragrafo: str | None    # Parágrafo único (ex: "1")
    inciso: str | None       # Inciso romano (ex: "I", "II")
    marca_atencao: bool      # #Atenção: no texto
    marca_stf: bool          # #STF: no texto
    marca_stj: bool          # #STJ: no texto
    banca: str | None        # Banca de concurso (ex: "CEBRASPE")
    ano: str | None          # Ano da questão
```

**Justificativa:**
- Preserva estrutura hierárquica de documentos jurídicos
- Permite navegação precisa (citar artigo específico)
- Suporta questões de concurso com metadados de banca/ano

---

### 2. Estratégia de Chunking

**Decisão:** Chunking hierárquico com overlap de 50 tokens

```python
CHUNK_CONFIG = {
    "max_tokens": 500,           # Tamanho máximo do chunk
    "overlap_tokens": 50,        # Overlap para contexto
    "respect_boundaries": True,  # Respeita limites de artigos
    "min_chunk_size": 100,       # Tamanho mínimo
    "metadata_max_depth": 3,     # Profundidade de metadados a preservar
}
```

**Justificativa:**
- 500 tokens = bom balanço contexto/precisão
- Overlap de 50 tokens mantém coesão entre chunks
- Respeitar limites de artigos evita cortar citações legais
- Min 100 tokens evita chunks fragmentados

**Trade-off:**
- ✅ Preserva estrutura jurídica
- ❌ Mais complexo que chunking por tamanho fixo

---

### 3. Batching Dinâmico para Embeddings

**Decisão:** Limite de 200K tokens por request (margem para 300K máximo)

```python
MAX_TOKENS_PER_REQUEST = 200000  # OpenAI max: 300K

if total_tokens <= MAX_TOKENS_PER_REQUEST:
    # Single request
else:
    # Process in batches, tracking tokens per batch
```

**Justificativa:**
- OpenAI text-embedding-3-small tem limite de 300K tokens
- Usar 200K como margem de segurança para erros de estimativa
- Estimativa `len(text) // 4` pode ser imprecisa
- Documentos grandes (CF/88 com 312K tokens) falharam sem batching

**Problema Resolvido:**
- CF/88 (312K tokens) falhou com "max_tokens_per_request"
- Solução: Batching dinâmico divide em múltiplas requests

---

### 4. Configuração com Pydantic-Settings

**Decisão:** Nested configs com `env_nested_delimiter="__"`

```python
class RAGConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    enabled: bool = True
    top_k: int = 5
    min_similarity: float = 0.6
    embedding_model: str = "text-embedding-3-small"
```

**Variáveis de ambiente:**
```bash
RAG__ENABLED=true
RAG__TOP_K=5
RAG__EMBEDDING_MODEL=text-embedding-3-small
```

**Problema Resolvido:**
- Nested classes não herdavam `env_file` automaticamente
- Solução: Adicionar `env_file=".env"` explicitamente

---

### 5. Eventos de Log em pt-BR

**Decisão:** Todos os nomes de eventos em português

```python
LogEvents = {
    "rag_documento_indexado": "Documento indexado com sucesso",
    "rag_chunk_criado": "Chunk criado",
    "rag_embedding_criado": "Embedding gerado",
    "rag_busca_executada": "Busca vetorial executada",
    # ...
}
```

**Justificativa:**
- Consistência com restante do projeto
- Facilita debugging para time brasileiro
- Ferramentas de log (Datadog, CloudWatch) suportam unicode

---

## Trade-offs Analisados

### 1. SQLite vs ChromaDB

| Aspecto | SQLite | ChromaDB |
|---------|--------|----------|
| Dependências | 0 (já em uso) | +1 |
| Setup | Nenhum | Docker/service |
| Performance | ~10ms/busca | ~5ms/busca |
| Escalabilidade | até 1M chunks | até 100M chunks |
| Flexibilidade | Total | Limitada |

**Decisão:** SQLite
**Justificativa:**
- Volume atual < 100K chunks
- Zero dependências adicionais
- Controle total sobre implementação
- Fácil migrar para ChromaDB se necessário

---

### 2. OpenAI API vs Local Embeddings

| Aspecto | OpenAI API | Local (sentence-transformers) |
|---------|------------|-------------------------------|
| Custo | $0.02/1M tokens | Grátis |
| Qualidade pt-BR | Alta | Média |
| Latência | ~100ms | ~500ms (CPU) |
| Setup | API key | Modelo 500MB+ |
| GPU | Não necessária | Recomendada |

**Decisão:** OpenAI API
**Justificativa:**
- Qualidade superior para português jurídico
- Custo baixo ($0.60 por 1M chunks)
- Sem overhead de setup
- Latência aceitável

---

### 3. Chunking Hierárquico vs Tamanho Fixo

| Aspecto | Hierárquico | Tamanho Fixo |
|---------|-------------|--------------|
| Complexidade | Alta | Baixa |
| Preserva estrutura | ✅ Sim | ❌ Não |
| Overhead metadados | Alto | Baixo |
| Precisão citação | ✅ Alta | Baixa |

**Decisão:** Hierárquico
**Justificativa:**
- Caso de uso jurídico requer precisão
- Citar artigo específico é obrigatório
- Overhead aceitável para volume atual

---

## Problemas Resolvidos

### Problema 1: Alembic Async Driver

**Erro:** `The asyncio extension requires an async driver`

**Causa:** `alembic revision --autogenerate` não suporta async SQLAlchemy

**Solução:**
```bash
# Criar migration manualmente
alembic revision -m "add_rag_tables"

# Escrever upgrade/downgrade manualmente
def upgrade():
    op.create_table("rag_documents", ...)
    op.create_table("rag_chunks", ...)
```

---

### Problema 2: API Key Não Lida do .env

**Erro:** `settings.openai.api_key` sempre retorna `None`

**Causa:** Nested Pydantic classes com `default_factory` não herdam `env_file`

**Solução 1 (configuração):**
```python
class OpenAIConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",  # Adicionar explicitamente
        env_file_encoding="utf-8",
    )
```

**Solução 2 (workaround CLI):**
```python
api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI__API__KEY")
if not api_key:
    api_key = settings.get_openai_api_key()
```

---

### Problema 3: Limite de Tokens OpenAI Excedido

**Erro:** `max_tokens_per_request exceeded` (CF/88 com 312K tokens)

**Causa:** Documento excede limite de 300K tokens da OpenAI

**Solução:** Batching dinâmico em `EmbeddingService.embed_batch()`
```python
MAX_TOKENS_PER_REQUEST = 200000  # Margem de segurança

if total_tokens <= MAX_TOKENS_PER_REQUEST:
    # Single request
else:
    # Process in batches, tracking tokens per batch
    for idx, text in texts:
        if current_tokens + text_tokens > MAX_TOKENS_PER_REQUEST:
            # Process current batch, start new one
```

---

## Decisões Resolvidas (Pós-MVP)

| Decisão | Escolha Final |
|---------|---------------|
| **Algoritmo de similaridade** | Cosine similarity em Python (numpy) |
| **Re-ranking** | Sem re-ranking (pós-MVP: re-ranking jurídico) |
| **Cache de embeddings** | SQLite persiste embeddings; sem cache adicional |
| **Atualização de documentos** | `!reindexar` deleta e reingesta; deduplicação SHA-256 evita reprocessamento desnecessário |

---

## Métricas de Sucesso

### Milestone 0 e 1: ✅ Completados

- ✅ 134 testes passando
- ✅ 2 documentos indexados (775 chunks, 345K tokens)
- ✅ Ingestão CF/88 (687 chunks, 303K tokens) com batching
- ✅ Zero erros de encoding

### MVP Completo ✅

- ✅ Busca com similaridade > 0.7 retorna resultados relevantes
- ✅ Latência de busca < 100ms
- ✅ Comandos `!buscar`, `!fontes`, `!reindexar` em produção
- ✅ Deduplicação SHA-256
- ✅ Todos os milestones (M0–M4) concluídos

---

## Referências

- [Plano Principal](../../../.omc/plans/rag-feature-implementation.md)
- [Melhorias Sugeridas](./melhorias_sugeridas.md)
- [CLAUDE.md](../../../CLAUDE.md)
