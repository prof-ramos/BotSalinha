"""E2E tests for RAG-related bot commands and formatting helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.discord import BotSalinhaBot
from src.models.rag_models import DocumentORM


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGIntegrationE2E:
    """End-to-end tests for RAG user-facing behavior."""

    @pytest.mark.asyncio
    async def test_fontes_command_sem_documentos(self, db_session: AsyncSession) -> None:
        """!fontes should inform when no RAG sources are indexed."""
        bot = BotSalinhaBot()

        @asynccontextmanager
        async def fake_rag_session():
            yield db_session

        bot._rag_session = fake_rag_session  # type: ignore[method-assign]

        ctx = MagicMock()
        ctx.author.id = 123456789
        ctx.guild = None
        ctx.typing = AsyncMock()
        ctx.send = AsyncMock()

        await bot.fontes_command.callback(bot, ctx)

        assert ctx.send.called
        first_message = ctx.send.call_args_list[0][0][0]
        assert "Nenhuma fonte RAG indexada" in first_message

    @pytest.mark.asyncio
    async def test_fontes_command_com_documentos(self, db_session: AsyncSession) -> None:
        """!fontes should list indexed documents when present."""
        bot = BotSalinhaBot()

        @asynccontextmanager
        async def fake_rag_session():
            yield db_session

        bot._rag_session = fake_rag_session  # type: ignore[method-assign]

        doc = DocumentORM(
            nome="CF/88 Test",
            arquivo_origem="test.docx",
            chunk_count=10,
            token_count=5000,
            created_at=datetime.now(UTC),
        )
        db_session.add(doc)
        await db_session.commit()

        ctx = MagicMock()
        ctx.author.id = 123456789
        ctx.guild = None
        ctx.typing = AsyncMock()
        ctx.send = AsyncMock()

        await bot.fontes_command.callback(bot, ctx)

        assert ctx.send.called
        sent_text = ctx.send.call_args_list[0][0][0]
        assert "Fontes RAG Indexadas" in sent_text
        assert "CF/88 Test" in sent_text


@pytest.mark.e2e
@pytest.mark.rag
class TestRAGDiscordFlow:
    """Smoke tests for RAG-enabled runtime settings."""

    @pytest.mark.asyncio
    async def test_rag_enabled_setting_available(self) -> None:
        """RAG setting should be available to command handlers."""
        from src.config.settings import get_settings

        settings = get_settings()
        assert isinstance(settings.rag.enabled, bool)


__all__ = ["TestRAGIntegrationE2E", "TestRAGDiscordFlow"]
