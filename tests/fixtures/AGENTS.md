<!-- Generated: 2026-02-27 | Updated: 2026-02-27 | Parent: ../../AGENTS.md -->

# AGENTS.md — BotSalinha Test Fixtures

## Purpose

BotSalinha test fixtures provides reusable testing infrastructure for Discord bot testing with realistic Brazilian legal content, Discord mocking helpers, and test data factories. Designed to enable comprehensive unit, integration, and E2E testing without external API dependencies.

### Características Principais
- **Mock Discord completo:** Simulação de IDs, usuários, guildas e canais do Discord
- **Dados brasileiros realistas:** Faker com locale `pt_BR` para conteúdo jurídico
- **Factory pattern:** Classes reutilizáveis para dados de teste consistentes
- **E2E testing helpers:** Interface completa para testar comandos do bot
- **Tempo controlado:** Mock de timestamp com `freezegun`

## Arquivos Chave

| Arquivo | Descrição | Comando |
|---------|-----------|---------|
| `bot_wrapper.py` | Interface completa para testar comandos do bot | `from fixtures import DiscordBotWrapper` |
| `factories.py` | Classes factory para dados de teste realistas | `from fixtures import DiscordFactory, LegalContentFactory` |
| `__init__.py` | Exportações públicas do módulo | `from fixtures import *` |

## Subdiretório

| Diretório | Descrição | Arquivos Importantes |
|-----------|-----------|---------------------|
| `tests/fixtures/` | Infraestrutura de teste central | `DiscordBotWrapper`, `TestScenario`, `Factories` |

## Para Agentes de IA

### Instruções de Trabalho

1. **Entenda o Contexto de Teste:**
   - Testes realizados sem conexão real ao Discord
   - Mock completo da API do Discord usando `unittest.mock`
   - Todos os testes usam SQLite em memória (`sqlite+aiosqlite:///:memory:`)
   - Conteúdo jurídico realista em português brasileiro

2. **Padrões de Teste:**
   - Usar factories para dados consistentes e realistas
   - Sempre mockar APIs externas (Discord, OpenAI, Google)
   - Faker com locale `pt_BR` para nomes e locais brasileiros
   - Async tests com `@pytest.mark.asyncio`
   - Limpeza de recursos após testes

3. **Configuração Importante:**
   - Mock de Discord bot com latência padrão (50ms)
   - Limite de taxa: 10 requests por 60 segundos
   - Histórico de conversa: 3 pares pergunta/resposta
   - Tempo controlável com `freezegun`

### Dependências Essenciais

```python
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from contextlib import suppress
from fixtures import (
    DiscordBotWrapper,
    TestScenario,
    DiscordFactory,
    LegalContentFactory,
    ConversationFactory,
    MessageFactory,
)
```

### Key Mock Objects

```python
# Discord IDs padrão
DEFAULT_USER_ID = "123456789"
DEFAULT_GUILD_ID = "987654321"
DEFAULT_CHANNEL_ID = "111222333"

# Faker com locale pt_BR
fake = Faker("pt_BR")
```

## Mock Discord Pattern

### Estrutura Base

```python
# Criar bot wrapper
bot_wrapper = DiscordBotWrapper(repository=mock_repo)

# Criar contexto de comando
ctx = bot_wrapper._create_mock_context(
    user_id="123456789",
    guild_id="987654321",
    channel_id="111222333"
)

# Enviar comando
ctx, messages = await bot_wrapper.send_command(
    "ask", "Qual é o prazo de prescrição?",
    user_id="123456789"
)
```

### Exemplo Completo

```python
import pytest
from fixtures import DiscordBotWrapper, LegalContentFactory

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_ask_command_legal_response():
    """Test ask command with legal question."""
    # Setup
    bot_wrapper = DiscordBotWrapper()
    question = LegalContentFactory.legal_question()

    # Execute
    ctx, messages = await bot_wrapper.send_command(
        "ask",
        question,
        user_id=DiscordFactory.user_id(),
        guild_id=DiscordFactory.guild_id()
    )

    # Verify
    assert len(messages) == 1
    assert "resposta" in messages[0].lower() or "jurisprudência" in messages[0].lower()

    # Cleanup
    await bot_wrapper.cleanup()
```

## Factory Classes

### DiscordFactory

```python
# Gerar IDs realistas do Discord
user_id = DiscordFactory.user_id()
guild_id = DiscordFactory.guild_id()
channel_id = DiscordFactory.channel_id()

# Gerar nomes e conteúdo realista
username = DiscordFactory.username()
guild_name = DiscordFactory.guild_name()
question = LegalContentFactory.legal_question()
```

