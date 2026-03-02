"""E2E tests for RAG reindex command."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.discord import BotSalinhaBot


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGReindexCommand:
    """End-to-end tests for !reindexar command."""

    @pytest.mark.asyncio
    async def test_reindexar_command_as_owner(self, db_session: AsyncSession) -> None:
        """!reindexar completo should run and report completion for owner."""
        bot = BotSalinhaBot()

        @asynccontextmanager
        async def fake_rag_session():
            yield db_session

        bot._rag_session = fake_rag_session  # type: ignore[method-assign]
        bot.is_owner = AsyncMock(return_value=True)  # type: ignore[method-assign]

        ctx = MagicMock()
        ctx.author.id = 123456789
        ctx.guild = None
        # NOTE: discord.py uses `await ctx.typing()` (not `async with ctx.typing():`)
        # AsyncMock() is correct for this pattern - see discord.py:243,331,415
        ctx.typing = AsyncMock()
        ctx.send = AsyncMock()

        fake_stats = {
            "documents_count": 1,
            "chunks_count": 3,
            "duration_seconds": 0.12,
        }

        with patch("src.core.discord.IngestionService.reindex", new=AsyncMock(return_value=fake_stats)):
            await bot.reindexar_command.callback(bot, ctx, "completo")

        assert ctx.send.called
        messages = [call[0][0] for call in ctx.send.call_args_list if call[0]]
        assert any("Reindexação RAG concluída" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_reindexar_command_exists(self) -> None:
        """!reindexar command should be registered on bot."""
        bot = BotSalinhaBot()

        assert hasattr(bot, "reindexar_command")
        command_obj = bot.reindexar_command
        assert callable(command_obj.callback)


__all__ = ["TestRAGReindexCommand"]
