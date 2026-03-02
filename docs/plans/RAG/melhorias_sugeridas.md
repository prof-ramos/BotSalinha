# Melhorias Sugeridas - RAG Jurídico BotSalinha

**Data:** 2026-02-28
**Fonte:** Análise de implementação de referência

## Visão Geral

Este documento registra melhorias e descobertas obtidas a partir da análise de uma implementação de referência de RAG jurídico para Discord, comparando com a implementação atual do BotSalinha.

## Decisões Arquiteturais: BotSalinha vs Referência

| Aspecto | BotSalinha (Atual) | Referência Externa | Justificativa |
|---------|-------------------|-------------------|---------------|
| **Vector Store** | SQLite + índice vetorial customizado | ChromaDB | Menos dependências, controle total, SQLite já em uso |
| **Embeddings** | OpenAI text-embedding-3-small (API) | sentence-transformers (local) | Maior qualidade para português jurídico, $0.02/1M tokens |
| **Orquestração** | Agno Framework | LangChain | Agno já em uso no projeto |
| **Chunking** | Hierárquico (título→capítulo→seção→artigo) | Por tamanho fixo | Preserva estrutura jurídica |
| **Formatação** | Markdown simples | Prefixos visuais (emojis) | ✅ Melhoria sugerida abaixo |

---

## Melhorias Sugeridas

### 1. Normalização de Encoding ⚠️ **Alta Prioridade**

**Problema:** Documentos jurídicos brasileiros frequentemente usam encoding latin-1, causando caracteres corrompidos.

**Solução da Referência:**
```python
# normalizador.py
def normalize_encoding(text: str) -> str:
    """
    Normaliza encoding de documentos jurídicos brasileiros.
    Converte latin-1 → utf-8 e remove caracteres problemáticos.
    """
    # Substituições comuns de encoding latin-1 corrompido
    replacements = {
        "Ã§": "ç", "Ã£": "ã", "Ãµ": "õ", "Ã¡": "á", "Ã©": "é",
        "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã¢": "â", "Ãª": "ê",
        "Ã´": "ô", "Ã­": "í", "Ã ": "à", "Ã": "Á", "Ã‰": "É",
        "â€œ": '"', "â€": '"', "â€˜": "'", "â€™": "'",
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    return text
```

**Implementação Sugerida:**
- Adicionar `src/rag/utils/normalizer.py`
- Integrar no `DOCXParser.parse()` após leitura de cada parágrafo
- Adicionar testes para caracteres problemáticos comuns

---

### 2. Prefixos Visuais para Tipos de Chunk 📋

**Problema:** Chunks de diferentes tipos jurídicos ficam difíceis de distinguir visualmente.

**Solução da Referência:**
```python
CHUNK_PREFIXES = {
    "artigo": "⚖️",
    "jurisprudencia": "📜",
    "questao": "❓",
    "nota": "📝",
    "lei": "📋",
}

def format_chunk(chunk: Chunk) -> str:
    prefix = CHUNK_PREFIXES.get(chunk.tipo, "📄")
    return f"{prefix} {chunk.texto}"
```

**Implementação Sugerida:**
- Adicionar campo `tipo: str` em `ChunkMetadata`
- Implementar `formatador.py` com prefixos
- Usar na resposta do Discord para melhor UX

---

### 3. Filtragem por Tipo de Metadado 🔍

**Problema:** Usuários podem querer buscar apenas artigos, ou apenas jurisprudência.

**Solução da Referência:**
```python
# Slash command /buscar
@bot.command("/buscar")
async def buscar(
    ctx,
    query: str,
    tipo: Literal["artigo", "jurisprudencia", "questao", "nota", "todos"] = "todos"
):
    results = vector_store.search(query, tipo_filter=tipo)
```

**Implementação Sugerida:**
- Adicionar parâmetro `tipo` em `QueryService.query()`
- Mapear `ChunkMetadata` para tipos:
  - `artigo`: tem campo `artigo` preenchido
  - `jurisprudencia`: marcas `marca_stf` ou `marca_stj`
  - `questao`: tem campo `banca` preenchido
  - `nota`: texto curto (< 100 tokens)
