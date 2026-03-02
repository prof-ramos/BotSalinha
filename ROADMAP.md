# ROADMAP

Para uma visão detalhada das capacidades já implementadas e em desenvolvimento, veja **[FEATURES.md](FEATURES.md)**.

## Agora (Sprint atual)

- [ ] Sistema de citação de fontes jurídicas
- [ ] Índice de legislação e jurisprudência
- [ ] Dashboard de analytics
- [ ] Interface web para gerenciamento de conversas

---

## Concluído

### Multi-Model Support (Sprint Finalizada)
- [x] Alinhamento multi-model (OpenAI padrão + Google oficial)
- [x] Contrato de configuração (`config.yaml` define provider; `.env` define credenciais)
- [x] Documentação operacional alinhada (`docs/architecture.md`, `docs/CODE_DOCUMENTATION.md`, `docs/operations.md`)
- [x] **ADR-001:** Decisão arquitetural para multi-model provider documentada em `docs/adr/ADR-001-multi-model-provider.md`

### RAG Implementation (Sprint Finalizada)
- [x] Implementação completa de RAG para documentos
- [x] Implementação de RAG para codebase (código como contexto)
- [x] Sistema de chunking de código com metadados
- [x] Parser XML para documentos estruturados
- [x] Extração de metadados de código (funções, classes, imports)
- [x] Integração com vector store (ChromaDB)
- [x] Documentação completa em `docs/features/rag.md`

### Fast Path Otimization (Sprint Finalizada)
- [x] **Cache Semântico:** Fast Path implementado para otimizar cache hits
- [x] Cache check movido para ANTES de get_conversation_history()
- [x] Cache hit latência: 518ms → 1ms (99.8% melhoria)
- [x] SLO ≤100ms atingido
- [x] Speedup de 11,583x em cache hits
- [x] Testes criados em `tests/unit/test_agent_fast_path.py`
- [x] Script de teste de latência em `scripts/test_semantic_cache_latency.py`
- [x] Commit: c9e1d1c - feat(agent): implementar Fast Path para otimizar cache hits (Fase 1)

### CodeRabbit Fixes (20 correções aplicadas)
- [x] **Configuração e Ambiente:** Variáveis `.env.example` padronizadas com prefixo `BOTSALINHA_`, `env_prefix` restaurado em `settings.py`, seção de migração adicionada na ADR-001
- [x] **Segurança (MCP):** Credenciais hardcoded removidas de `.mcp.json`
- [x] **Core e Storage:** Erro de concorrência em iteradores corrigido em `sqlite_repository.py`, problemas de divisão de mensagens e logs estruturados corrigidos em `discord.py`
- [x] **Testes:** Decorators `asyncio` corrigidos, marcações `e2e` adicionadas, uso global de `settings` substituído por `get_settings()` em `test_cli.py`
- [x] **Ferramental e Docs:** Validação melhorada, formatação corrigida, typos removidos, comandos de lint (Ruff) corrigidos
- [x] Documentação técnica atualizada:
  - `docs/architecture.md` - Visão arquitetural completa
  - `docs/CODE_DOCUMENTATION.md` - Documentação detalhada do código
  - `docs/adr/ADR-001-multi-model-provider.md` - Decisão de multi-model provider

## Próximas entregas (Curto prazo)

- [ ] Sistema de citação de fontes jurídicas com formatação ABNT
- [ ] Índice de legislação e jurisprudência (busca por palavras-chave)
- [ ] Dashboard de analytics (uso por usuário, perguntas mais frequentes)
- [ ] Interface web para gerenciamento de conversas

## Médio prazo

- [ ] Suporte a Claude (Anthropic) como provider adicional
- [ ] Suporte a múltiplos idiomas (espanhol, inglês)
- [ ] Sistema de feedback para respostas (thumbs up/down)

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