### LegalContentFactory

```python
# Banco de perguntas jurídicas realistas
questions = LegalContentFactory.QUESTIONS  # Lista pré-definida
response = LegalContentFactory.legal_response()
complex_response = LegalContentFactory.complex_legal_response()
citation = LegalContentFactory.CITATIONS  # Lista de citações jurídicas
```

### ConversationFactory

```python
# Criar dados de conversação
conversation_data = ConversationFactory.create_conversation_data(
    user_id="123456789",
    guild_id="987654321"
)

# Criar conversação completa com mensagens
conversation_with_messages = ConversationFactory.create_conversation_with_messages(
    message_count=3
)
```

### MessageFactory

```python
# Criar mensagens específicas
user_message = MessageFactory.create_user_message(
    conversation_id="conv_123",
    question="Qual é o conceito de coisa julgada?"
)

assistant_message = MessageFactory.create_assistant_message(
    conversation_id="conv_123",
    response="A coisa julgada..."
)
```

## TestScenarios

### Padrões Comuns

```python
# Pergunta jurídica básica
ctx, messages = await TestScenario.ask_legal_question(
    bot_wrapper,
    "O que é jurisprudência?",
    user_id=DiscordFactory.user_id()
)

# Ping do bot
ctx, messages = await TestScenario.ping_bot(bot_wrapper)

# Limpar conversa
ctx, messages = await TestScenario.clear_conversation(bot_wrapper)

# DM sem guilda
ctx, messages = await TestScenario.ask_question_in_dm(
    bot_wrapper,
    "Pergunta via DM"
)
```

## Testing Patterns

### Teste de Unidade com Factory

```python
import pytest
from fixtures import DiscordFactory, LegalContentFactory

@pytest.mark.unit
def test_discord_factory_realistic_ids():
    """Test Discord ID generation."""
    user_id = DiscordFactory.user_id()
    assert isinstance(user_id, str)
    assert len(user_id) == 18  # Discord ID length
    assert user_id.isdigit()

@pytest.mark.unit
def test_legal_content_factory_questions():
    """Test legal question generation."""
    question = LegalContentFactory.legal_question()
    assert isinstance(question, str)
    assert len(question) > 10
    # Should contain legal keywords
    assert any(word in question.lower() for word in ["prazo", "pena", "direito", "concurso"])

@pytest.mark.unit
def test_conversation_factory_structure():
    """Test conversation data structure."""
    data = ConversationFactory.create_conversation_data()
    assert "user_id" in data
    assert "guild_id" in data
    assert "channel_id" in data
    assert all(isinstance(v, str) for v in data.values())
```

### Teste de Integração

```python
import pytest
from fixtures import DiscordBotWrapper, MessageFactory, ConversationFactory

@pytest.mark.integration
async def test_conversation_flow():
    """Test complete conversation flow."""
    # Setup
    bot_wrapper = DiscordBotWrapper()
    conversation_data = ConversationFactory.create_conversation_data()

    # Simular múltiplas interações
    ctx1, messages1 = await bot_wrapper.send_command(
        "ask",
        "Qual é o conceito de jurisprudência?",
        user_id=conversation_data["user_id"]
    )

    ctx2, messages2 = await bot_wrapper.send_command(
        "ask",
        "Explique a diferença entre crime doloso e culposo",
        user_id=conversation_data["user_id"]
    )

    # Verify conversation state
    assert len(messages1) == 1
    assert len(messages2) == 1
    assert "resposta" in messages1[0].lower()
    assert "resposta" in messages2[0].lower()

    # Cleanup
    await bot_wrapper.cleanup()
```

### Teste de Erro

```python
import pytest
from discord.ext.commands import CommandOnCooldown
from fixtures import DiscordBotWrapper

@pytest.mark.integration
async def test_rate_limit_error_handling():
    """Test rate limiting error handling."""
    # Setup
    bot_wrapper = DiscordBotWrapper()
    error = CommandOnCooldown(
        bucket=MagicMock(),
        retry_after=60.0,
        cooldown=60.0
    )

    # Execute error handler
    ctx, messages = await bot_wrapper.invoke_error_handler(
        "ask",
        error,
        user_id=DiscordFactory.user_id()
    )

    # Verify error message
    assert len(messages) == 1
    assert "aguarde" in messages[0].lower() or "taxa" in messages[0].lower()

    # Cleanup
    await bot_wrapper.cleanup()
```

