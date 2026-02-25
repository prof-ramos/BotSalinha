# Guia do Desenvolvedor - BotSalinha

Este guia fornece informações completas para desenvolvedores que trabalham no BotSalinha.

## Sumário

1. [Instruções de Configuração](#1-instruções-de-configuração)
2. [Visão Geral da Estrutura do Projeto](#2-visão-geral-da-estrutura-do-projeto)
3. [Fluxo de Trabalho de Desenvolvimento](#3-fluxo-de-trabalho-de-desenvolvimento)
4. [Abordagem de Teste](#4-abordagem-de-teste)
5. [Solução de Problemas](#5-solução-de-problemas)

---

## 1. Instruções de Configuração

### Pré-requisitos

- **Python**: 3.12 ou superior
- **uv**: Gerenciador de pacotes Python moderno
- **Git**: Para controle de versão
- **Docker** (opcional): Para desenvolvimento em container

### Configuração Inicial

#### 1. Clone o Repositório

```bash
git clone <repository-url>
cd BotSalinha
```

#### 2. Instale as Dependências

```bash
# Instalar uv se não tiver instalado
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sincronizar dependências
uv sync
```

#### 3. Configure Variáveis de Ambiente

```bash
# Copiar template de ambiente
cp .env.example .env

# Editar .env com suas credenciais
# Variáveis obrigatórias:
# - DISCORD_BOT_TOKEN
# - GOOGLE_API_KEY
```

#### 4. Ative o Ambiente Virtual

```bash
# O uv cria o ambiente automaticamente
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate     # Windows
```

#### 5. Instale Hooks de Pre-commit

```bash
uv run pre-commit install
```

### Verificação da Configuração

Execute os seguintes comandos para verificar se tudo está funcionando:

```bash
# Verificar versão do Python
uv run python --version

# Executar testes
uv run pytest

# Verificar lint
uv run ruff check src/

# Verificar tipos
uv run mypy src/
```

---

## 2. Visão Geral da Estrutura do Projeto

### Diretórios Principais

```text
botsalinha/
├── bot.py                      # Ponto de entrada principal
├── pyproject.toml              # Dependências e configuração do projeto
├── .env.example                # Template de variáveis de ambiente
│
├── src/                        # Código fonte principal
│   ├── __init__.py
│   ├── main.py                 # Função principal da aplicação
│   │
│   ├── config/                 # Configuração
│   │   └── settings.py         # Pydantic Settings com validação
│   │
│   ├── core/                   # Componentes centrais
│   │   ├── agent.py            # Wrapper do Agno AI Agent
│   │   ├── discord.py          # Bot Discord com comandos
│   │   └── lifecycle.py        # Gerenciamento de ciclo de vida
│   │
│   ├── models/                 # Modelos de dados
│   │   ├── conversation.py     # Modelo Conversação (SQLAlchemy + Pydantic)
│   │   └── message.py          # Modelo Mensagem (SQLAlchemy + Pydantic)
│   │
│   ├── storage/                # Camada de persistência
│   │   ├── repository.py       # Interfaces abstratas de repositório
│   │   └── sqlite_repository.py# Implementação SQLite
│   │
│   ├── utils/                  # Utilitários
│   │   ├── logger.py           # Configuração structlog
│   │   ├── errors.py           # Exceções customizadas
│   │   └── retry.py            # Lógica de retry com tenacity
│   │
│   └── middleware/             # Middleware
│       └── rate_limiter.py     # Limitação de taxa (token bucket)
│
├── tests/                      # Suíte de testes
│   ├── conftest.py             # Configuração pytest e fixtures
│   ├── test_rate_limiter.py    # Testes de rate limiter
│   └── ...                     # Mais testes
│
├── migrations/                 # Migrações Alembic
│   ├── alembic.ini             # Configuração Alembic
│   ├── env.py                  # Ambiente de migração
│   └── versions/               # Arquivos de migração
│
├── scripts/                    # Scripts utilitários
│   └── backup.py               # Script de backup do SQLite
│
├── docs/                       # Documentação
│   ├── deployment.md           # Guia de implantação
│   └── operations.md           # Manual de operações
│
├── data/                       # Banco de dados SQLite (gitignore)
├── logs/                       # Logs da aplicação (gitignore)
└── backups/                    # Backups do banco (gitignore)
```

### Arquitetura em Camadas

```text
┌─────────────────────────────────────────────────┐
│           Camada de Apresentação                │
│  (Discord Bot, Comandos, Event Handlers)        │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│           Camada de Middleware                  │
│     (Rate Limiting, Error Handling)             │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│            Camada de Serviço                    │
│     (Agent Wrapper, Business Logic)             │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│         Camada de Acesso a Dados                │
│  (Repository Pattern, SQLAlchemy ORM)           │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│              Camada de Dados                    │
│           (SQLite Database)                     │
└─────────────────────────────────────────────────┘
```

### Fluxo de Dados

```text
Usuário Discord
    │
    ▼
!ask pergunta
    │
    ▼
Discord Bot → Rate Limiter → Agent Wrapper
                                   │
                                   ▼
                            Conversation History
                                   │
                                   ▼
                            Gemini 2.0 Flash
                                   │
                                   ▼
                            Resposta Formatada
                                   │
                                   ▼
                            Salvar no SQLite
                                   │
                                   ▼
                            Enviar para Discord
```

---

## 3. Fluxo de Trabalho de Desenvolvimento

### Branch Strategy

```text
main           ← Branch de produção
├── develop    ← Branch de desenvolvimento
    ├── feature/feature-name    ← Novas funcionalidades
    ├── bugfix/bug-name         ← Correções de bugs
    └── hotfix/issue-name       ← Correções urgentes
```

### Processo de Desenvolvimento

#### 1. Crie uma Branch

```bash
git checkout -b feature/nova-funcionalidade
```

#### 2. Faça Suas Alterações

```bash
# Editar arquivos
# Executar testes
uv run pytest

# Formatar código
uv run ruff format src/

# Verificar lint
uv run ruff check src/

# Verificar tipos
uv run mypy src/
```

#### 3. Commit suas Mudanças

```bash
git add .
git commit -m "feat: adicionar nova funcionalidade"
```

**Convenções de Commit:**

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Mudanças na documentação
- `style:` Formatação, ponto e vírgula, etc.
- `refactor:` Refatoração de código
- `test:` Adiciona ou modifica testes
- `chore:` Atualização de tarefas, configs, etc.

#### 4. Push e Pull Request

```bash
git push origin feature/nova-funcionalidade
```

Crie um Pull Request no GitHub com descrição das mudanças.

### Comandos Comuns de Desenvolvimento

#### Executar o Bot Localmente

```bash
uv run bot.py
```

#### Executar Testes Específicos

```bash
# Todos os testes
uv run pytest

# Teste específico
uv run pytest tests/test_rate_limiter.py

# Com coverage
uv run pytest --cov=src --cov-report=html

# Verbose
uv run pytest -v
```

#### Trabalhar com Migrações

```bash
# Criar migração
uv run alembic revision --autogenerate -m "descricao"

# Aplicar migrações
uv run alembic upgrade head

# Reverter última migração
uv run alembic downgrade -1

# Ver histórico
uv run alembic history
```

#### Lint e Formatação

```bash
# Verificar problemas
uv run ruff check src/

# Auto-corrigir problemas
uv run ruff check --fix src/

# Formatar código
uv run ruff format src/

# Verificar formatação sem modificar
uv run ruff format --check src/
```

#### Type Checking

```bash
# Verificar tipos
uv run mypy src/

# Verificar arquivo específico
uv run mypy src/core/agent.py
```

### Debugging

#### Debug Local com VS Code

Crie `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: BotSalinha",
      "type": "debugpy",
      "request": "launch",
      "module": "bot",
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Pytest: Current File",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

#### Debug de Logs

```bash
# Habilitar logs debug no .env
LOG_LEVEL=DEBUG

# Executar com logs debug
uv run bot.py
```

---

## 4. Abordagem de Teste

### Pirâmide de Testes

```text
        ┌─────┐
       / E2E  \         ← Poucos, lentos (Playwright)
      /───────\
     / Integração \     ← Alguns, moderados
    /─────────────\
   /  Unitários    \    ← Muitos, rápidos (pytest)
  /─────────────────\
```

### Testes Unitários

**Localização:** `tests/`

**Exemplo:**

```python
import pytest
from src.middleware.rate_limiter import RateLimiter
from src.utils.errors import RateLimitError

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        limiter = RateLimiter(requests=10, window_seconds=60)

        # Não deve lançar exceção
        await limiter.check_rate_limit(user_id="123", guild_id="456")

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self):
        limiter = RateLimiter(requests=1, window_seconds=60)

        await limiter.check_rate_limit(user_id="123", guild_id="456")

        # Deve lançar exceção
        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(user_id="123", guild_id="456")
```

### Fixtures do Pytest

**Localização:** `tests/conftest.py`

```python
import pytest
from src.storage.sqlite_repository import SQLiteRepository

@pytest_asyncio.fixture
async def conversation_repository():
    """Repositório para testes."""
    repo = SQLiteRepository("sqlite+aiosqlite:///:memory:")
    await repo.initialize_database()
    await repo.create_tables()

    yield repo

    await repo.close()

@pytest.fixture
def mock_discord_context():
    """Contexto Discord simulado."""
    ctx = MagicMock()
    ctx.author.id = 123456789
    ctx.send = AsyncMock()
    return ctx
```

### Executar Testes

```bash
# Todos os testes
uv run pytest

# Testes específicos
uv run pytest tests/test_rate_limiter.py

# Teste específico
uv run pytest tests/test_rate_limiter.py::TestRateLimiter::test_check_rate_limit_allowed

# Com coverage
uv run pytest --cov=src --cov-report=html --cov-report=term

# Parar no primeiro erro
uv run pytest -x

# Mostrar print statements
uv run pytest -s
```

### Boas Práticas de Teste

1. **Testes Independentes**: Cada teste deve funcionar isoladamente
2. **AAA Pattern**: Arrange, Act, Assert
3. **Nomes Descritivos**: `test_<oque>_<quando>_<entao>`
4. **Mock External Services**: Use mocks para APIs externas
5. **Test Edge Cases**: Limite, vazio, nulo, etc.

---

## 5. Solução de Problemas

### Problemas Comuns de Desenvolvimento

#### 1. Erro: "No module named 'src'"

**Causa:** Python não encontra o módulo src.

**Solução:**

```bash
# Garantir que está executando com uv
uv run python bot.py

# Ou ativar o venv
source .venv/bin/activate
python bot.py
```

#### 2. Erro: "DATABASE_URL not set"

**Causa:** Variáveis de ambiente não configuradas.

**Solução:**

```bash
# Criar arquivo .env
cp .env.example .env

# Editar .env com valores corretos
```

#### 3. Erro: "discord.py.errors.LoginFailure"

**Causa:** Token do Discord inválido.

**Solução:**

1. Verifique o token em `.env`
2. Gere novo token no Discord Developer Portal
3. Certifique-se de copiar o token completo (59 caracteres)

#### 4. Erro: "sqlite3.OperationalError: database is locked"

**Causa:** Múltiplas instâncias acessando o SQLite.

**Solução:**

```bash
# Parar todas as instâncias
docker-compose down
pkill -f bot.py

# Verificar processos
ps aux | grep bot.py

# Deletar arquivo de lock se existir
rm data/botsalinha.db-wal
rm data/botsalinha.db-shm
```

#### 5. Erro: "mypy: error: invalid syntax"

**Causa:** Versão do Python incompatível.

**Solução:**

```bash
# Verificar versão do Python
python --version  # Deve ser 3.12+

# Reinstalar dependências
uv sync
```

### Problemas de Performance

#### Bot Lento para Responder

**Diagnosticar:**

```bash
# Verificar logs
tail -f logs/botsalinha.log | grep "duration"

# Verificar latência da API
curl -w "@curl-format.txt" -o /dev/null -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=YOUR_KEY"
```

**Soluções:**

- Aumentar `HISTORY_RUNS` para reduzir contexto
- Verificar latência de rede
- Usar cache para respostas comuns

#### Alto Uso de Memória

**Diagnosticar:**

```bash
# Verificar uso de memória
docker stats botsalinha

# Ou localmente
python -m memory_profiler bot.py
```

**Soluções:**

- Limpar conversas antigas: `!limpar` ou cleanup automático
- Reduzir tamanho do histórico
- Verificar memory leaks

### Problemas de Testes

#### Testes Falham com "asyncio"

**Erro:** `RuntimeError: This event loop is already running`

**Solução:**

```python
# Usar pytest-asyncio corretamente
@pytest.mark.asyncio
async def test_minha_funcao():
    resultado = await funcao_async()
    assert resultado is not None
```

#### Testes Lentos

**Soluções:**

```bash
# Usar banco em memória
TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:"

# Usar fixtures de escopo correto
@pytest.fixture(scope="session")  # Ao invés de function
def expensive_resource():
    ...
```

### Recursos de Debug

#### Logs Estruturados

```python
import structlog

log = structlog.get_logger()

# Adicionar contexto
log = log.bind(user_id="123", guild_id="456")

# Log com contexto
log.info("processando_requisicao", action="ask", length=100)

# Log de erro
log.error("falha_na_api", error_type="ConnectionError", retry=1)
```

#### Verificar Estado do Banco

```python
# Python shell interativo
uv run python

>>> from src.storage.sqlite_repository import get_repository
>>> import asyncio
>>>
>>> async def check_db():
...     repo = get_repository()
...     convs = await repo.get_by_user_and_guild("123", "456")
...     print(f"Conversas: {len(convs)}")
...     for conv in convs:
...         print(f"  - {conv.id}: {conv.created_at}")
...
>>> asyncio.run(check_db())
```

### Obter Ajuda

**Recursos Internos:**

- [PRD.md](PRD.md) - Requisitos do produto
- [docs/deployment.md](docs/deployment.md) - Guia de implantação
- [docs/operations.md](docs/operations.md) - Manual de operações

**Recursos Externos:**

- [Agno Documentation](https://github.com/agno-ai/agno)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

---

## Checklist de Desenvolvimento

### Antes de Commitar

- [ ] Testes passando: `uv run pytest`
- [ ] Lint clean: `uv run ruff check src/`
- [ ] Tipos ok: `uv run mypy src/`
- [ ] Código formatado: `uv run ruff format src/`
- [ ] Documentação atualizada
- [ ] Changelog atualizado (se aplicável)

### Antes de Criar PR

- [ ] Branch atualizada com `develop`
- [ ] Commits com mensagens claras
- [ ] CI/CD passando
- [ ] Revisor atribuído
- [ ] Descrição da PR completa

### Antes de Deploy

- [ ] Testes de integração passando
- [ ] Migrações testadas
- [ ] Backup do banco criado
- [ ] Documentação de deploy atualizada
- [ ] Rollback planejado

---

### Happy Coding! 🚀

Para mais informações, consulte os outros documentos do projeto ou abra uma issue no GitHub.
