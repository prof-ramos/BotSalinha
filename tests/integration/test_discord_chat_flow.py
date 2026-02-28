"""
Integration tests for Discord chat flow (IA channel and DM).

Tests the complete flow from message to response with database integration.
These tests use in-memory SQLite database and mocked Discord API.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest

from src.models.message import MessageRole


@pytest.mark.integration
@pytest.mark.discord
@pytest.mark.database
class TestCanalIAFlow:
    """Integration tests for IA channel chat flow."""

    async def test_complete_flow_in_canal_ia(
        self, conversation_repository, mock_ai_response, test_settings, monkeypatch
    ):
        """Complete flow: message in IA channel -> response -> saved to database."""
        from src.config.settings import get_settings
        from src.core.discord import BotSalinhaBot

        # Arrange - Configure IA channel
        canal_ia_id = "123456789"
        monkeypatch.setenv("DISCORD__CANAL_IA_ID", canal_ia_id)
        get_settings.cache_clear()
        new_settings = get_settings()

        bot = BotSalinhaBot(repository=conversation_repository)

        # Create mock message
        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.author.name = "TestUser"
        message.content = "Qual é o prazo de prescrição trabalhista?"
        message.id = 999888777
        message.guild = MagicMock()
        message.guild.id = 987654321
        message.channel.id = int(canal_ia_id)
        message.channel.send = AsyncMock()
        message.channel.typing = MagicMock()
        message.channel.typing.return_value.__aenter__ = AsyncMock()
        message.channel.typing.return_value.__aexit__ = AsyncMock()

        # Act
        with (
            patch("src.core.discord.settings", new_settings),
            patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user,
        ):
            mock_user.return_value.id = 12345
            await bot.on_message(message)

        # Assert - Response was sent
        message.channel.send.assert_called()
        response_sent = message.channel.send.call_args[0][0]
        assert "legalidade" in response_sent.lower() or "constituição" in response_sent.lower()

        # Assert - Conversation was created in database
        conversations = await conversation_repository.get_by_user_and_guild(
            user_id=str(message.author.id), guild_id=str(message.guild.id)
        )
        assert len(conversations) == 1
        assert conversations[0].channel_id == canal_ia_id

        # Assert - Messages were saved
        conversation = conversations[0]
        messages = await conversation_repository.get_conversation_history(conversation.id)
        assert len(messages) >= 2  # At least user + assistant

        # Check roles
        roles = [msg["role"] for msg in messages]
        assert MessageRole.USER in roles
        assert MessageRole.ASSISTANT in roles


@pytest.mark.integration
@pytest.mark.discord
@pytest.mark.database
class TestDMFlow:
    """Integration tests for DM chat flow."""

    async def test_complete_flow_in_dm(
        self, conversation_repository, mock_ai_response, test_settings
    ):
        """Complete flow: DM message -> response -> saved to database."""
        from src.core.discord import BotSalinhaBot

        # Arrange
        bot = BotSalinhaBot(repository=conversation_repository)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.author.name = "TestUser"
        message.content = "O que é crime doloso?"
        message.id = 999888777
        message.guild = None  # DM has no guild
        message.channel = MagicMock(spec=discord.DMChannel)
        message.channel.id = 555666777
        message.channel.send = AsyncMock()
        message.channel.typing = MagicMock()
        message.channel.typing.return_value.__aenter__ = AsyncMock()
        message.channel.typing.return_value.__aexit__ = AsyncMock()

        # Act
        with patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user:
            mock_user.return_value.id = 12345
            await bot.on_message(message)

        # Assert - Response was sent
        message.channel.send.assert_called()
        response_sent = message.channel.send.call_args[0][0]
        assert len(response_sent) > 20  # Should have meaningful content

        # Assert - Conversation was created with guild_id=None for DM
        conversations = await conversation_repository.get_dm_conversations(
            user_id=str(message.author.id)
        )
        assert len(conversations) == 1
        assert conversations[0].guild_id is None

        # Assert - Messages were saved
        conversation = conversations[0]
        messages = await conversation_repository.get_conversation_history(conversation.id)
        assert len(messages) >= 2


@pytest.mark.integration
@pytest.mark.discord
@pytest.mark.database
class TestRateLimitingIntegration:
    """Integration tests for rate limiting in chat flow."""

    async def test_rate_limiting_is_applied(
        self, conversation_repository, test_settings, rate_limiter
    ):
        """Rate limiter should be applied to chat messages."""
        from src.core.discord import BotSalinhaBot

        # Arrange - Set strict rate limit for testing
        rate_limiter.requests = 2
        rate_limiter.window_seconds = 60

        bot = BotSalinhaBot(repository=conversation_repository)

        # Create mock message
        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "Pergunta teste"
        message.id = 999888777
        message.guild = None
        message.channel = MagicMock(spec=discord.DMChannel)
        message.channel.id = 123456789
        message.channel.send = AsyncMock()

        # Act - Send multiple messages rapidly
        with (
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="Resposta teste"),
            ),
            patch("src.core.discord.rate_limiter", rate_limiter),
        ):
            # First two should succeed
            message.id = 1
            with patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user:
                mock_user.return_value.id = 12345
                await bot.on_message(message)
            message.id = 2
            with patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user:
                mock_user.return_value.id = 12345
                await bot.on_message(message)

            # Third should hit rate limit
            message.id = 3
            with patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user:
                mock_user.return_value.id = 12345
                await bot.on_message(message)

        # Assert - Rate limit message should be sent
        message.channel.send.assert_called()
        # Check if any call contains rate limit message
        rate_limit_sent = any(
            "limite" in str(call).lower() or "excedeu" in str(call).lower()
            for call in message.channel.send.call_args_list
        )
        assert rate_limit_sent


@pytest.mark.integration
@pytest.mark.discord
@pytest.mark.database
class TestCommandsStillWork:
    """Integration tests to ensure commands continue to work."""

    async def test_commands_work_in_normal_channels(self, conversation_repository, test_settings):
        """Commands should still work in normal channels (prefix-based)."""
        from src.core.discord import BotSalinhaBot

        # Arrange
        bot = BotSalinhaBot(repository=conversation_repository)

        ctx = MagicMock()
        ctx.author.bot = False
        ctx.author.id = 111222333
        ctx.guild = MagicMock()
        ctx.guild.id = 987654321
        ctx.channel.id = 111222333
        ctx.message = MagicMock()
        ctx.message.content = "!ping"
        ctx.message.id = 999888777
        ctx.message.author = ctx.author
        ctx.message.guild = ctx.guild
        ctx.message.channel = ctx.channel
        ctx.send = AsyncMock()

        # Act - Invoke ping command directly
        with patch.object(BotSalinhaBot, "latency", new_callable=PropertyMock) as mock_latency:
            mock_latency.return_value = 0.05
            await bot.ping_command.callback(bot, ctx)

        # Assert
        ctx.send.assert_called_once()
        response = ctx.send.call_args[0][0]
        assert "pong" in response.lower() or "ms" in response.lower()

    async def test_clear_command_works_with_dm_conversations(
        self, conversation_repository, test_settings
    ):
        """Clear command should work for DM conversations."""
        from src.core.discord import BotSalinhaBot

        # Arrange - Create a DM conversation
        bot = BotSalinhaBot(repository=conversation_repository)

        user_id = "111222333"
        channel_id = "555666777"

        conversation = await conversation_repository.get_or_create_conversation(
            user_id=user_id, guild_id=None, channel_id=channel_id
        )

        # Add some messages
        from src.models.message import MessageCreate

        await conversation_repository.create_message(
            MessageCreate(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="Test message",
            )
        )

        # Verify conversation exists
        conversations = await conversation_repository.get_dm_conversations(user_id=user_id)
        assert len(conversations) == 1

        # Create mock context for clear command
        ctx = MagicMock()
        ctx.author.id = user_id
        ctx.guild = None
        ctx.channel.id = channel_id
        ctx.send = AsyncMock()

        # Act - Run clear command
        await bot.clear_command.callback(bot, ctx)

        # Assert
        ctx.send.assert_called()
        response = ctx.send.call_args[0][0]
        assert "limpo" in response.lower() or "sucesso" in response.lower()

        # Verify conversation was deleted
        conversations_after = await conversation_repository.get_dm_conversations(user_id=user_id)
        assert len(conversations_after) == 0


@pytest.mark.integration
@pytest.mark.discord
@pytest.mark.database
class TestConversationHistory:
    """Integration tests for conversation history persistence."""

    async def test_history_is_maintained_between_messages(
        self, conversation_repository, mock_ai_response, test_settings
    ):
        """Conversation history should persist across multiple messages."""
        from src.core.discord import BotSalinhaBot

        # Arrange
        bot = BotSalinhaBot(repository=conversation_repository)

        user_id = "111222333"
        channel_id = "555666777"

        # First message
        message1 = MagicMock()
        message1.author.bot = False
        message1.author.id = user_id
        message1.content = "Qual é a base de cálculo do ICMS?"
        message1.id = 1
        message1.guild = None
        message1.channel = MagicMock(spec=discord.DMChannel)
        message1.channel.id = channel_id
        message1.channel.send = AsyncMock()
        message1.channel.typing = MagicMock()
        message1.channel.typing.return_value.__aenter__ = AsyncMock()
        message1.channel.typing.return_value.__aexit__ = AsyncMock()

        # Act - Send first message
        with (
            patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user,
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="Resposta 1 sobre ICMS"),
            ),
        ):
            mock_user.return_value.id = 12345
            await bot.on_message(message1)

        # Second message (follow-up)
        message2 = MagicMock()
        message2.author.bot = False
        message2.author.id = user_id
        message2.content = "E para o IPI?"  # Follow-up question
        message2.id = 2
        message2.guild = None
        message2.channel = MagicMock(spec=discord.DMChannel)
        message2.channel.id = channel_id
        message2.channel.send = AsyncMock()
        message2.channel.typing = MagicMock()
        message2.channel.typing.return_value.__aenter__ = AsyncMock()
        message2.channel.typing.return_value.__aexit__ = AsyncMock()

        # Act - Send second message
        with (
            patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user,
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="Resposta 2 sobre IPI"),
            ),
        ):
            mock_user.return_value.id = 12345
            await bot.on_message(message2)

        # Assert - Same conversation should contain both exchanges
        conversations = await conversation_repository.get_dm_conversations(user_id=str(user_id))
        assert len(conversations) == 1

        conversation = conversations[0]
        messages = await conversation_repository.get_conversation_history(conversation.id)

        # Should have 4 messages: user1, assistant1, user2, assistant2
        assert len(messages) >= 4

        # Verify content
        contents = [msg["content"] for msg in messages]
        assert any("ICMS" in c for c in contents)
        assert any("IPI" in c for c in contents)
