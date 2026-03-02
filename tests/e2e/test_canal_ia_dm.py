"""E2E tests for chat behavior in guild channels and DM."""

import pytest

from tests.fixtures.bot_wrapper import DiscordBotWrapper, TestScenario
from tests.fixtures.factories import DiscordFactory


@pytest.mark.e2e
@pytest.mark.discord
@pytest.mark.gemini
class TestGuildAndDMFlow:
    """End-to-end tests for supported guild/DM chat flows."""

    @pytest.mark.asyncio
    async def test_guild_ask_flow(self, bot_wrapper: DiscordBotWrapper, fake_legal_question, mock_gemini_api):
        """Guild command flow should respond and persist conversation."""
        user_id = DiscordFactory.user_id()
        guild_id = DiscordFactory.guild_id()
        channel_id = DiscordFactory.channel_id()

        _, messages = await TestScenario.ask_legal_question(
            bot_wrapper,
            fake_legal_question,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

        assert len(messages) > 0
        conversations = await bot_wrapper.repository.get_by_user_and_guild(
            user_id=user_id,
            guild_id=guild_id,
        )
        assert len(conversations) == 1

    @pytest.mark.asyncio
    async def test_dm_ask_flow(self, bot_wrapper: DiscordBotWrapper, fake_legal_question, mock_gemini_api):
        """DM flow should create a DM conversation and respond."""
        user_id = DiscordFactory.user_id()
        dm_channel_id = DiscordFactory.channel_id()

        _, messages = await bot_wrapper.send_command(
            "ask",
            fake_legal_question,
            user_id=user_id,
            guild_id=None,
            channel_id=dm_channel_id,
        )

        assert len(messages) > 0
        dm_conversations = await bot_wrapper.repository.get_by_user_and_guild(
            user_id=user_id,
            guild_id=None,
        )
        assert len(dm_conversations) >= 1

    @pytest.mark.asyncio
    async def test_dm_history_is_maintained(
        self,
        bot_wrapper: DiscordBotWrapper,
        mock_gemini_api,
    ):
        """Multiple DM requests should keep history in the same DM conversation."""
        user_id = DiscordFactory.user_id()
        dm_channel_id = DiscordFactory.channel_id()

        await bot_wrapper.send_command("ask", "Pergunta 1", user_id=user_id, guild_id=None, channel_id=dm_channel_id)
        await bot_wrapper.send_command("ask", "Pergunta 2", user_id=user_id, guild_id=None, channel_id=dm_channel_id)

        dm_conversations = await bot_wrapper.repository.get_by_user_and_guild(
            user_id=user_id,
            guild_id=None,
        )
        assert len(dm_conversations) >= 1

        conversation = dm_conversations[0]
        history = await bot_wrapper.repository.get_conversation_history(conversation.id)
        assert len(history) >= 4


@pytest.mark.e2e
@pytest.mark.discord
@pytest.mark.gemini
class TestCommandCoexistence:
    """Basic commands should remain available while chat flows are active."""

    @pytest.mark.asyncio
    async def test_ping_still_works(self, bot_wrapper: DiscordBotWrapper):
        """Ping should work in regular channel command flow."""
        _, messages = await TestScenario.ping_bot(bot_wrapper)
        assert len(messages) > 0
        assert any("pong" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_clear_works_after_dm_messages(self, bot_wrapper: DiscordBotWrapper, mock_gemini_api):
        """Clear command should work after DM interaction."""
        user_id = DiscordFactory.user_id()
        dm_channel_id = DiscordFactory.channel_id()

        await bot_wrapper.send_command("ask", "Pergunta teste", user_id=user_id, guild_id=None, channel_id=dm_channel_id)
        _, messages = await bot_wrapper.send_command(
            "limpar",
            user_id=user_id,
            guild_id=None,
            channel_id=dm_channel_id,
        )

        assert len(messages) > 0
        assert any("limp" in msg.lower() or "conversa" in msg.lower() for msg in messages)
