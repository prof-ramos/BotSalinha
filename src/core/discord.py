"""
Discord bot implementation using discord.py.

Implements the main bot with command handling, error handling,
and integration with the AI agent.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import discord
import structlog
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config.settings import settings
from ..models.rag_models import DocumentORM
from ..rag.services.embedding_service import EmbeddingService
from ..rag.services.ingestion_service import IngestionService
from ..services.conversation_service import ConversationService
from ..storage.repository_factory import get_configured_repository
from ..utils.errors import RateLimitError as BotRateLimitError
from ..utils.log_events import LogEvents
from ..utils.logger import bind_request_context
from ..utils.message_splitter import MessageSplitter
from .agent import AgentWrapper

log = structlog.get_logger()

# Discord message limit
DISCORD_MAX_MESSAGE_LENGTH = 2000

# Help text template
HELP_TEXT_TEMPLATE = """
**BotSalinha** - Assistente de Direito e Concursos

**Comandos disponíveis:**
• `{prefix}ask <pergunta>` - Faça uma pergunta sobre direito ou concursos
• `{prefix}ping` - Verifique a latência do bot
• `{prefix}ajuda` - Mostra esta mensagem de ajuda
• `{prefix}fontes` - Lista documentos indexados no RAG
• `{prefix}reindexar [completo|incremental]` - Reindexa o RAG (owner)

**Sobre:**
Sou um assistente especializado em direito brasileiro e concursos públicos.
Posso ajudar com dúvidas sobre legislação, jurisprudência, e preparação para concursos.

**Limitações:**
• Mantenho contexto de até {history_runs} mensagens anteriores
• Respeito limites de taxa para uso justo

