# ROADMAP

Para uma visão detalhada das capacidades já implementadas e em desenvolvimento, veja **[FEATURES.md](FEATURES.md)**.

## Agora (Sprint atual)

- [ ] Concluir alinhamento multi-model (OpenAI padrão + Google oficial)
- [ ] Fechar contrato de configuração (`config.yaml` define provider; `.env` define credenciais)
- [ ] Cobrir startup/config com testes (provider inválido, API key ausente, smoke por provider)
- [ ] Alinhar documentação operacional (`README.md`, `PRD.md`, `.env.example`, `docs/operations.md`)
- [ ] Adicionar MCPs
- [ ] Resolver apontamentos da análise do CodeRabbit
  - [ ] **Configuração e Ambiente:** Padronizar variáveis `.env.example` com prefixo `BOTSALINHA_`, restaurar `env_prefix` em `settings.py` e adicionar seção de migração na ADR-001.
  - [ ] **Segurança (MCP):** Remover credenciais hardcoded (API Keys, Banco de Dados) e caminhos locais do `.mcp.json`.
  - [ ] **Core e Storage:** Corrigir erro de concorrência em iteradores no `sqlite_repository.py`, problemas de divisão de mensagens e logs estruturados em `discord.py`.
  - [ ] **Testes:** Corrigir decorators `asyncio`, adicionar marcações `e2e` e substituir uso global de `settings` por `get_settings()` em `test_cli.py`.
  - [ ] **Ferramental e Docs:** Melhorar validação, formatação e remover typos nos scripts de skill-creator; corrigir comandos do `memory_profiler` e comandos de lint (Ruff) em arquivos Markdown.

## Próximas entregas (Curto prazo)

- [ ] Sistema de citação de fontes jurídicas
- [ ] Índice de legislação e jurisprudência
- [ ] Dashboard de analytics
- [ ] Interface web para gerenciamento de conversas

## Médio prazo

- [ ] Suporte a modelos adicionais além de OpenAI/Google (ex.: Claude)
- [ ] Suporte a múltiplos idiomas

---

## Estratégia de RAG Local

Para ~1.000 documentos, um RAG local em VPS é **perfeitamente viável** — é um volume pequeno/médio que roda confortavelmente sem infraestrutura complexa.

### Por que Local?

Tudo depende do tamanho dos documentos, mas estimando documentos de texto médios (~2–5 páginas cada):

| Componente                      | ~1.000 docs                 |
| ------------------------------- | --------------------------- |
| Embeddings (1536 dims, float32) | ~50–150 MB RAM              |
| Índice vetorial (FAISS flat)    | ~100–300 MB disco           |
| Modelo de embedding local       | 500 MB – 2 GB (se local)    |
| **Total estimado**              | **~1–3 GB RAM confortável** |

Uma VPS de **2–4 GB RAM** já comporta tudo isso com folga para o bot Discord rodar junto.

### Stack RAG Local Recomendado

Para 1.000 docs, **não precisa** de solução pesada como Weaviate ou Qdrant com servidor separado. O stack leve ideal:

```text
Embeddings → sentence-transformers (local) ou API (OpenAI/Cohere)
Vector Store → ChromaDB (persistente em disco, zero config)
Orquestração → LlamaIndex ou LangChain
LLM → API externa (Anthropic/OpenAI) ou Ollama local
```

```bash
uv add chromadb sentence-transformers llama-index python-dotenv
```

### Implementação Mínima

```python
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# Inicializa DB persistente em disco
client = chromadb.PersistentClient(path="./rag_db")

embed_fn = SentenceTransformerEmbeddingFunction(
    model_name="intfloat/multilingual-e5-large"  # ótimo para PT-BR
)

collection = client.get_or_create_collection(
    name="documentos",
    embedding_function=embed_fn
)

# Indexar (roda uma vez)
def indexar_documentos(docs: list[dict]):
    collection.add(
        documents=[d["texto"] for d in docs],
        metadatas=[d["metadata"] for d in docs],
        ids=[d["id"] for d in docs]
    )

# Buscar (a cada mensagem)
def buscar(query: str, n_results: int = 5):
    return collection.query(
        query_texts=[query],
        n_results=n_results
    )
```

### Integração com o Bot Discord

```python
async def chamar_llm(prompt: str, user_id: str) -> str:
    # 1. Busca contexto relevante
    resultados = buscar(prompt, n_results=4)
    contexto = "\n\n".join(resultados["documents"][0])

    # 2. Monta prompt com RAG
    system = f"""Você é um assistente especializado.
Use o contexto abaixo para responder. Se não souber, diga que não encontrou.

CONTEXTO:
{contexto}"""

    # 3. Chama o LLM
    resposta = await anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    return resposta.content[0].text
```

### Modelo de Embedding: API vs Local

|                     | API (OpenAI/Cohere) | Local (sentence-transformers)     |
| ------------------- | ------------------- | --------------------------------- |
| Custo               | Por chamada         | Zero                              |
| RAM na VPS          | ~50 MB              | 500 MB – 2 GB                     |
| Qualidade PT-BR     | ✅ Alta             | ✅ Alta (`multilingual-e5-large`) |
| Latência            | ~200ms              | ~50–100ms (CPU)                   |
| Dependência externa | Sim                 | Não                               |

Para documentos jurídicos/administrativos em PT-BR, o modelo `intfloat/multilingual-e5-large` ou `paraphrase-multilingual-mpnet-base-v2` são excelentes opções locais.

### VPS Mínima Recomendada

- **RAM:** 4 GB (2 GB para o bot + RAG, 2 GB de folga)
- **Disco:** 10 GB SSD (ChromaDB + modelo de embedding)
- **CPU:** 2 vCPUs (embedding em CPU é lento mas OK para ~1k docs)
- **Referência de preço:** ~$12–20/mês (DigitalOcean, Hostinger)

## Critério de avanço da sprint atual

- [ ] `uv run ruff check .`
- [ ] `uv run mypy src`
- [ ] `uv run pytest`
