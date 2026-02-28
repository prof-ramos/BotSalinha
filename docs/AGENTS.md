<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-28 | Updated: 2026-02-28 -->

# AGENTS.md — BotSalinha

<!-- OMC:START -->
<!-- OMC:VERSION:4.4.5 -->
<!-- AGENTS:GENERATED:2026-02-27 -->
<!-- AGENTS:UPDATED:2026-02-27 -->
<!-- AGENTS:GENERATED-BY:writer -->
<!-- AGENTS:PARENT:../AGENTS.md -->
<!-- AGENTS:CONTEXT:bot-salinha-discord-ai -->

## Purpose

Este documento define as convenções e instruções para agentes de IA no BotSalinha. O bot utiliza o framework Agno com OpenAI gpt-4o-mini para fornecer respostas contextualizadas sobre direito brasileiro e preparação para concursos públicos, com histórico persistente e limitação de taxa por usuário.

## Arquivos Chave

| Arquivo | Descrição |
|---------|-----------|
| `prompt/prompt_v1.md` | Prompt padrão ativo (simple) |
| `prompt/prompt_v2.json` | Prompt com exemplos few-shot |
| `prompt/prompt_v3.md` | Prompt avançado chain-of-thought |
| `src/core/agent.py` | Agno AgentWrapper - wrapper de IA |
| `config.yaml` | Configuração do agente e modelo |
| `src/core/discord.py` | Comandos do Discord e eventos |

## Estrutura de Diretórios

| Diretório | Conteúdo |
|-----------|----------|
| `prompt/` | Arquivos de sistema prompts |
| `src/core/` | Lógica central do bot |
| `src/config/` | Configuração e settings |
| `src/models/` | Models de banco de dados |
| `src/utils/` | Utilitários e helpers |
| `tests/` | Suite de testes |

## Instruções para Agentes de IA

### Configuração do Agente
- **Framework**: Agno AgentWrapper
- **Modelo**: OpenAI gpt-4o-mini
- **Histórico**: Pares de mensagens (usuário + assistente)
- **Rate Limiting**: Token bucket por usuário/guild

### Prompts Disponíveis
1. **prompt_v1.md** (default)
   - Estilo: Simples e direto
   - Uso: Conversações básicas e rápidas

2. **prompt_v2.json**
   - Estilo: Few-shot com exemplos
   - Uso: Quando precisamos de exemplos concretos

3. **prompt_v3.md**
   - Estilo: Chain-of-thought avançado
   - Uso: Respostas complexas ou analíticas

### Comandos do Discord
- `!ask <pergunta>` - Perguntar sobre direito/concursos
- `!ping` - Verificação de saúde
- `!ajuda` - Mensagem de ajuda
- `!info` - Informações do bot
- `!limpar` - Limpar histórico do usuário

### Padrões de Conversação
1. **Contexto persistente**: Histórico mantido por usuário
2. **Rate limiting**: Limitação de tokens por janela temporal
3. **Respostas estruturadas**: Formato claro e profissional
4. **Suporte em pt-BR**: Linguagem natural brasileira

## Padrões Comuns

### Erros e Exceções
```python
from src.utils.errors import (
    BotSalinhaError,
    APIError,
    RateLimitError,
    ValidationError,
    DatabaseError,
    ConfigurationError,
    RetryExhaustedError
)
```

### Logging Estruturado
```python
import structlog
log = structlog.get_logger(__name__)

log.info("event_name", user_id=user_id, guild_id=guild_id)
log.error("operation_failed", error=str(e), detail=extra)
```

### Retry Assíncrono
```python
from src.utils.retry import async_retry, AsyncRetryConfig

@async_retry(AsyncRetryConfig(max_attempts=3, base_delay=1.0))
async def call_external_api() -> str:
    ...
```

### Settings Pydantic
```python
from src.config.settings import get_settings

settings = get_settings()
```

### Configuração YAML
```python
from src.config.yaml_config import load_config

config = load_config()
prompt_file = config.prompt.file
```

### banco de Dados
```python
from src.storage.repository import ConversationRepository, MessageRepository
from src.storage.sqlite_repository import SQLiteRepository

repo = SQLiteRepository()
await repo.save_conversation(conversation)
```

## Diretrizes de Desenvolvimento

1. **Sempre use async/await** para I/O operations
2. **Repository pattern** para acesso a dados
3. **Injeção de dependências** para repositories
4. **Pydantic** para validação de dados
5. **structlog** para logging estruturado
6. **Tratamento específico de exceções** - nunca `except:`
7. **Cobertura mínima de testes** 70% (enforcado no CI)

## Variáveis de Ambiente Suportadas

| Variável | Padrão | Obrigatório | Descrição |
|----------|--------|-------------|-----------|
| `DISCORD_BOT_TOKEN` | - | Sim | Token do Discord |
| `OPENAI_API_KEY` | - | Sim | Chave da OpenAI |
| `HISTORY_RUNS` | `3` | Não | Pares de histórico |
| `RATE_LIMIT_REQUESTS` | `10` | Não | Máx. requisições |
| `DATABASE_URL` | `sqlite:///data/botsalinha.db` | Não | Caminho do banco |

## Common Patterns

### Handler de Comando Discord
```python
@commands.command(name="ask")
async def ask_command(self, ctx: commands.Context, *, question: str):
    if not self.rate_limiter.check_rate_limit(ctx.author, ctx.guild):
        await ctx.send("Limite de taxa atingido. Tente novamente mais tarde.")
        return

    try:
        response = await self.agent.generate_response(
            question=question,
            guild_id=ctx.guild.id,
            user_id=ctx.author.id
        )
        await ctx.send(response)
    except APIError as e:
        await ctx.send("Erro ao processar sua pergunta. Tente novamente.")
        log.error("api_error", error=str(e))
```

### Geração de Resposta
```python
async def generate_response(
    self,
    question: str,
    guild_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> str:
    conversation_history = await self.repository.get_conversation_history(
        user_id=user_id,
        guild_id=guild_id,
        limit=self.settings.history_runs
    )

    prompt = self.config.prompt_file

    response = await self.agent.generate(
        message=question,
        history=conversation_history,
        prompt=prompt
    )

    await self.save_message(
        user_id=user_id,
        guild_id=guild_id,
        content=question,
        role="user"
    )

    await self.save_message(
        user_id=user_id,
        guild_id=guild_id,
        content=response,
        role="assistant"
    )

    return response
```

### Testes Unitários
```python
@pytest.mark.unit
async def test_generate_response(self, test_repository, test_settings):
    agent = AgentWrapper(
        repository=test_repository,
        settings=test_settings,
        config=test_config
    )

    response = await agent.generate_response(
        question="Como funciona a Lei Maria da Penha?",
        user_id=123,
        guild_id=456
    )

    assert isinstance(response, str)
    assert len(response) > 0
```

## Considerações de Segurança

1. Nunca expor tokens ou chaves de API no código
2. Validar todas as entradas do usuário
3. Usar limitação de taxa para prevenção de abuse
4. Logs sensíveis filtrados em produção
5. Rate limiting por usuário e guild

## Monitoramento e Logging

- Logs estruturados em JSON ou texto
- Correlation IDs para rastreamento
- Métricas de performance (latência, taxa de erro)
- Alertas para falhas críticas
- Backup automático do banco de dados

## Maintenance Notes

- Atualizar prompts conforme necessário
- Monitorar limites de API da OpenAI
- Atualizar dependências regularmente
- Executar testes pré-commit
- Manter documentação atualizada

<!-- OMC:END -->

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->