Desenvolvido com ❤️ usando Agno + Gemini
"""


class BotSalinhaBot(commands.Bot):
    """
    Main Discord bot class for BotSalinha.

    Implements command handling with proper error handling,
    rate limiting, and AI integration.
    """

    def __init__(self) -> None:
        """Initialize the bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.dm_messages = True

        super().__init__(
            command_prefix=settings.discord.command_prefix,
            intents=intents,
            help_command=None,
        )

        # Initialize components - use configured repository (Convex or SQLite)
        self.repository = get_configured_repository()
        self.agent = AgentWrapper(repository=self.repository)
        self.message_splitter = MessageSplitter(max_length=DISCORD_MAX_MESSAGE_LENGTH)

        # Initialize service layer
        self.conversation_service = ConversationService(
            conversation_repo=self.repository,
            message_repo=self.repository,
            agent=self.agent,
            message_splitter=self.message_splitter,
        )

        self._ready_event = asyncio.Event()

        log.info("discord_bot_initialized", prefix=settings.discord.command_prefix)

    @staticmethod
    def _resolve_async_database_url() -> str:
        """Retorna URL de banco compatível com SQLAlchemy async."""
        db_url = str(settings.database.url)
        if db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return db_url

    @staticmethod
    def _resolve_rag_documents_dir() -> Path:
        """Retorna diretório padrão de documentos DOCX do RAG."""
        return Path(__file__).resolve().parents[2] / "docs" / "plans" / "RAG"

    @asynccontextmanager
    async def _rag_session(self) -> AsyncSession:
        """Cria sessão isolada para operações RAG administrativas."""
        db_url = self._resolve_async_database_url()
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite+") else {}
        engine = create_async_engine(
            db_url,
            echo=settings.database.echo,
            connect_args=connect_args,
        )
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as session:
                yield session
        finally:
            await engine.dispose()

    async def setup_hook(self) -> None:
        """Called when the bot is setting up."""
        # Only initialize database for SQLite (Convex doesn't need this)
        if hasattr(self.repository, 'initialize_database'):
            await self.repository.initialize_database()
            await self.repository.create_tables()
            log.info("sqlite_database_initialized")
        else:
            log.info("using_cloud_backend_no_init_needed")

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        self._ready_event.set()

        guild_count = len(self.guilds)
        user_count = sum(g.member_count or 0 for g in self.guilds)
        self._ready_event.set()

        guild_count = len(self.guilds)
        user_count = sum(g.member_count or 0 for g in self.guilds)

        log.info(
            "bot_ready",
            bot_id=str(self.user.id),
            bot_name=self.user.name,
            guild_count=guild_count,
            user_count=user_count,
        )

    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming messages.

        Args:
            message: Discord message
        """
        # Ignore messages from bots
        if message.author.bot:
            return

        # Bind request context for logging
        bind_request_context(
            request_id=f"msg_{message.id}",
            user_id=str(message.author.id),
            guild_id=str(message.guild.id) if message.guild else None,
            channel_id=str(message.channel.id),
        )

        # Only process commands with the prefix
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        Global error handler for commands.

        Args:
            ctx: Command context
            error: Exception that was raised
        """
        # Get original error if wrapped
        if hasattr(error, "original"):
            error = error.original  # type: ignore

        error_type = type(error).__name__

        log.error(
            "command_error",
            command=ctx.command.name if ctx.command else None,
            user_id=str(ctx.author.id),
            guild_id=str(ctx.guild.id) if ctx.guild else None,
            error_type=error_type,
            error_message=str(error),
        )

        # Handle specific error types
        if isinstance(error, commands.CommandNotFound):
            # Silently ignore unknown commands
            return

        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ Você não tem permissão: `{perms}`")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Argumento faltando: `{error.param.name}`")

        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Argumento inválido: {error}")

        elif isinstance(error, BotRateLimitError):
            await ctx.send(f"⏱️ {error.message}")

        else:
            # Generic error message
            await ctx.send(
                "❌ Ocorreu um erro ao processar seu comando. "
                "Por favor, tente novamente mais tarde."
            )

    @commands.command(name="ask")
    @commands.cooldown(
        rate=1,
        per=60.0,
        type=commands.BucketType.user,
    )
    async def ask_command(self, ctx: commands.Context, question: str) -> None:
        """
        Ask a question about law or contests.

        Usage: !ask <sua pergunta>

        Args:
            ctx: Command context
            question: User's question
        """
        # Send typing indicator
        await ctx.typing()

        try:
            # Get or create conversation
            conversation = await self.conversation_service.get_or_create_conversation(
                user_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id) if ctx.guild else None,
                channel_id=str(ctx.channel.id),
            )

            # Process question through service
            response_chunks = await self.conversation_service.process_question(
                question=question,
                conversation=conversation,
                user_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id) if ctx.guild else None,
                discord_message_id=str(ctx.message.id),
            )

            # Send response chunks
            for chunk in response_chunks:
                await ctx.send(chunk)

        except Exception as e:
            log.exception(
                "ask_command_failed",
                user_id=str(ctx.author.id),
                error_type=type(e).__name__,
            )
            await ctx.send(
                "❌ Desculpe, ocorreu um erro ao processar sua pergunta. "
                "Por favor, tente novamente."
            )

    @commands.command(name="ping")
    async def ping_command(self, ctx: commands.Context) -> None:
        """Check bot latency."""
        latency_ms = round(self.latency * 1000)
        await ctx.send(f"🏓 Pong! {latency_ms}ms")

    @commands.command(name="ajuda", aliases=["help"])
    async def help_command(self, ctx: commands.Context) -> None:
        """Show help information."""
        help_text = HELP_TEXT_TEMPLATE.format(
            prefix=settings.discord.command_prefix,
            history_runs=settings.history_runs,
        )
        await ctx.send(help_text)

    @commands.command(name="limpar", aliases=["clear"])
    async def clear_command(self, ctx: commands.Context) -> None:
        """Clear your conversation history."""
        deleted = await self.conversation_service.clear_conversation(
            user_id=str(ctx.author.id),
            guild_id=str(ctx.guild.id) if ctx.guild else None,
            channel_id=str(ctx.channel.id),
        )

        if deleted:
            await ctx.send("✅ Histórico da conversa limpo.")
        else:
            await ctx.send("ℹ️ Nenhuma conversa encontrada para limpar.")

    @commands.command(name="info")
    async def info_command(self, ctx: commands.Context) -> None:
        """Show bot information."""
        embed = discord.Embed(
            title="BotSalinha",
            description="Assistente virtual especializado em direito e concursos",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Versão", value=settings.app_version, inline=True)
        embed.add_field(name="Modelo", value=settings.google.model_id, inline=True)
        embed.add_field(
            name="Servidores",
            value=str(len(self.guilds)),
            inline=True,
        )

        await ctx.send(embed=embed)

    @commands.command(name="fontes")
    async def fontes_command(self, ctx: commands.Context) -> None:
        """Lista documentos indexados no RAG e estatísticas resumidas."""
        if not settings.rag.enabled:
            await ctx.send("ℹ️ RAG está desabilitado na configuração atual.")
            return

        await ctx.typing()
        try:
            async with self._rag_session() as session:
                stmt = select(DocumentORM).order_by(DocumentORM.nome.asc())
                documents = (await session.execute(stmt)).scalars().all()

            if not documents:
                await ctx.send(
                    "📚 Nenhuma fonte RAG indexada ainda.\n"
                    "Use `!reindexar completo` para criar o índice inicial."
                )
                return

            total_chunks = sum(doc.chunk_count for doc in documents)
            total_tokens = sum(doc.token_count for doc in documents)
            max_lines = 15

            lines = ["📚 Fontes RAG Indexadas", ""]
            for doc in documents[:max_lines]:
                lines.append(f"• {doc.nome}")
                lines.append(f"  {doc.chunk_count:,} chunks | {doc.token_count:,} tokens")

            if len(documents) > max_lines:
                lines.append(f"\n... e mais {len(documents) - max_lines} documento(s).")

            lines.append(f"\nTotal: {len(documents)} documento(s)")
            lines.append(f"Chunks totais: {total_chunks:,}")
            lines.append(f"Tokens totais: {total_tokens:,}")

            await ctx.send("\n".join(lines))
            log.info(
                "rag_fontes_consultadas",
                user_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id) if ctx.guild else None,
                documentos=len(documents),
                chunks_total=total_chunks,
                tokens_total=total_tokens,
                event_name="rag_fontes_consultadas",
            )
        except Exception as e:
            log.exception(
                "rag_fontes_falhou",
                user_id=str(ctx.author.id),
                error_type=type(e).__name__,
                error=str(e),
            )
            await ctx.send("❌ Falha ao consultar fontes RAG. Verifique os logs.")

    @commands.command(name="reindexar")
    async def reindexar_command(self, ctx: commands.Context, mode: str = "completo") -> None:
        """Executa reindexação RAG nos modos completo ou incremental (owner only)."""
        if not settings.rag.enabled:
            await ctx.send("ℹ️ RAG está desabilitado na configuração atual.")
            return

        if not await self.is_owner(ctx.author):
            await ctx.send("❌ Apenas o dono do bot pode executar este comando.")
            return

        mode_normalized = mode.strip().lower()
        aliases = {
            "c": "completo",
            "full": "completo",
            "completo": "completo",
            "i": "incremental",
            "inc": "incremental",
            "incremental": "incremental",
        }
        mode_normalized = aliases.get(mode_normalized, mode_normalized)
        if mode_normalized not in {"completo", "incremental"}:
            await ctx.send("❌ Modo inválido. Use `!reindexar completo` ou `!reindexar incremental`.")
            return

        documents_dir = self._resolve_rag_documents_dir()
        start = time.perf_counter()
        log.info(
            LogEvents.RAG_REINDEXACAO_INICIADA,
            user_id=str(ctx.author.id),
            guild_id=str(ctx.guild.id) if ctx.guild else None,
            mode=mode_normalized,
            documents_dir=str(documents_dir),
            event_name="rag_reindex_command_started",
        )
        await ctx.send(f"🔄 Reindexação RAG iniciada (`{mode_normalized}`). Aguarde...")
        await ctx.typing()

        try:
            async with self._rag_session() as session:
                ingestion_service = IngestionService(
                    session=session,
                    embedding_service=EmbeddingService(),
                )

                if mode_normalized == "completo":
                    stats = await ingestion_service.reindex(documents_dir=str(documents_dir))
                    duration = float(stats["duration_seconds"])
                    await ctx.send(
                        "✅ Reindexação RAG concluída!\n\n"
                        f"Modo: `{mode_normalized}`\n"
                        f"📄 Documentos processados: {stats['documents_count']}\n"
                        f"📦 Chunks indexados: {stats['chunks_count']}\n"
                        f"⏱️ Duração: {duration:.2f}s"
                    )
                    log.info(
                        LogEvents.RAG_REINDEXACAO_CONCLUIDA,
                        user_id=str(ctx.author.id),
                        guild_id=str(ctx.guild.id) if ctx.guild else None,
                        mode=mode_normalized,
                        documents_count=int(stats["documents_count"]),
                        chunks_count=int(stats["chunks_count"]),
                        duration_seconds=duration,
                        event_name="rag_reindex_command_completed",
                    )
                    return

                docx_files = sorted(documents_dir.rglob("*.docx"))
                if not docx_files:
                    await ctx.send(f"⚠️ Nenhum arquivo DOCX encontrado em `{documents_dir}`.")
                    return

                updated_docs = 0
                unchanged_docs = 0
                failed_docs = 0
                total_chunks = 0

                for docx_file in docx_files:
                    previous = (
                        await session.execute(
                            select(DocumentORM).where(DocumentORM.arquivo_origem == str(docx_file))
                        )
                    ).scalar_one_or_none()
                    previous_hash = previous.content_hash if previous else None
                    previous_chunks = previous.chunk_count if previous else 0
                    try:
                        document = await ingestion_service.ingest_document(
                            file_path=str(docx_file),
                            document_name=docx_file.stem,
                        )
                        total_chunks += document.chunk_count
                        if previous_hash == document.content_hash and previous_chunks > 0:
                            unchanged_docs += 1
                        else:
                            updated_docs += 1
                    except Exception as e:
                        failed_docs += 1
                        log.error(
                            "rag_reindex_incremental_document_failed",
                            document=str(docx_file),
                            error_type=type(e).__name__,
                            error=str(e),
                            event_name="rag_reindex_incremental_document_failed",
                        )

                duration = time.perf_counter() - start
                await ctx.send(
                    "✅ Reindexação RAG incremental concluída!\n\n"
                    f"📄 Processados: {len(docx_files)}\n"
                    f"♻️ Atualizados: {updated_docs}\n"
                    f"⏭️ Sem alteração: {unchanged_docs}\n"
                    f"❌ Falhas: {failed_docs}\n"
                    f"📦 Chunks totais vistos: {total_chunks}\n"
                    f"⏱️ Duração: {duration:.2f}s"
                )
                log.info(
                    LogEvents.RAG_REINDEXACAO_CONCLUIDA,
                    user_id=str(ctx.author.id),
                    guild_id=str(ctx.guild.id) if ctx.guild else None,
                    mode=mode_normalized,
                    documents_count=len(docx_files),
                    updated_documents=updated_docs,
                    unchanged_documents=unchanged_docs,
                    failed_documents=failed_docs,
                    chunks_count=total_chunks,
                    duration_seconds=duration,
                    event_name="rag_reindex_command_completed",
                )
        except Exception as e:
            duration = time.perf_counter() - start
            log.exception(
                "rag_reindex_command_failed",
                user_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id) if ctx.guild else None,
                mode=mode_normalized,
                duration_seconds=duration,
                error_type=type(e).__name__,
                error=str(e),
            )
            await ctx.send("❌ Reindexação falhou. Verifique logs e configuração do RAG.")

    @ask_command.error
    async def ask_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Local error handler for ask command."""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏱️ Aguarde `{error.retry_after:.1f}s` antes de usar este comando novamente."
            )
        else:
            # Let global error handler handle other errors
            raise


__all__ = ["BotSalinhaBot"]
