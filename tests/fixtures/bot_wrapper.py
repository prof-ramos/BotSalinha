"""
Discord Bot Wrapper for E2E testing.

Provides a clean interface for testing Discord bot interactions
without requiring actual Discord connection.
"""

from contextlib import suppress
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

# Default test constants
DEFAULT_USER_ID = "123456789"
DEFAULT_GUILD_ID = "987654321"
DEFAULT_CHANNEL_ID = "111222333"


class DiscordBotWrapper:
    """
    Wrapper around BotSalinhaBot for testing.

    Provides methods to simulate Discord commands and interactions
    without connecting to the actual Discord API.

    Note: This wrapper directly calls bot command methods rather than
    going through discord.py's command system to avoid complex mocking.
    """

    def __init__(self, repository: Any | None = None):
        """
        Initialize the bot wrapper.

        Args:
            repository: Optional repository instance for dependency injection
        """
        self.repository = repository
        self.bot = None
        self._mock_discord_objects = {}
        self._patches = []
        # Initialize the bot immediately so repository is available
        self._setup_mock_discord()

    def _setup_mock_discord(self):
        """Set up mock Discord objects for testing."""
        from src.core.discord import BotSalinhaBot

        # Create the bot (without initializing the discord.py client)
        self.bot = BotSalinhaBot()

        # Replace repository if provided
        if self.repository:
            self.bot.repository = self.repository
            if self.bot.agent is not None:
                self.bot.agent.repository = self.repository

        # Mock the latency property (used by ping_command)
        patch_latency = patch.object(
            type(self.bot),
            "latency",
            new_callable=PropertyMock,
            return_value=0.05,  # 50ms latency
        )
        patch_latency.start()
        self._patches.append(patch_latency)

    async def _call_command_method(
        self, command_name: str, ctx: MagicMock, *args, **kwargs
    ) -> list[str]:
        """
        Directly call the command method on the bot.

        Args:
            command_name: Name of the command (without prefix)
            ctx: Mock Discord context
            *args: Command arguments
            **kwargs: Additional keyword arguments

        Returns:
            List of sent messages
        """
        # Map command names to their attributes
        # Note: help_command is the method name, but the command is called "ajuda"
        command_attributes = {
            "ask": "ask_command",
            "ping": "ping_command",
            "ajuda": "help_command",  # Method is help_command, command name is ajuda
            "help": "help_command",  # Alias for ajuda
            "limpar": "clear_command",
            "clear": "clear_command",
            "info": "info_command",
        }

        if command_name not in command_attributes:
            raise ValueError(
                f"Command '{command_name}' not found. Available: {list(command_attributes.keys())}"
            )

        attr_name = command_attributes[command_name]

        # Try to get from instance first, then from class
        # (help_command is overridden to None in instance, so we need class attribute)
        command_obj = getattr(self.bot, attr_name, None)
        if command_obj is None:
            command_obj = getattr(type(self.bot), attr_name, None)

        if command_obj is None:
            raise ValueError(
                f"Command object for '{command_name}' (attribute '{attr_name}') is None"
            )

        # Call the command callback directly (pass self=bot)
        # The callback is an unbound function that needs (self, ctx, ...)
        from discord.ext.commands import CommandError

        try:
            await command_obj.callback(self.bot, ctx, *args, **kwargs)
        except CommandError as e:
            # Store error in context for test inspection
            ctx.error = e

        # Retrieve sent messages
        # Handle both positional args (ctx.send("text")) and keyword args (ctx.send(embed=...))
        sent_messages = []
        for call in ctx.send.call_args_list:
            if call[0]:  # Positional args
                sent_messages.append(call[0][0])
            elif "embed" in call[1]:  # Keyword args with embed
                sent_messages.append(f"<Embed: {call[1]['embed']}>")
            else:
                sent_messages.append(str(call[1]))  # Other kwargs

        return sent_messages

    async def send_command(
        self,
        command_name: str,
        *args,
        user_id: str = DEFAULT_USER_ID,
        guild_id: str = DEFAULT_GUILD_ID,
        channel_id: str = DEFAULT_CHANNEL_ID,
        **kwargs,
    ) -> tuple[Any, list[str]]:
        """
        Simulate sending a Discord command.

        Args:
            command_name: Name of the command to execute
            *args: Positional arguments for the command
            user_id: Discord user ID
            guild_id: Discord guild ID
            channel_id: Discord channel ID
            **kwargs: Additional context parameters

        Returns:
            Tuple of (context, sent_messages)
        """
        if self.bot is None:
            self._setup_mock_discord()

        # Create mock context
        ctx = self._create_mock_context(user_id, guild_id, channel_id)

        # Call the command method directly
        sent_messages = await self._call_command_method(command_name, ctx, *args, **kwargs)

        return ctx, sent_messages

    def _create_mock_context(
        self, user_id: str, guild_id: str | None, channel_id: str
    ) -> MagicMock:
        """
        Create a mock Discord command context.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            channel_id: Discord channel ID

        Returns:
            Mocked context object
        """
        ctx = MagicMock()

        # Author setup
        ctx.author.id = int(user_id) if user_id.isdigit() else user_id
        ctx.author.name = f"User_{user_id[:8]}"
        ctx.author.bot = False
        ctx.author.mention = f"<@{user_id}>"

        # Guild setup
        if guild_id:
            ctx.guild.id = int(guild_id) if str(guild_id).isdigit() else guild_id
            ctx.guild.name = f"TestGuild_{str(guild_id)[:8]}"
        else:
            ctx.guild = None

        # Channel setup
        ctx.channel.id = int(channel_id) if str(channel_id).isdigit() else channel_id
        ctx.channel.name = f"test-channel-{channel_id[:6]}"

        # Message setup
        ctx.message.id = 999888777
        ctx.message.content = ""
        ctx.message.author = ctx.author
        ctx.message.guild = ctx.guild
        ctx.message.channel = ctx.channel

        # Async methods
        ctx.typing = MagicMock()  # provides __aenter__/__aexit__ by default
        ctx.send = AsyncMock()
        ctx.reply = AsyncMock()

        # Command setup
        ctx.command = MagicMock()
        ctx.command.name = "test_command"

        return ctx

    async def cleanup(self):
        """Clean up resources after testing."""
        # Stop all patches
        for p in self._patches:
            with suppress(Exception):
                p.stop()
        self._patches.clear()

        # Close the bot
        if self.bot:
            with suppress(Exception):
                await self.bot.close()


