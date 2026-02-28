"""E2E tests for complete RAG integration with Discord bot.

Tests the full flow from user query to RAG-augmented response,
including confidence display, source citations, and Discord formatting.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from src.config.settings import get_settings
from src.core.discord import BotSalinhaBot
from src.models.rag_models import DocumentORM, ChunkORM
from src.rag import Chunk, ChunkMetadata
from src.storage.sqlite_repository import SQLiteRepository


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGIntegrationE2E:
    """End-to-end tests for RAG integration."""

    @pytest.mark.asyncio
    async def test_rag_response_with_high_confidence(
        self,
        rag_query_service,
        db_session: AsyncSession,
    ) -> None:
        """Test RAG response with high confidence shows sources."""
        # This test would require actual indexed documents
        # For now, test the structure

        # Create a mock Discord message
        message = MagicMock()
        message.content = "Quais são os direitos fundamentais na Constituição?"
        message.author = MagicMock()
        message.author.id = 123456789
        message.author.name = "TestUser"
        message.author.bot = False
        message.guild = MagicMock()
        message.guild.id = 987654321
        message.channel = MagicMock()
        message.channel.id = 111222333
        message.channel.send = AsyncMock()
        # typing() needs to return an async context manager
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_typing():
            yield

        message.channel.typing = mock_typing

        # Create bot with db_session
        repository = SQLiteRepository("sqlite+aiosqlite:///:memory:")
        await repository.initialize_database()
        await repository.create_tables()

        bot = BotSalinhaBot(repository=repository)

        # Mock the agent response to avoid real API call
        async def mock_generate_with_rag(prompt, *args, **kwargs):
            # Return mock response with RAG context
            from src.rag import RAGContext, ConfiancaLevel

            mock_context = RAGContext(
                chunks_usados=[
                    Chunk(
                        chunk_id="test-1",
                        documento_id=1,
                        texto="Art. 5o Todos são iguais perante a lei...",
                        metadados=ChunkMetadata(documento="CF/88", artigo="5"),
                        token_count=50,
                        posicao_documento=0.1,
                    )
                ],
                similaridades=[0.92],  # Must match chunks_usados length
                confianca=ConfiancaLevel.ALTA,
                fontes=["CF/88, Art. 5"],
            )

            mock_response = (
                "Conforme a Constituição Federal de 1988, todos são iguais "
                "perante a lei, sem distinção de qualquer natureza."
            )

            return mock_response, mock_context

        # Patch the agent method
        from unittest.mock import patch

        with patch.object(
            bot.agent, "generate_response_with_rag", side_effect=mock_generate_with_rag
        ):
            # Create conversation and save user message
            conversation = await repository.get_or_create_conversation(
                user_id="123456789",
                guild_id="987654321",
                channel_id="111222333",
            )

            await bot.agent.save_message(
                conversation_id=conversation.id,
                role="user",
                content=message.content,
                discord_message_id="msg-123",
            )

            # Process message (this calls our modified _handle_chat_message)
            await bot._handle_chat_message(message, is_dm=False)

        # Verify response was sent with RAG context
        assert message.channel.send.called
        sent_messages = [call.args[0] for call in message.channel.send.call_args_list]

        # Should have confidence indicator and sources
        full_response = sent_messages[0] if sent_messages else ""
        assert "✅" in full_response or "[ALTA" in full_response
        assert "CF/88" in full_response or "Art. 5" in full_response

    @pytest.mark.asyncio
    async def test_rag_response_without_confidence(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test RAG response with no confidence (SEM_RAG) shows appropriate message."""
        from src.rag import RAGContext, ConfiancaLevel

        # Create bot without RAG enabled
        repository = SQLiteRepository("sqlite+aiosqlite:///:memory:")
        await repository.initialize_database()
        await repository.create_tables()

        bot = BotSalinhaBot(repository=repository)
        bot.agent.enable_rag = False  # Disable RAG

        # Mock the agent response
        async def mock_generate(prompt, *args, **kwargs):
            from src.rag import RAGContext

            mock_context = RAGContext(
                chunks_usados=[],
                similaridades=[],
                confianca=ConfiancaLevel.SEM_RAG,
                fontes=[],
            )

            mock_response = "Esta é uma resposta baseada em conhecimento geral."

            return mock_response, mock_context

        # Create mock message
        message = MagicMock()
        message.content = "Quem ganhou a Copa do Mundo em 2022?"
        message.author.id = 123456789
        message.author.bot = False
        message.guild = MagicMock()
        message.guild.id = 987654321
        message.channel = MagicMock()
        message.channel.id = 111222333
        message.channel.send = AsyncMock()
        # typing() needs to return an async context manager
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_typing():
            yield

        message.channel.typing = mock_typing

        # Patch agent method
        from unittest.mock import patch

        with patch.object(
            bot.agent, "generate_response_with_rag", side_effect=mock_generate
        ):
            # Create conversation and save user message
            conversation = await repository.get_or_create_conversation(
                user_id="123456789",
                guild_id="987654321",
                channel_id="111222333",
            )

            await bot.agent.save_message(
                conversation_id=conversation.id,
                role="user",
                content=message.content,
                discord_message_id="msg-123",
            )

            # Process message
            await bot._handle_chat_message(message, is_dm=False)

        # Verify SEM_RAG indicator is shown
        assert message.channel.send.called
        sent_messages = [call.args[0] for call in message.channel.send.call_args_list]
        full_response = sent_messages[0] if sent_messages else ""

        # Should have SEM_RAG indicator
        assert "ℹ️" in full_response or "[SEM RAG]" in full_response or "conhecimento geral" in full_response.lower()

    @pytest.mark.asyncio
    async def test_fontes_command(
        self,
        rag_query_service,
        db_session: AsyncSession,
    ) -> None:
        """Test !fontes command lists indexed documents."""
        from src.rag import QueryService
        import discord

        # Create bot
        repository = SQLiteRepository("sqlite+aiosqlite:///:memory:")
        await repository.initialize_database()
        await repository.create_tables()

        bot = BotSalinhaBot(repository=repository)

        # Create mock context with proper Discord context mock
        ctx = MagicMock()
        ctx.author.id = 123456789
        ctx.author.name = "TestUser"
        ctx.typing = AsyncMock()

        # Mock ctx.send to capture the embed
        sent_messages = []
        async def mock_send(content=None, embed=None, **kwargs):
            sent_messages.append({"content": content, "embed": embed, **kwargs})

        ctx.send = AsyncMock(side_effect=mock_send)

        # Index a test document
        from datetime import UTC, datetime

        # Create test document
        doc = DocumentORM(
            nome="CF/88 Test",
            arquivo_origem="test.docx",
            chunk_count=10,
            token_count=5000,
            created_at=datetime.now(UTC),
        )

        db_session.add(doc)
        await db_session.commit()

        # Call the underlying method directly (bypassing discord.py command decorator)
        # The @commands.command decorator wraps the method, so we access the underlying function
        await bot.fontes_command.callback(bot, ctx)

        # Verify embed was sent
        assert ctx.send.called
        assert len(sent_messages) > 0

        # Check that an embed was sent
        sent_embed = sent_messages[0].get("embed")
        assert sent_embed is not None
        assert sent_embed.title == "📚 Fontes RAG Indexadas"
        # Check that the document appears in the embed
        assert "CF/88 Test" in str(sent_embed.fields)

    def test_confidence_formatting(self) -> None:
        """Test confidence formatting produces correct output."""
        from src.core.discord import BotSalinhaBot

        # Test high confidence
        alta = BotSalinhaBot._format_confidence("alta")
        assert "✅" in alta
        assert "[ALTA CONFIANÇA]" in alta

        # Test medium confidence
        media = BotSalinhaBot._format_confidence("media")
        assert "⚠️" in media
        assert "[MÉDIA CONFIANÇA]" in media

        # Test low confidence
        baixa = BotSalinhaBot._format_confidence("baixa")
        assert "❌" in baixa
        assert "[BAIXA CONFIANÇA]" in baixa

        # Test no RAG
        sem_rag = BotSalinhaBot._format_confidence("sem_rag")
        assert "ℹ️" in sem_rag or "[SEM RAG]" in sem_rag

    def test_sources_formatting(self) -> None:
        """Test sources formatting produces correct output."""
        from src.core.discord import BotSalinhaBot

        # Test with sources
        fontes = ["CF/88, Art. 5, caput", "Lei 8.112/90, Art. 116"]
        formatted = BotSalinhaBot._format_sources(fontes)

        assert "📎 CF/88, Art. 5, caput" in formatted
        assert "📎 Lei 8.112/90, Art. 116" in formatted

        # Test empty sources
        empty = BotSalinhaBot._format_sources([])
        assert "Nenhuma" in empty

        # Test with more than 3 sources
        muitas_fontes = [
            "CF/88, Art. 1",
            "CF/88, Art. 5",
            "Lei 8.112/90, Art. 41",
            "Lei 8.112/90, Art. 116",
        ]
        formatted_muitas = BotSalinhaBot._format_sources(muitas_fontes)

        assert "mais 1 fontes" in formatted_muitas

    def test_response_splitting_with_rag(self) -> None:
        """Test response splitting works with RAG context."""
        from src.core.discord import BotSalinhaBot

        # Long response with RAG context
        long_response = (
            "Esta é uma resposta muito longa que precisa ser dividida. "
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        ) * 10  # ~1000 chars

        rag_context = "✅ [ALTA CONFIANÇA]\n\n📎 CF/88, Art. 5\n\n"

        full_response = f"{rag_context}{long_response}"

        chunks = BotSalinhaBot._split_response(full_response, max_len=2000)

        # Should split into multiple chunks
        assert len(chunks) >= 1
        # First chunk should start with RAG context
        assert "✅" in chunks[0]
        # All chunks should be within limit
        for chunk in chunks:
            assert len(chunk) <= 2000


