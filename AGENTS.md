<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->

# AGENTS.md — BotSalinha

## Purpose

BotSalinha é um bot do Discord especializado em direito brasileiro e preparação para concursos públicos, desenvolvido com framework Agno e modelos de IA OpenAI/Google. Fornece conversas contextuais com histórico persistente, limitação de taxa por usuário e logging estruturado.

### Características Principais
- **Linguagem:** Python 3.12+ com async/await
- **Framework:** discord.py + Agno AI Agent
- **IA:** OpenAI gpt-4o-mini e Google Gemini via Agno
- **Banco de Dados:** SQLite + SQLAlchemy ORM async + Alembic
- **Package Manager:** `uv`

## Arquivos Chave

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `bot.py` | Ponto de entrada mínimo (CLI wrapper) | `uv run bot.py` |
| `pyproject.toml` | Configuração de projeto e dependências | `uv sync` |
| `config.yaml` | Configuração do Agente/models YAML | `cat config.yaml` |
| `.env.example` | Template de variáveis de ambiente | `cp .env.example .env` |
| `README.md` | Documentação principal (em português) | `cat README.md` |

## Subdiretórios

| Diretório | Descrição | Arquivos Importantes |
|-----------|-----------|---------------------|
| `src/` | Código fonte principal | `main.py`, `core/`, `config/`, `models/`, `storage/` |
| `tests/` | Suítes de testes | `conftest.py`, `unit/`, `integration/`, `e2e/` |
| `docs/` | Documentação | `DEVELOPER_GUIDE.md`, `deployment.md`, `operations.md` |
| `migrations/` | Migrações do Alembic | `alembic.ini`, `versions/` |
| `scripts/` | Scripts utilitários | `backup.py`, `run_tests.sh` |
| `prompt/` | System prompts do Agente | `prompt_v1.md`, `prompt_v2.json`, `prompt_v3.md` |
| `assets/` | Recursos estáticos (imagens, etc.) | - |
| `data/` | Dados persistentes | `botsalinha.db` (SQLite runtime) |

## Para Agentes de IA

### Instruções de Trabalho

1. **Entenda o Contexto:**
   - BotSalinha funciona no Discord com comandos prefixados por `!`
   - Responde perguntas sobre direito brasileiro e concursos públicos
   - Mantém histórico de conversas por usuário/guilda
   - Usa rate limiting para evitar abusos

2. **Padrões de Código:**
   - Todo código assíncrono (`async/await`)
   - Pydantic Settings com `get_settings()` (nunca instanciar diretamente)
   - Repository Pattern com interfaces abstratas
   - Structlog para logging estruturado
   - Error hierarchy customizada (herda de `BotSalinhaError`)

3. **Configuração Importante:**
   - Tokens de API em `.env` (OPENAI_API_KEY, GOOGLE_API_KEY)
   - Rate limiting: 10 requests por 60 segundos por usuário
   - Histórico: 3 pares pergunta/resposta por conversa

### Requisitos de Testes

1. **Convenções de Testes:**
   - Use fixtures em `tests/conftest.py`
   - Banco de dados: SQLite em memória (`sqlite+aiosqlite:///:memory:`)
   - Mock Discord API (nunca chamar API real)
   - Mock OpenAI/Google API
   - Faker com locale `pt_BR` para dados realistas

2. **Markers Disponíveis:**
   ```python
   @pytest.mark.unit          # Teste isolado (sem I/O)
   @pytest.mark.integration   # Componentes juntos
   @pytest.mark.e2e           # Workflow completo
   @pytest.mark.slow          # Demorado (>1s)
   @pytest.mark.discord       # Requiere Discord mock
   @pytest.mark.database      # Requiere acesso a DB
   ```

3. **Cobertura Mínima:** 70% (enforcado no CI)

### Padrões Comuns

#### Adicionar Novo Comando Discord
1. Editar `src/core/discord.py`
2. Método com `@commands.command(name="meucomando")`
3. Aplicar rate limiting padrão
4. Adicionar testes em `tests/unit/`

#### Adicionar Nova Configuração
1. Adicionar campo em `src/config/settings.py`
2. Atualizar `.env.example`
3. Atualizar este AGENTS.md se necessário

#### Adicionar Novo Modelo de Banco de Dados
1. Criar ORM + Pydantic em `src/models/`
2. Adicionar métodos abstratos em `src/storage/repository.py`
3. Implementar em `src/storage/sqlite_repository.py`
4. Gerar migração: `uv run alembic revision --autogenerate -m "add_meu_modelo"`
5. Aplicar: `uv run alembic upgrade head`

#### Executar Bot Localmente (sem Discord)
```bash
cp .env.example .env
# Editar .env com GOOGLE_API_KEY (não precisa de DISCORD_TOKEN)
uv sync
uv run bot.py --chat
```

## Dependências

### Dependências Externas
- **discord.py** (v2.3+) - Biblioteca de Discord API
- **agno** - Agente de IA com suporte OpenAI/Google
- **openai** (v1.30+) - Cliente OpenAI API
- **google-generativeai** (v0.8+) - Cliente Google Gemini API
- **sqlalchemy[asyncio]** (v2.0+) - ORM assíncrono
- **alembic** - Migrações de banco de dados
- **pydantic-settings** (v2.0+) - Settings com Pydantic
- **pydantic** (v2.0+) - Validação de dados
- **uv** (v0.3+) - Package manager e ambiente virtual
- **pytest** (v7.4+) - Framework de testes
- **structlog** (v23.0+) - Logging estruturado
- **faker** (v20.0+) - Dados de teste realistas
- **freezegun** - Mock de tempo para testes
- **pytest-mock** - Mocks para testes
- **pytest-asyncio** - Suporte async para pytest
- **ruff** - Linter e formatter Python
- **mypy** - Checagem de tipos

### Dependências de Desenvolvimento
- **pre-commit** - Hooks pré-commit
- **black** - Formatter (integrado ao ruff)
- **isort** - Import sorting (integrado ao ruff)
- **bandit** - Análise de segurança
- **safety** - Análise de vulnerabilidades

## Ambiente de Execução

### Variáveis de Ambiente Essenciais
```bash
DISCORD_BOT_TOKEN=<seu_token_discord>
OPENAI_API_KEY=<sua_chave_openai>
GOOGLE_API_KEY=<sua_chave_google>  # Opcional
DATABASE_URL=sqlite:///data/botsalinha.db
LOG_LEVEL=INFO
LOG_FORMAT=json
COMMAND_PREFIX=!
```

### Ambiente Docker
```bash
# Desenvolvimento
docker-compose up -d
docker-compose logs -f

# Produção
docker-compose -f docker-compose.prod.yml up -d
```