## Best Practices

### 1. Uso de Factories

```python
# Bom: usar factories para consistência
user_id = DiscordFactory.user_id()
question = LegalContentFactory.legal_question()

# Ruim: gerar manualmente ou hardcode
user_id = "123456789"  # Padrão, não realista
question = "Qual é o prazo?"  # Genérico, não específico
```

### 2. Limpeza de Recursos

```python
# Sempre limpar após teste
bot_wrapper = DiscordBotWrapper()
try:
    # Realizar testes
    pass
finally:
    await bot_wrapper.cleanup()
```

### 3. Isolar Testes

```python
# Cada teste deve ser independente
@pytest.mark.asyncio
async def test_isolated_scenario():
    # Criar nova instância para cada teste
    bot_wrapper = DiscordBotWrapper()

    # Teste específico
    ctx, messages = await TestScenario.ping_bot(bot_wrapper)

    # Limpar
    await bot_wrapper.cleanup()
```

### 4. Naming Conventions

```python
# Seguir padrões de teste
def test_[feature]_[scenario]_[expected]():
    """[descrição do teste]"""
    # Setup
    # Execute
    # Verify
    # Cleanup (se necessário)
```

## Padrões de Comando

### Comandos Disponíveis

| Comando | Método | Test Pattern |
|---------|--------|--------------|
| `!ask` | `ask_command` | `bot_wrapper.send_command("ask", question)` |
| `!ping` | `ping_command` | `bot_wrapper.send_command("ping")` |
| `!ajuda` | `help_command` | `bot_wrapper.send_command("ajuda")` |
| `!limpar` | `clear_command` | `bot_wrapper.send_command("limpar")` |
| `!info` | `info_command` | `bot_wrapper.send_command("info")` |

### Test Template

```python
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_[command]_[scenario]():
    """Test [command] with [scenario]."""
    # Setup
    bot_wrapper = DiscordBotWrapper(repository=mock_repo)

    # Execute
    ctx, messages = await bot_wrapper.send_command(
        "[command]",
        *[args],
        user_id=DiscordFactory.user_id(),
        guild_id=DiscordFactory.guild_id()
    )

    # Verify
    assert len(messages) == expected_count
    assert expected_condition in messages[0]

    # Cleanup
    await bot_wrapper.cleanup()
```

## Erros Comuns

### 1. Esquecer de limpar

```python
# Ruim: sem cleanup
bot_wrapper = DiscordBotWrapper()
# test code...
# Recursos não liberados

# Bom: com cleanup
bot_wrapper = DiscordBotWrapper()
try:
    # test code...
finally:
    await bot_wrapper.cleanup()
```

### 2. Usar IDs hardcode

```python
# Ruim: IDs não realistas
user_id = "1"

# Bom: usar factory
user_id = DiscordFactory.user_id()
```

### 3. Não mockar APIs externas

```python
# Ruim: chamar API real
response = await openai.ChatCompletion.create(...)

# Bom: mockar completamente
mock_openai.return_value = mocked_response
```

## Extensão e Customização

### Adicionar Novos Factories

```python
# Criar nova factory específica
class SpecificLegalFactory:
    @staticmethod
    def constitutional_question() -> str:
        return fake.sentence(ext_word_list=["constituição", "direitos", "fundamentais"])

# Adicionar exports
__all__.append("SpecificLegalFactory")
```

### Adicionar Novos TestScenarios

```python
class CustomScenario:
    @staticmethod
    async def complex_conversation(bot_wrapper, question_count=3):
        """Simulate complex conversation with multiple questions."""
        messages = []
        for i in range(question_count):
            ctx, msg = await TestScenario.ask_legal_question(
                bot_wrapper,
                f"Question {i+1} about {fake.random_element(['constituição', 'penal', 'civil'])}"
            )
            messages.extend(msg)
        return ctx, messages
```

## Performance Considerations

- Usar fixtures pytest para dados compartilhados
- Mockar tudo que não for essencial para o teste
- Limpar recursos após cada teste
- Evitar testes lentos (usar markers como `@pytest.mark.slow`)

## Debugging

Para depurar testes:

```python
# Habilitar logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Verificar mensagens enviadas
print("Messages sent:", messages)
print("Context attributes:", vars(ctx))

# Verificar estado do bot
print("Bot repository:", bot_wrapper.bot.repository)
```

---

*Este arquivo foi gerado para ajudar agentes de IA a compreender e usar a infraestrutura de testes do BotSalinha.*