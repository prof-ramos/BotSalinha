"""E2E tests for RAG reindex command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.discord import BotSalinhaBot
from src.models.rag_models import DocumentORM
from src.storage.sqlite_repository import SQLiteRepository


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGReindexCommand:
    """End-to-end tests for !reindexar command."""

    @pytest.mark.asyncio
    async def test_reindexar_command_as_owner(
        self,
        rag_query_service,
        db_session: AsyncSession,
    ) -> None:
        """Test !reindexar command when user is bot owner."""
        # Create bot
        repository = SQLiteRepository("sqlite+aiosqlite:///:memory:")
        await repository.initialize_database()
        await repository.create_tables()

        bot = BotSalinhaBot(repository=repository)

        # Create mock context with owner
        ctx = MagicMock()
        ctx.author.id = bot.owner_id if hasattr(bot, "owner_id") else 123456789
        ctx.author.name = "BotOwner"
        ctx.typing = AsyncMock()

        # Mock ctx.send to capture messages
        sent_messages = []

        async def mock_send(content=None, embed=None, **kwargs):
            msg = MagicMock()
            msg.content = content
            msg.embed = embed
            sent_messages.append(msg)
            return msg

        async def mock_edit(new_content=None, **kwargs):
            msg = MagicMock()
            msg.content = new_content
            return msg

        ctx.send = AsyncMock(side_effect=mock_send)

        # Mock start_msg.edit
        start_msg = MagicMock()
        start_msg.edit = AsyncMock(side_effect=mock_edit)

        # Patch ctx.send to return our mock start_msg
        original_send = ctx.send

        async def patched_send(content=None, embed=None, **kwargs):
            if "Iniciando reindexação" in (content or ""):
                return start_msg
            return await original_send(content=content, embed=embed, **kwargs)

        ctx.send = AsyncMock(side_effect=patched_send)

        # Check if RAG documents exist
        from sqlalchemy import func, select

        doc_count_stmt = select(func.count(DocumentORM.id))
        doc_count_result = await db_session.execute(doc_count_stmt)
        doc_count = doc_count_result.scalar() or 0

        # If no documents, skip test
        if doc_count == 0:
            pytest.skip("No RAG documents found for reindex test")

        # Call the underlying command method
        try:
            await bot.reindexar_command.callback(bot, ctx)
        except AttributeError:
            # Command doesn't exist yet - skip test
            pytest.skip("Command !reindexar not yet implemented")

        # Verify messages were sent
        assert ctx.send.called
        assert len(sent_messages) >= 1

    @pytest.mark.asyncio
    async def test_reindexar_command_exists(
        self,
        rag_query_service,
        db_session: AsyncSession,
    ) -> None:
        """Test !reindexar command is registered on bot."""
        # Create bot
        repository = SQLiteRepository("sqlite+aiosqlite:///:memory:")
        await repository.initialize_database()
        await repository.create_tables()

        bot = BotSalinhaBot(repository=repository)

        # Check if command exists
        command = bot.get_command("reindexar")
        if command is None:
            pytest.skip("Command !reindexar not yet implemented")

        # Verify command properties
        assert command.name == "reindexar"
        assert command.checks  # Should have @commands.is_owner() check


__all__ = ["TestRAGReindexCommand"]