class TestScenario:
    """
    Predefined test scenarios for common bot operations.

    Provides static methods that set up and execute common test scenarios.
    """

    @staticmethod
    async def ask_legal_question(
        bot_wrapper: DiscordBotWrapper,
        question: str,
        user_id: str = DEFAULT_USER_ID,
        guild_id: str = DEFAULT_GUILD_ID,
        channel_id: str = DEFAULT_CHANNEL_ID,
    ) -> tuple[Any, list[str]]:
        """
        Scenario: User asks a legal question.

        Args:
            bot_wrapper: Bot wrapper instance
            question: Legal question to ask
            user_id: Discord user ID
            guild_id: Discord guild ID
            channel_id: Discord channel ID

        Returns:
            Tuple of (context, sent_messages)
        """
        return await bot_wrapper.send_command(
            "ask", question, user_id=user_id, guild_id=guild_id, channel_id=channel_id
        )

    @staticmethod
    async def ping_bot(
        bot_wrapper: DiscordBotWrapper,
        user_id: str = DEFAULT_USER_ID,
        guild_id: str = DEFAULT_GUILD_ID,
        channel_id: str = DEFAULT_CHANNEL_ID,
    ) -> tuple[Any, list[str]]:
        """
        Scenario: User pings the bot.

        Args:
            bot_wrapper: Bot wrapper instance
            user_id: Discord user ID
            guild_id: Discord guild ID
            channel_id: Discord channel ID

        Returns:
            Tuple of (context, sent_messages)
        """
        return await bot_wrapper.send_command(
            "ping", user_id=user_id, guild_id=guild_id, channel_id=channel_id
        )

    @staticmethod
    async def clear_conversation(
        bot_wrapper: DiscordBotWrapper,
        user_id: str = DEFAULT_USER_ID,
        guild_id: str = DEFAULT_GUILD_ID,
        channel_id: str = DEFAULT_CHANNEL_ID,
    ) -> tuple[Any, list[str]]:
        """
        Scenario: User clears their conversation history.

        Args:
            bot_wrapper: Bot wrapper instance
            user_id: Discord user ID
            guild_id: Discord guild ID
            channel_id: Discord channel ID

        Returns:
            Tuple of (context, sent_messages)
        """
        return await bot_wrapper.send_command(
            "limpar", user_id=user_id, guild_id=guild_id, channel_id=channel_id
        )


__all__ = [
    "DiscordBotWrapper",
    "TestScenario",
    "DEFAULT_USER_ID",
    "DEFAULT_GUILD_ID",
    "DEFAULT_CHANNEL_ID",
]
