# Feature RAG (Retrieval-Augmented Generation)

## Visão Geral

O BotSalinha implementa um sistema RAG que permite respostas jurídicas fundamentadas em documentos reais (Constituição Federal de 1988 e Lei 8.112/90), com citações precisas e indicadores de confiança.

## Arquitetura

```
DOCX/XML → Parser → MetadataExtractor → ChunkExtractor → EmbeddingService → SQLite
                                                                    ↓
Usuario → Discord → QueryService → VectorStore → Agno → Resposta com Fontes
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

#### CodeIngestionService (`src/rag/services/code_ingestion_service.py`)
Responsável por ingerir código do repositório no sistema RAG.

**Pipeline:**
1. Parse XML (Repomix) com `RepomixXMLParser`
2. Extrair metadados de código com `CodeMetadataExtractor`
3. Criar chunks com `CodeChunkExtractor`
4. Gerar embeddings com `EmbeddingService`
5. Salvar no banco SQLite

**Método principal:**
```python
await code_ingestion_service.ingest_codebase(
    xml_file_path="repomix-output.xml",
    document_name="botsalinha-codebase"
)
```

#### QueryService (`src/rag/services/query_service.py`)
Orquestra a busca semântica e retorna contexto RAG.

**Método principal:**
```python
rag_context = await query_service.query(
    query_text="Quais são os direitos fundamentais?",
    top_k=5,
    min_similarity=0.4
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
- **ALTA** (≥0.70): Resposta baseada em documentos
- **MÉDIA** (0.55-0.69): Parcialmente baseada
- **BAIXA** (0.40-0.54): Informações limitadas
- **SEM_RAG** (<0.40): Conhecimento geral

## Contrato de Augmentação no Prompt

Quando o `AgentWrapper` decide usar contexto RAG, ele injeta um bloco determinístico no prompt com o seguinte formato:

```text
=== BLOCO_RAG_INICIO ===
RAG_STATUS: ALTA|MEDIA|BAIXA|SEM_RAG
RAG_QUERY_NORMALIZED: ...
RAG_RESULTADOS: <n>
RAG_SINALIZACAO: ...

CONTEXTO JURÍDICO RELEVANTE:
1. [Similaridade: 0.91]
Fonte: ...
Texto: ...

INSTRUÇÕES:
- ...
=== BLOCO_RAG_FIM ===
```

### Interpretação de `RAG_STATUS`

- `ALTA`: usar contexto como base principal da resposta e citar fontes.
- `MEDIA`: usar contexto como base principal, com alerta breve de validação complementar.
- `BAIXA`: usar contexto como referência parcial e recomendar confirmação em fontes oficiais.
- `SEM_RAG`: não inventar base jurídica; informar limitação de fonte e solicitar delimitação normativa ao usuário.

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
Executa operação administrativa de índice RAG.

Modos suportados:
- `completo` (default): recria o índice do zero.
- `incremental`: faz refresh por hash de conteúdo e só reembeda o que mudou.

**Uso:**
```
!reindexar
!reindexar completo
!reindexar incremental
```

**Requisitos:**
- Apenas o dono do bot pode executar
- Documentos DOCX devem estar em `docs/plans/RAG/`

**Resposta:**
```
✅ Reindexação RAG Concluída!

Modo: completo
📄 Documentos processados: 2
📦 Chunks indexados: 3300
⏱️ Duração: 12.5s

O índice RAG foi reconstruído com sucesso.
```

Resposta incremental:
```
✅ Reindexação RAG incremental concluída!

📄 Processados: 120
♻️ Atualizados: 8
⏭️ Sem alteração: 111
❌ Falhas: 1
📦 Chunks totais vistos: 45120
⏱️ Duração: 48.3s
```

## Configurações

### Variáveis de Ambiente

```bash
# .env
BOTSALINHA_RAG__ENABLED=true                        # Habilitar/desabilitar RAG
BOTSALINHA_RAG__TOP_K=5                             # Número de chunks a recuperar
BOTSALINHA_RAG__MIN_SIMILARITY=0.4                  # Similaridade mínima aceitável
BOTSALINHA_RAG__MAX_CONTEXT_TOKENS=2000             # Máximo de tokens no contexto
BOTSALINHA_RAG__CONFIDENCE_THRESHOLD=0.70           # Limiar para confiança média
BOTSALINHA_RAG__RETRIEVAL_MODE=hybrid_lite          # Modo estável atual
BOTSALINHA_RAG__RERANK_ENABLED=true                 # Rerank estável atual
BOTSALINHA_OPENAI__API_KEY=sk-...                   # Usada para embeddings (canônico)
# OPENAI_API_KEY=sk-...                             # Formato legado (funciona via fallback)
```

### Flags de Rollout Seguro (T3)

As flags abaixo permitem ativar estratégias novas de forma progressiva, com fallback imediato para o modo estável sem depender de rollback de código:

```bash
# Chunking (default seguro = off)
BOTSALINHA_RAG__ENABLE_EXPERIMENTAL_CHUNKING=false
BOTSALINHA_RAG__EXPERIMENTAL_CHUNKING_MODE=semantic_legal_v1

# Retrieval (default seguro = off)
BOTSALINHA_RAG__ENABLE_EXPERIMENTAL_RETRIEVAL=false
BOTSALINHA_RAG__EXPERIMENTAL_RETRIEVAL_MODE=hybrid_lite_v2

# Rerank (default seguro = off)
BOTSALINHA_RAG__ENABLE_EXPERIMENTAL_RERANK=false
BOTSALINHA_RAG__RERANK_PROFILE=stable_v1
BOTSALINHA_RAG__EXPERIMENTAL_RERANK_PROFILE=intent_aware_v1
BOTSALINHA_RAG__ROLLOUT_CANARY_PERCENTAGE=5
BOTSALINHA_RAG__ROLLOUT_STEP_PERCENTAGE=25
BOTSALINHA_RAG__ROLLOUT_AUTO_ROLLBACK=true
```

Fallback rápido:
- `*_ENABLE_EXPERIMENTAL_* = false` força retorno ao comportamento estável.
- Modos experimentais podem permanecer configurados; com flag desligada, não entram em produção.

### Configuração YAML (`config.yaml`) - Referência Operacional

```yaml
rag:
  enabled: true
  top_k: 5
  min_similarity: 0.4
  confidence_threshold: 0.70
  retrieval_mode: hybrid_lite
  rerank_enabled: true
  enable_experimental_chunking: false
  experimental_chunking_mode: semantic_legal_v1
  enable_experimental_retrieval: false
  experimental_retrieval_mode: hybrid_lite_v2
  enable_experimental_rerank: false
  rerank_profile: stable_v1
  experimental_rerank_profile: intent_aware_v1
```

### Smoke Test de Flags (on/off + fallback com migração aplicada)

```bash
uv run python - <<'PY'
from src.config.settings import Settings

# Cenário A: defaults seguros (tudo off)
s = Settings(_env_file=None)
assert s.rag.enable_experimental_chunking is False
assert s.rag.enable_experimental_retrieval is False
assert s.rag.enable_experimental_rerank is False
assert s.rag.effective_chunking_mode == "fixed_tokens_v1"
assert s.rag.effective_retrieval_mode == "hybrid_lite"
assert s.rag.effective_rerank_profile == "stable_v1"

# Cenário B: flags ON (rollout progressivo)
s_on = Settings(
    _env_file=None,
    rag={
        "enable_experimental_chunking": True,
        "enable_experimental_retrieval": True,
        "enable_experimental_rerank": True,
        "experimental_chunking_mode": "semantic_legal_v1",
        "experimental_retrieval_mode": "hybrid_lite_v2",
        "experimental_rerank_profile": "intent_aware_v1",
    },
)
assert s_on.rag.effective_chunking_mode == "semantic_legal_v1"
assert s_on.rag.effective_retrieval_mode == "hybrid_lite_v2"
assert s_on.rag.effective_rerank_profile == "intent_aware_v1"

# Cenário C: "migração aplicada + flag OFF"
# (novos campos/modos presentes, mas rollout desligado)
s_off = Settings(
    _env_file=None,
    rag={
        "enable_experimental_chunking": False,
        "enable_experimental_retrieval": False,
        "enable_experimental_rerank": False,
        "experimental_chunking_mode": "semantic_legal_v1",
        "experimental_retrieval_mode": "hybrid_fts_v1",
        "experimental_rerank_profile": "intent_aware_v1",
    },
)
assert s_off.rag.effective_chunking_mode == "fixed_tokens_v1"
assert s_off.rag.effective_retrieval_mode == "hybrid_lite"
assert s_off.rag.effective_rerank_profile == "stable_v1"

print("SMOKE_RAG_FLAGS_OK")
PY
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

#### Documentos Jurídicos (DOCX)

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

#### Codebase (XML/Repomix)

| Campo | Fonte | Exemplo |
|-------|-------|---------|
| `documento` | Nome do documento | "botsalinha-codebase" |
| `file_path` | Caminho do arquivo | "src/core/agent.py" |
| `language` | Extensão do arquivo | "python" |
| `line_start` | Linha inicial | "42" |
| `line_end` | Linha final | "156" |
| `functions` | Funções detectadas | ["generate_response"] |
| `classes` | Classes detectadas | ["AgentWrapper"] |
| `layer` | Camada da arquitetura | "core" |
| `module` | Módulo Python | "src.core.agent" |
| `is_test` | Arquivo de teste | True/False |

## Como Indexar Novos Documentos

### 1. Preparar o Documento

**Documentos Jurídicos (DOCX):**
- Formato: DOCX (Microsoft Word)
- Estrutura: Usar estilos deHeading (Heading 1-9) para títulos
- Metadados: Incluir marcadores como `#Atenção:`, `#STF:`, `#Concurso:`

**Codebase (XML/Repomix):**
- Gerar arquivo XML com Repomix: `npx repomix --output xml`
- O XML deve conter elementos `<file path="...">` com código
- Suporta Python, TypeScript, JavaScript, YAML, JSON, Markdown, etc.

### 2. Adicionar ao Diretório

**Documentos DOCX:**
```
docs/plans/RAG/novo_documento.docx
```

**Codebase (XML):**
```
repomix-output.xml  # ou qualquer caminho acessível
```

### 3. Executar Ingestão

**Documentos Jurídicos (via Discord):**
```bash
!reindexar completo
!reindexar incremental
```

**Codebase (via CLI):**
```bash
# Ingestão básica
uv run python scripts/ingest_codebase_rag.py repomix-output.xml

# Com nome personalizado
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "meu-projeto"

# Dry-run (apenas validação)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run

# Replace (substituir documento existente)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "botsalinha-codebase" --replace
```

**Requisitos para CLI:**
- `BOTSALINHA_OPENAI__API_KEY` configurada em `.env` (ou `OPENAI_API_KEY` para compatibilidade legada)
- Arquivo XML deve estar no formato Repomix

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
│   ├── __init__.py
│   ├── chunker.py              # Extrator de chunks genérico
│   ├── code_chunker.py         # Extrator de chunks para código
│   ├── docx_parser.py          # Parser de DOCX
│   └── xml_parser.py           # Parser de XML (Repomix)
├── services/
│   ├── __init__.py
│   ├── embedding_service.py    # OpenAI text-embedding-3-small
│   ├── ingestion_service.py    # Pipeline de ingestão DOCX
│   ├── code_ingestion_service.py  # Pipeline de ingestão codebase
│   └── query_service.py        # Busca semântica
├── storage/
│   ├── rag_repository.py       # Repository pattern para RAG
│   └── vector_store.py         # SQLite + busca vetorial
└── utils/
    ├── code_metadata_extractor.py  # Extração de metadados de código
    └── metadata_extractor.py   # Extração de metadados jurídicos
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

Eventos operacionais adicionais:
- `rag_fontes_consultadas`: métrica de inspeção de catálogo RAG via Discord.
- `rag_reindex_command_started`: início do comando `!reindexar` com modo e usuário.
- `rag_reindex_command_completed`: fechamento do comando com contagens e duração.
- `rag_reindex_incremental_document_failed`: falha por documento no modo incremental.

## Testes

### Rodar Testes RAG

```bash
# Todos os testes RAG
uv run pytest tests/ -k "rag" -v

# Apenas unitários
uv run pytest tests/unit/rag/ -v

# Testes de code ingestion
uv run pytest tests/integration/rag/test_code_ingestion.py -v

# Testes de parsers
uv run pytest tests/unit/rag/test_xml_parser.py -v
uv run pytest tests/unit/rag/test_code_chunker.py -v
uv run pytest tests/unit/rag/test_code_metadata_extractor.py -v

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
2. Reindexar incremental: `!reindexar incremental`
3. Se necessário, rebuild completo: `!reindexar completo`
4. Verificar `RAG_MIN_SIMILARITY` (muito alto?)
5. Verificar se `BOTSALINHA_OPENAI__API_KEY` está configurada (ou `OPENAI_API_KEY` para compatibilidade legada)

### Erro de Ingestão

**Problema:** Documentos não são indexados

**Soluções:**
1. Verificar formato do documento (deve ser DOCX)
2. Verificar estrutura (usar Heading styles)
3. Verificar logs: `tail -f logs/botsalinha.log | grep -E "rag_reindex|rag_ingestion|rag_fontes"`
4. Rodar incremental por CLI para diagnóstico:
   `uv run python scripts/ingest_all_rag.py --mode incremental --recursive`
5. Testar parser isoladamente

### Latência Alta

**Problema:** Respostas demoram > 2 segundos

**Soluções:**
1. Reduzir `RAG_TOP_K` (padrão: 5)
2. Verificar latência da API OpenAI
3. Considerar cache de embeddings

## Ingestão de Codebase

### Visão Geral

O sistema RAG suporta ingestão de código-fonte do repositório BotSalinha, permitindo consultas sobre a própria arquitetura e implementação do bot. Isso é útil para:

- Responder perguntas sobre como o bot funciona
- Documentar arquitetura e padrões de código
- Auxiliar em manutenção e debugging
- Fornecer contexto para novas funcionalidades

### Pipeline de Ingestão

```
Repomix XML → RepomixXMLParser → CodeMetadataExtractor → CodeChunkExtractor → EmbeddingService → SQLite
```

**Componentes:**

1. **RepomixXMLParser** (`src/rag/parser/xml_parser.py`)
   - Parse arquivo XML gerado pelo Repomix
   - Extrai conteúdo de elementos `<file path="...">`
   - Detecta linguagem de programação pela extensão
   - Suporta: Python, TypeScript, JavaScript, YAML, JSON, Markdown, etc.

2. **CodeMetadataExtractor** (`src/rag/utils/code_metadata_extractor.py`)
   - Extrai funções e classes do código
   - Identifica camada da arquitetura (core, models, storage, etc.)
   - Detecta arquivos de teste
   - Mapeia módulo Python

3. **CodeChunkExtractor** (`src/rag/parser/code_chunker.py`)
   - Chunks menores (300 tokens vs 500 para documentos)
   - Respeita limites de arquivos
   - Rastreia números de linha
   - Mantém contexto com overlap

4. **EmbeddingService** (existente)
   - Gera embeddings com OpenAI text-embedding-3-small
   - Processa chunks em batch

### CLI de Ingestão

**Script:** `scripts/ingest_codebase_rag.py`

**Uso básico:**
```bash
# Gerar XML com Repomix (primeira vez)
npx repomix --output xml

# Ingerir no RAG
uv run python scripts/ingest_codebase_rag.py repomix-output.xml
```

**Opções:**
```bash
# Nome personalizado
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "botsalinha-v1.0"

# Dry-run (validação sem ingestão)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run

# Replace (substituir documento existente)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "botsalinha-codebase" --replace
```

**Saída:**
```
📚 Codebase RAG Ingestion
📄 XML: repomix-output.xml
📦 Document: botsalinha-codebase

Files:    238
Chunks:   412
Tokens:   125,430
Cost:     $0.0251

✅ Ingestion complete!
```

### Estratégia de Chunking para Código

**Configuração padrão:**
```python
CHUNK_CONFIG = {
    "max_tokens": 300,           # Tamanho menor para código
    "overlap_tokens": 50,        # Overlap entre chunks
    "respect_boundaries": True,  # Respeita limites de arquivos
    "min_chunk_size": 50,        # Tamanho mínimo
}
```

**Metadados enriquecidos:**
- `file_path`: Caminho completo do arquivo
- `language`: Linguagem de programação
- `line_start`/`line_end`: Linhas do código
- `functions`: Lista de funções no chunk
- `classes`: Lista de classes no chunk
- `layer`: Camada da arquitetura (core, models, storage, etc.)
- `module`: Módulo Python (ex: `src.core.agent`)
- `is_test`: True se for arquivo de teste

### Exemplo de Consulta

```python
# Pergunta sobre o código
query = "Como funciona o wrapper do Agno?"

rag_context = await query_service.query(
    query_text=query,
    top_k=5,
    min_similarity=0.4
)

# Retorna chunks de:
# - src/core/agent.py (AgentWrapper)
# - src/config/yaml_config.py (configuração do agente)
# - docs/features/rag.md (documentação)
```

### Integração com Discord

Após ingestão, usuários podem perguntar sobre o código:

```
!ask Como o bot implementa rate limiting?
!ask Qual é a arquitetura do RAG?
!ask Onde fica a configuração do Discord?
```

O bot responderá com citações para o código-fonte específico.

## Custos

### Embeddings

| Operação | Tokens | Custo USD |
|----------|--------|-----------|
| CF/88 (ingestão) | ~150K | $0.003 |
| Lei 8.112 (ingestão) | ~30K | $0.0006 |
| Codebase (ingestão) | ~125K | $0.0025 |
| Query (pergunta) | ~50 | $0.00001 |
| **Total (one-time)** | ~305K | **$0.006** |

### Operacional

| Operação | Por Query | 1000 queries | 10K queries |
|----------|-----------|--------------|-------------|
| RAG (embedding + LLM) | ~$0.001 | ~$0.15 | ~$1.50 |

## Referências

- [Plano de Implementação RAG](../../.omc/plans/rag-feature-implementation.md)
- [Modelos RAG](../../src/models/rag_models.py)
- [Configurações RAG](../../src/config/settings.py)