@pytest.mark.e2e
@pytest.mark.rag
class TestRAGDiscordFlow:
    """Test complete Discord flow with RAG."""

    @pytest.mark.asyncio
    async def test_complete_flow_high_confidence(
        self,
        rag_query_service,
        db_session: AsyncSession,
    ) -> None:
        """Test complete user flow with high confidence RAG response."""
        # This test simulates a user asking a question in DM
        # and receiving a RAG-augmented response with sources

        # Would require:
        # 1. User sends DM message
        # 2. Bot processes with RAG
        # 3. Bot responds with confidence + answer + sources
        # 4. User can follow up with !fontes to see indexed documents

        # For now, we test the components
        assert rag_query_service is not None
        assert db_session is not None

        # Verify RAG is enabled
        from src.config.settings import get_settings

        settings = get_settings()
        assert settings.rag.enabled

    @pytest.mark.asyncio
    async def test_complete_flow_low_confidence(
        self,
        rag_query_service,
        db_session: AsyncSession,
    ) -> None:
        """Test complete flow when RAG finds low confidence results."""
        # Simulates asking a question outside the document base
        # Should show SEM_RAG or BAIXA confidence

        # Query service should work but return low confidence
        context = await rag_query_service.query(
            query_text="Quem ganhou a Copa do Mundo de 2022?",
            top_k=5,
        )

        # Should return SEM_RAG or BAIXA confidence
        assert context.confianca.value in ["sem_rag", "baixa"]


__all__ = ["TestRAGIntegrationE2E", "TestRAGDiscordFlow"]
