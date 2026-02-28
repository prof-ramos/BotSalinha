<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->
Parent reference: ../../AGENTS.md

# AGENTS.md — BotSalinha Core

## Purpose

Módulo principal da lógica de negócios do BotSalinha. Contém a implementação central do bot do Discord, wrapper do Agente AI, interface CLI e gerenciamento de ciclo de vida. Este é o coração do sistema, responsável por processar comandos Discord, gerar respostas AI e gerenciar recursos.

### Características Principais
- **AgentWrapper**: Abstração sobre o framework Agno com injeção de dependências
- **BotSalinhaBot**: Implementação principal do Discord bot com comandos integrados
- **CLI Interface**: Interface completa desenvolvedor com múltiplos subcomandos
- **Lifecycle Management**: Shutdown graceful e gerenciamento de recursos
- **MCP Support**: Integração com Model Context Protocol para ferramentas externas

## Arquivos Chave

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `agent.py` | Agno AgentWrapper com injeção de repositório e MCP | `uv run src/core/cli.py chat` |
| `discord.py` | BotSalinhaBot com comandos Discord (!ask, !ping, etc) | `uv run src/core/cli.py run` |
| `cli.py` | Interface CLI com múltiplos subcomandos | `uv run src/core/cli.py --help` |
| `lifecycle.py` | Gerenciamento de ciclo de vida e shutdown graceful | `uv run src/core/cli.py stop` |

## Subdiretórios

| Diretório | Descrição | Arquivos Importantes |
|-----------|-----------|---------------------|
| `../config/` | Configuração do sistema | `settings.py`, `yaml_config.py` |
| `../models/` | Modelos de dados | `conversation.py`, `message.py` |
| `../storage/` | Camada de persistência | `repository.py`, `sqlite_repository.py` |
| `../utils/` | Utilitários e erros | `logger.py`, `errors.py`, `retry.py` |
| `../tools/` | Ferramentas externas | `mcp_manager.py` |

## Para Agentes de IA

### Instruções de Trabalho

1. **Entenda a Arquitetura:**
   - AgentWrapper requer repositório via injeção de dependência (NÃO singleton)
   - BotSalinhaBot gerencia comandos Discord com rate limiting integrado
   - Todas as operações são assíncronas (`async/await`)
   - MCP Tools são gerenciados via `MCPToolsManager` se habilitado

2. **Padrões de Código:**
   - **Repository Pattern**: Sempre usar `async with create_repository() as repo:` para novas instâncias
   - **Injeção de Dependência**: Nunca instanciar diretamente, receber via constructor
   - **Async/Await**: Todas as I/O operations devem usar `async/await`
   - **Error Handling**: Usar hierarchy de `BotSalinhaError` do `../utils/errors.py`
   - **Logging**: Sempre usar `structlog` com context binding

3. **Configuração Importante:**
   - Tokens de API em `.env` (OPENAI_API_KEY, GOOGLE_API_KEY, DISCORD_BOT_TOKEN)
   - Rate limiting: 10 requests por 60 segundos por usuário (via discord.py)
   - Histórico: 3 pares pergunta/resposta por conversa (configurável)
   - MCP: Habilitado via `config.yaml` > `mcp.enabled: true`

### Requisitos de Testes

1. **Convenções de Testes:**
   - Usar fixtures em `../tests/conftest.py`
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

#### Criar Novo Comando Discord
1. Editar `discord.py`
2. Adicionar método com `@commands.command(name="meucomando")`
3. Aplicar rate limiting padrão com `@commands.cooldown()`
4. Adicionar error handler específico se necessário
5. Adicionar testes em `../tests/unit/`

#### Criar Nova Ferramenta MCP
1. Editar `../tools/mcp_manager.py`
2. Adicionar configuração em `config.yaml`
3. Registrar tool no `MCPToolsManager`
4. Testar via CLI: `uv run src/core/cli.py mcp list`

#### Modificar Configuração
1. Adicionar campo em `../config/settings.py`
2. Atualizar `config.yaml` se necessário
3. Atualizar `.env.example`
4. Atualizar este AGENTS.md se necessário

#### Executar Bot Localmente
```bash
uv run src/core/cli.py chat      # Modo CLI interativo
uv run src/core/cli.py run      # Modo Discord
uv run src/core/cli.py --help   # Todos os comandos
```

## Dependências

### Dependências Externas
- **discord.py** (v2.3+) - Framework Discord API
- **agno** - Agente de IA com suporte OpenAI/Google
- **openai** (v1.30+) - Cliente OpenAI API
- **google-generativeai** (v0.8+) - Cliente Google Gemini API
- **sqlalchemy[asyncio]** (v2.0+) - ORM assíncrono
- **pydantic-settings** (v2.0+) - Settings com Pydantic
- **typer** (v0.9+) - Interface CLI
- **rich** (v13.0+) - Rich terminal interface
- **structlog** (v23.0+) - Logging estruturado
- **questionary** (v2.0+) - Interactive prompts
- **pytest** (v7.4+) - Framework de testes
- **faker** (v20.0+) - Dados de teste realistas
- **freezegun** - Mock de tempo para testes
- **pytest-mock** - Mocks para testes
- **pytest-asyncio** - Suporte async para pytest

### Dependências de Projeto
- **../models/** - Modelos ORM e Pydantic
- **../storage/** - Implementação do Repository Pattern
- **../utils/** - Utils e error hierarchy
- **../config/** - Configuração do sistema
- **../tools/** - Ferramentas externas (MCP)

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

### Debug e Desenvolvimento
```bash
# Modo debug completo
uv run src/core/cli.py --debug

# Chat interativo sem Discord
uv run src/core/cli.py chat

# Ver configuração
uv run src/core/cli.py config show

# Logs em tempo real
uv run src/core/cli.py logs show --lines 50
```

## Integrações

### Model Context Protocol (MCP)
Se habilitado em `config.yaml`, o sistema integra com servidores MCP:
- **Configuração**: `mcp.enabled: true`
- **Servidores**: Definidos em `mcp.servers`
- **Ferramentas**: Disponíveis automaticamente no AgentWrapper
- **Teste**: `uv run src/core/cli.py mcp list`

### Docker Development
```bash
# Build e run
docker build -t botsalinha-core src/core/
docker run -it botsalinha-core chat

# Com Docker Compose
docker-compose up -d
docker-compose logs -f core
```