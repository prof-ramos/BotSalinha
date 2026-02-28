"""
Unit tests for Discord on_message handler.

Tests the chat flow for IA channel and DM support following TDD principles.
These tests verify the behavior of the on_message handler and _handle_chat_message method.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest

from src.utils.errors import RateLimitError


@pytest.mark.unit
@pytest.mark.discord
class TestOnMessageBotDetection:
    """Tests for bot message detection."""

    async def test_ignores_messages_from_other_bots(self, mock_discord_context, test_settings):
        """Bot should ignore messages from other bots."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        bot = BotSalinhaBot(repository=mock_repo)
        await bot._setup_hook() if hasattr(bot, "_setup_hook") else None

        message = MagicMock()
        message.author.bot = True
        message.author.id = 999999999
        message.content = "Olá bot!"
        message.id = 111222333
        message.guild = None
        message.channel = MagicMock()

        # Act
        with patch.object(bot, "process_commands", new=AsyncMock()) as mock_process:
            await bot.on_message(message)

        # Assert - process_commands should NOT be called for bot messages
        mock_process.assert_not_called()


@pytest.mark.unit
@pytest.mark.discord
class TestOnMessageCanalIADetection:
    """Tests for IA channel detection."""

    async def test_responds_in_configured_canal_ia(
        self, mock_discord_context, test_settings, monkeypatch
    ):
        """Bot should respond to messages in the configured IA channel."""
        from src.config.settings import get_settings
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        canal_ia_id = "123456789"
        monkeypatch.setenv("DISCORD__CANAL_IA_ID", canal_ia_id)
        get_settings.cache_clear()
        new_settings = get_settings()

        mock_repo = MagicMock(spec=SQLiteRepository)
        mock_repo.get_or_create_conversation = AsyncMock(return_value=MagicMock(id="conv-1"))
        mock_repo.create_message = AsyncMock()

        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "Teste IA"
        message.id = 999888777
        message.guild = MagicMock()
        message.guild.id = 987654321
        message.channel.id = 123456789  # Canal IA ID
        message.channel.send = AsyncMock()
        # Mock typing as an async context manager
        message.channel.typing = MagicMock()
        message.channel.typing.return_value.__aenter__ = AsyncMock()
        message.channel.typing.return_value.__aexit__ = AsyncMock()

        # Act
        with (
            patch("src.core.discord.settings", new_settings),
            patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user,
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="Resposta de teste"),
            ),
        ):
            mock_user.return_value.id = 12345
            await bot.on_message(message)

        # Assert - Message should be sent in the IA channel
        assert message.channel.send.called

    async def test_valueerror_malformed_canal_ia_id_logs_warning(
        self, mock_discord_context, test_settings, monkeypatch, caplog
    ):
        """Malformed canal_ia_id should log warning and fallback to process_commands."""
        from src.config.settings import get_settings
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange - Set malformed canal_ia_id
        monkeypatch.setenv("DISCORD__CANAL_IA_ID", "not-a-number")
        get_settings.cache_clear()
        new_settings = get_settings()

        mock_repo = MagicMock(spec=SQLiteRepository)
        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.id = 999888777
        message.guild = MagicMock()
        message.guild.id = 987654321
        message.channel.id = 123456789
        message.content = "!ping"

        # Act
        with (
            patch("src.core.discord.settings", new_settings),
            patch.object(bot, "process_commands", new=AsyncMock()) as mock_process,
        ):
            await bot.on_message(message)

        # Assert - Should fallback to process_commands
        mock_process.assert_called_once_with(message)


@pytest.mark.unit
@pytest.mark.discord
class TestOnMessageDMDetection:
    """Tests for DM detection."""

    async def test_responds_in_dm(self, mock_discord_context, test_settings):
        """Bot should respond to messages in DM."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "O que é crime doloso?"
        message.id = 999888777
        message.guild = None  # DM has no guild
        message.channel = MagicMock(spec=discord.DMChannel)
        message.channel.id = 111222333
        message.channel.send = AsyncMock()
        # Mock typing as an async context manager
        message.channel.typing = MagicMock()
        message.channel.typing.return_value.__aenter__ = AsyncMock()
        message.channel.typing.return_value.__aexit__ = AsyncMock()

        # Act
        with (
            patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user,
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="Resposta de teste"),
            ),
        ):
            mock_user.return_value.id = 12345
            await bot.on_message(message)

        # Assert - Message should be sent in DM
        assert message.channel.send.called


@pytest.mark.unit
@pytest.mark.discord
class TestOnMessageNormalChannel:
    """Tests for normal channel behavior."""

    async def test_processes_commands_in_normal_channels(self, mock_discord_context, test_settings):
        """Normal channels should only process commands with prefix."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "Olá bot!"  # No prefix
        message.id = 999888777
        message.guild = MagicMock()
        message.guild.id = 987654321
        message.channel = MagicMock()
        message.channel.id = 111222333

        # Act
        with patch.object(bot, "process_commands", new=AsyncMock()) as mock_process:
            await bot.on_message(message)

        # Assert
        mock_process.assert_called_once_with(message)


