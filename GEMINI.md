# 🤖 BotSalinha - Instruções do Projeto

Este projeto é um bot de Discord especializado em **Direito Brasileiro** e **Concursos Públicos**, utilizando IA avançada com capacidades de RAG e memória persistente.

## 🚀 Visão Geral e Arquitetura

- **Tecnologias Core:** Python 3.12+, `discord.py`, `agno` (AI Framework), `pydantic-settings`, `sqlalchemy` (Async), `alembic`, `structlog`, `uv`.
- **IA Multi-Model:** Suporte nativo para OpenAI (`gpt-4o-mini`) e Google AI (`gemini-2.0-flash`). O provedor é definido no `config.yaml`.
- **RAG (Retrieval-Augmented Generation):** Busca semântica em documentos DOCX (CF/88, leis, etc.) usando embeddings da OpenAI (`text-embedding-3-small`).
- **Arquitetura em Camadas:**
  1. **Discord Layer:** Comandos e eventos (`src/core/discord.py`).
  2. **Middleware:** Rate limiting (Token Bucket) e Logging contextual.
  3. **Service Layer:** Agente (`src/core/agent.py`) integrando Agno + RAG.
  4. **Data Layer:** Repositório assíncrono para SQLite (`src/storage/`).

## 🛠️ Comandos e Execução (via `uv`)

O projeto utiliza um CLI centralizado: `uv run botsalinha [comando]`.

### Execução Principal
- **Iniciar Bot:** `uv run botsalinha run` (ou `start`)
- **Modo Chat CLI:** `uv run botsalinha chat` (interação direta no terminal sem Discord)
- **Ingestão RAG:** `uv run botsalinha ingest <caminho.docx>` (indexa documentos para o bot)

### Gerenciamento
- **Banco de Dados:**
  - `uv run botsalinha db status` - Estatísticas de conversas/mensagens.
  - `uv run botsalinha db clear` - Apaga todo o histórico.
- **Configuração:**
  - `uv run botsalinha config show` - Mostra configurações ativas.
  - `uv run botsalinha config set <chave> <valor>` - Altera `config.yaml` via CLI.
- **Prompts:**
  - `uv run botsalinha prompt list` - Lista versões de prompts em `prompt/`.
  - `uv run botsalinha prompt use <arquivo>` - Troca o prompt do sistema.
- **Testes:**
  - `uv run pytest` - Executa a suíte completa (mínimo 70% de cobertura).

## ⚙️ Configuração (Ordem de Precedência)

1. **`.env`**: Secrets e credenciais (`DISCORD_BOT_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`).
2. **`config.yaml`**: Comportamento do agente (modelo, temperatura, prompts, MCP).
3. **`DATABASE__URL`**: Suporta formato aninhado (Pydantic) ou flat `DATABASE_URL`.

## 📐 Convenções de Desenvolvimento

- **Código:** Seguir PEP 8 via **Ruff** (limite de 100 caracteres).
- **Tipagem:** **MyPy** em modo `strict` obrigatório para novas funções.
- **Async:** I/O sempre assíncrono. Nunca usar funções bloqueantes (`time.sleep`, `requests`) no loop principal.
- **Logs:** Usar `structlog`. Sempre passar contexto via kwargs: `log.info("evento", user_id=id)`.
- **Commits:** Seguir [Conventional Commits](https://www.conventionalcommits.org/).
- **Injeção de Dependência:** Usar `get_repository()` e injetar sessões nos serviços/agentes.

## 📚 RAG e Busca Semântica

O bot utiliza indicadores de confiança nas respostas:
- **Alta/Média:** Baseada em documentos indexados (cita fontes).
- **Baixa/Sem RAG:** Baseada no conhecimento geral da IA.

## 📂 Estrutura de Pastas Chave

- `src/core/`: Lógica principal do bot e do agente Agno.
- `src/rag/`: Serviços de embedding, ingestão e busca vetorial.
- `src/models/`: Definições ORM (SQLAlchemy) e Schemas (Pydantic).
- `migrations/`: Histórico de migrações do banco de dados (Alembic).
- `prompt/`: Arquivos Markdown/JSON com personas e instruções da IA.