- Comando Discord: `!buscar <query> [--tipo artigo|jurisprudencia|questao|nota]`

---

### 4. Comandos Discord Adicionais 💬

**Comando `/fontes`**
```python
@commands.command(name="fontes")
async def fontes(self, ctx):
    """Lista documentos indexados no RAG."""
    docs = await repository.list_documents()
    response = "**Fontes Jurídicas Indexadas:**\n\n"
    for doc in docs:
        response += f"📋 {doc.nome} ({doc.chunk_count} chunks)\n"
    await ctx.send(response)
```

**Comando `/limpar`** (já existe `!limpar` para conversas)
```python
@commands.command(name="reindexar")
async def reindexar(self, ctx, document_name: str):
    """Reindexa um documento do zero."""
    # Limpa chunks existentes
    # Reingesta documento
    await ctx.send(f"✅ Documento {document_name} reindexado.")
```

---

### 5. Categorização de Confiança 🎯

**Problema:** Usuários precisam saber o quão confiante é o RAG para a resposta.

**Solução da Referência:**
```python
def get_confidence_category(similarity: float) -> str:
    """Retorna categoria de confiança baseada em similaridade."""
    if similarity >= 0.85:
        return "ALTA"  # ✅
    elif similarity >= 0.70:
        return "MEDIA"  # ⚠️
    else:
        return "BAIXA"  # ❌
```

**Implementação Sugerida:**
- Já implementado em `ConfiancaLevel` enum (`ALTA`, `MEDIA`, `BAIXA`, `SEM_RAG`)
- Adicionar indicadores visuais na resposta Discord:
  - `ALTA` → ✅ Fontes confiáveis
  - `MEDIA` → ⚠️ Verifique as fontes
  - `BAIXA` → ❌ Baixa confiança nas fontes
  - `SEM_RAG` → ℹ️ Resposta sem base jurídica específica

---

## Lições Aprendidas

### Do Milestone 0 (Fundação)

✅ **Bem-sucedido:**
- Pydantic v2 com `env_nested_delimiter="__"` funciona bem
- SQLAlchemy 2.0 async ORM com `Mapped[]` annotations
- Migração Alembic manual quando `--autogenerate` falha

⚠️ **Problemas Resolvidos:**
1. **Nested classes Pydantic-settings** não herdam `env_file` automaticamente
   - Solução: Adicionar `env_file=".env"` explicitamente em cada classe aninhada

2. **API key não lida do .env** em nested configs
   - Solução: Workaround no CLI lendo `os.environ` diretamente

### Do Milestone 1 (Ingestão)

✅ **Bem-sucedido:**
- `python-docx` preserva estrutura hierárquica bem
- Regex para extração de metadados jurídicos funciona
- Dynamic batching resolve limite de 300K tokens da OpenAI

⚠️ **Problemas Resolvidos:**
1. **Limite de tokens OpenAI excedido**
   - Documento CF/88 com 312K tokens falhou
   - Solução: Implementar batching dinâmico em `EmbeddingService.embed_batch()`

2. **Estimativa de tokens imprecisa**
   - Solução: Usar `len(text) // 4` como aproximação para português

---

## Status das Melhorias

| Melhoria | Status |
|----------|--------|
| Normalização de encoding (`normalize_encoding`) | ✅ Implementado em `src/rag/utils/normalizer.py` |
| Prefixos visuais por tipo de chunk | ✅ Implementado em `QueryService.get_augmentation_text()` |
| Filtragem por tipo de metadado | ✅ Implementado em `QueryService.query_by_tipo()` |
| Indicadores visuais de confiança | ✅ Implementado em `ConfiancaCalculator.get_confidence_message()` |
| Comando `!reindexar` | ✅ Implementado |
| Comando `!fontes` | ✅ Implementado |
| Comando `!buscar <tipo>` | ✅ Implementado |

## Próximas Melhorias (Post-MVP)

- [ ] Suporte a PDF nativo
- [ ] Re-ranking por relevância jurídica
- [ ] Hybrid search (semântico + BM25)

---

## Referências

- **Implementação Atual:** `src/rag/`
- **Schema Técnico:** [`docs/rag_schema.md`](../../rag_schema.md)