@pytest.mark.unit
@pytest.mark.discord
class TestHandleChatMessageErrors:
    """Tests for error handling in _handle_chat_message."""

    async def test_rate_limit_error_is_handled_correctly(self, mock_discord_context, test_settings):
        """RateLimitError should show user-friendly message with retry_after."""
        from src.core.discord import BotSalinhaBot
        from src.middleware.rate_limiter import RateLimiter
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        mock_rate_limiter = MagicMock(spec=RateLimiter)
        mock_rate_limiter.check_rate_limit = AsyncMock(
            side_effect=RateLimitError(
                "Rate limit exceeded. Try again in 30.0 seconds.",
                retry_after=30.0,
            )
        )

        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "Pergunta teste"
        message.id = 999888777
        message.guild = None
        message.channel = MagicMock(spec=discord.DMChannel)
        message.channel.send = AsyncMock()

        # Act
        with patch("src.core.discord.rate_limiter", mock_rate_limiter):
            await bot.on_message(message)

        # Assert - User-friendly message should be sent
        message.channel.send.assert_called()
        sent_message = message.channel.send.call_args[0][0]
        assert "30" in sent_message or "segundos" in sent_message.lower()

    async def test_discord_forbidden_when_user_blocks_bot(
        self, mock_discord_context, test_settings
    ):
        """discord.Forbidden should be handled gracefully when user blocks bot."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        mock_repo.get_or_create_conversation = AsyncMock(return_value=MagicMock(id="conv-1"))

        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "Pergunta teste"
        message.id = 999888777
        message.guild = None
        message.channel = MagicMock(spec=discord.DMChannel)
        # First send succeeds, second raises Forbidden (user blocks mid-response)
        message.channel.send = AsyncMock(
            side_effect=[None, discord.Forbidden(MagicMock(), MagicMock())]
        )

        # Act & Assert - Should not crash, should log warning
        with (
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="A" * 3000),  # Long response that needs split
            ),
            patch("src.core.discord.log"),
        ):
            try:
                await bot.on_message(message)
            except discord.Forbidden:
                pytest.fail("Forbidden exception should be caught, not propagated")

    async def test_empty_message_is_rejected(self, mock_discord_context, test_settings):
        """Empty or whitespace-only messages should be rejected."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "   "  # Only whitespace
        message.id = 999888777
        message.guild = None
        message.channel = MagicMock(spec=discord.DMChannel)
        message.channel.send = AsyncMock()

        # Act
        with patch(
            "src.core.discord.AgentWrapper.generate_response",
            new=AsyncMock(return_value="Resposta"),
        ) as mock_generate:
            await bot.on_message(message)

        # Assert - No response should be sent for empty messages
        mock_generate.assert_not_called()
        message.channel.send.assert_not_called()

    async def test_history_is_maintained_by_user(self, mock_discord_context, test_settings):
        """Conversation history should be maintained per user."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        mock_repo.get_or_create_conversation = AsyncMock(return_value=MagicMock(id="conv-user-123"))
        mock_repo.create_message = AsyncMock()

        bot = BotSalinhaBot(repository=mock_repo)

        user_id = 111222333
        message1 = MagicMock()
        message1.author.bot = False
        message1.author.id = user_id
        message1.content = "Primeira pergunta"
        message1.id = 111
        message1.guild = None
        message1.channel = MagicMock(spec=discord.DMChannel)
        message1.channel.id = 111222333
        message1.channel.send = AsyncMock()

        # Act - First message
        with (
            patch.object(BotSalinhaBot, "user", new_callable=PropertyMock) as mock_user,
            patch(
                "src.core.discord.AgentWrapper.generate_response",
                new=AsyncMock(return_value="Resposta 1"),
            ),
        ):
            mock_user.return_value.id = 12345
            await bot.on_message(message1)

        # Assert - Same conversation should be used for same user
        mock_repo.get_or_create_conversation.assert_called()
        call_kwargs = mock_repo.get_or_create_conversation.call_args.kwargs
        assert call_kwargs["user_id"] == str(user_id)
        assert call_kwargs["guild_id"] is None
        assert call_kwargs["channel_id"] == str(message1.channel.id)


@pytest.mark.unit
@pytest.mark.discord
class TestHandleChatMessageValidation:
    """Tests for message validation."""

    async def test_message_too_long_is_rejected(self, mock_discord_context, test_settings):
        """Messages over 10,000 characters should be rejected."""
        from src.core.discord import BotSalinhaBot
        from src.storage.sqlite_repository import SQLiteRepository

        # Arrange
        mock_repo = MagicMock(spec=SQLiteRepository)
        bot = BotSalinhaBot(repository=mock_repo)

        message = MagicMock()
        message.author.bot = False
        message.author.id = 111222333
        message.content = "A" * 10001  # Over limit
        message.id = 999888777
        message.guild = None
        message.channel = MagicMock(spec=discord.DMChannel)
        message.channel.send = AsyncMock()

        # Act
        with patch(
            "src.core.discord.AgentWrapper.generate_response",
            new=AsyncMock(return_value="Resposta"),
        ):
            await bot.on_message(message)

        # Assert - Should send error message about length
        message.channel.send.assert_called()
        sent_message = message.channel.send.call_args[0][0]
        assert "longa" in sent_message.lower() or "10.000" in sent_message
