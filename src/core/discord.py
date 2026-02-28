"""
Discord bot implementation using discord.py.

Implements the main bot with command handling, error handling,
and integration with the AI agent.
"""

import asyncio
from typing import TYPE_CHECKING

import discord
import structlog
from discord.ext import commands

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from ..config.settings import settings
from ..config.yaml_config import yaml_config
from ..middleware.rate_limiter import rate_limiter
from ..storage.sqlite_repository import SQLiteRepository, get_repository
from ..utils.errors import APIError
from ..utils.errors import RateLimitError as BotRateLimitError
from ..utils.log_correlation import bind_discord_context
from ..utils.log_events import LogEvents
from .agent import AgentWrapper

log = structlog.get_logger()


class BotSalinhaBot(commands.Bot):
    """
    Main Discord bot class for BotSalinha.

    Implements command handling with proper error handling,
    rate limiting, and AI integration.
    """

    def __init__(self, repository: SQLiteRepository | None = None) -> None:
        """Initialize the bot.

        Args:
            repository: Optional repository instance for dependency injection.
                        If not provided, uses the global repository.
        """
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.dm_messages = True

        super().__init__(
            command_prefix=settings.discord.command_prefix,
            intents=intents,
            help_command=None,
        )

        # Initialize components with dependency injection
        self.repository = repository or get_repository()
        # Agent is created without a RAG session; setup_hook enables RAG once the DB is ready.
        self.agent = AgentWrapper(repository=self.repository)
        self._ready_event = asyncio.Event()
        # Persistent session opened in setup_hook and closed in close().
        self._rag_session: "AsyncSession | None" = None

        log.info(LogEvents.BOT_DISCORD_INICIALIZADO, prefix=settings.discord.command_prefix)

    async def setup_hook(self) -> None:
        """Called when the bot is setting up."""
        # Initialize database
        await self.repository.initialize_database()
        await self.repository.create_tables()

        # Open a long-lived session for RAG and wire it into the agent.
        self._rag_session = self.repository.async_session_maker()
        self.agent.enable_rag_with_session(self._rag_session)

        log.info(LogEvents.BANCO_DADOS_INICIALIZADO)

    async def close(self) -> None:
        """Shutdown the bot and release the RAG session."""
        if self._rag_session is not None:
            await self._rag_session.close()
            self._rag_session = None
        await super().close()

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        self._ready_event.set()

        if self.user is None:
            log.warning(LogEvents.BOT_PRONTO_SEM_USUARIO)
            return

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
        bind_discord_context(
            message_id=message.id,
            user_id=message.author.id,
            guild_id=message.guild.id if message.guild else None,
            channel_id=message.channel.id,
        )

        # Detect AI channel (with try/except for ValueError/TypeError)
        is_canal_ia = False
        if settings.discord.canal_ia_id is not None:
            try:
                canal_ia_id = int(settings.discord.canal_ia_id)
                is_canal_ia = message.channel.id == canal_ia_id
            except (ValueError, TypeError) as e:
                log.warning(
                    LogEvents.CANAL_IA_ID_MALFORMADO,
                    canal_ia_id=settings.discord.canal_ia_id,
                    error=str(e),
                )
                # Fallback to process_commands when malformed

        is_dm = isinstance(message.channel, discord.DMChannel)

        # If AI channel or DM, process as chat
        if is_canal_ia or is_dm:
            await self._handle_chat_message(message, is_dm)
            return

        # Otherwise, process commands normally
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:  # type: ignore[type-arg]
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
            LogEvents.COMANDO_ERRO,
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

    async def _handle_chat_message(
        self,
        message: discord.Message,
        is_dm: bool,
    ) -> None:
        """
        Process messages from AI channel or DM with automatic response.

        Args:
            message: Discord message
            is_dm: Whether this is a DM message
        """
        guild_id = message.guild.id if message.guild else None
        user_id = message.author.id

        # 1. Validate message length (max 10,000 characters)
        if len(message.content) > 10_000:
            await message.channel.send(
                "❌ Mensagem muito longa. Por favor, use no máximo 10.000 caracteres."
            )
            return

        # 2. Validate message is not empty
        if not message.content.strip():
            return

        # 3. Apply rate limit (use existing middleware)
        try:
            await rate_limiter.check_rate_limit(
                user_id=user_id,
                guild_id=guild_id,
            )
        except BotRateLimitError as e:
            await message.channel.send(
                f"⏱️ Você excedeu o limite de solicitações. "
                f"Tente novamente em {e.retry_after:.0f} segundos."
            )
            return

        # 4. Show typing indicator and process message
        try:
            async with message.channel.typing():
                # 5. Get or create conversation via repository
                conversation = await self.repository.get_or_create_conversation(
                    user_id=str(user_id),
                    guild_id=str(guild_id) if guild_id else None,
                    channel_id=str(message.channel.id),
                )

                # 6. Save user message
                await self.agent.save_message(
                    conversation_id=conversation.id,
                    role="user",
                    content=message.content,
                    discord_message_id=str(message.id),
                )

                # 7. Generate response via AgentWrapper with RAG
                response, rag_context = await self.agent.generate_response_with_rag(
                    prompt=message.content,
                    conversation_id=conversation.id,
                    user_id=str(user_id),
                    guild_id=str(guild_id) if guild_id else None,
                )

                # 8. Save assistant message
                await self.agent.save_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response,
                )

            # 9. Send response (respecting Discord's 2000 character limit)
            # Add RAG context (confidence + sources) if available
            response_to_send = response
            if rag_context and rag_context.chunks_usados:
                # Add confidence indicator and sources
                confianca_msg = self._format_confidence(rag_context.confianca.value)
                sources_msg = self._format_sources(rag_context.fontes)
                response_to_send = f"{confianca_msg}\n\n{response}\n\n{sources_msg}"

            for chunk in self._split_response(response_to_send):
                try:
                    await message.channel.send(chunk)
                except discord.Forbidden:
                    log.warning(
                        LogEvents.USUARIO_BLOQUEOU_BOT,
                        user_id=str(user_id),
                        guild_id=str(guild_id),
                    )
                    # Cannot notify user if they blocked the bot
                    return

        except APIError as e:
            # Sanitize error details to prevent logging sensitive data
            sensitive_keys = {"api_key", "token", "password", "secret", "authorization", "bearer"}
            safe_details = (
                dict(e.details.items() if isinstance(e.details, dict) else [])
                if not isinstance(e.details, dict)
                else {
                    k: "***REDACTED***" if k.lower() in sensitive_keys else v
                    for k, v in e.details.items()
                }
            )

            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                user_id=str(user_id),
                guild_id=str(guild_id),
                error=str(e),
                details=safe_details,
            )
            await message.channel.send(
                "❌ Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente."
            )
        except Exception as e:
            log.error(
                LogEvents.ERRO_INESPERADO_PROCESSAR_MENSAGEM,
                user_id=str(user_id),
                guild_id=str(guild_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            await message.channel.send("❌ Ocorreu um erro inesperado. Por favor, tente novamente.")
        finally:
            log.info(
                LogEvents.MENSAGEM_PROCESSADA,
                user_id=str(user_id),
                guild_id=str(guild_id),
                is_dm=is_dm,
                message_length=len(message.content),
            )

    @commands.command(name="ask")  # type: ignore[type-var]
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
        # Validate prompt length to prevent DoS and excessive API costs
        max_prompt_length = 10_000  # 10k characters
        if len(question) > max_prompt_length:
            await ctx.send(
                f"❌ Pergunta muito longa. Máximo: {max_prompt_length:,} caracteres. "
                f"Sua pergunta tem {len(question):,} caracteres."
            )
            return

        # Send typing indicator
        await ctx.typing()

        try:
            # Get or create conversation
            conversation = await self.repository.get_or_create_conversation(
                user_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id) if ctx.guild else None,
                channel_id=str(ctx.channel.id),
            )

            # Save user message
            await self.agent.save_message(
                conversation_id=conversation.id,
                role="user",
                content=question,
                discord_message_id=str(ctx.message.id),
            )

            # Generate response with RAG
            response, rag_context = await self.agent.generate_response_with_rag(
                prompt=question,
                conversation_id=conversation.id,
                user_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id) if ctx.guild else None,
            )

            # Save assistant message
            await self.agent.save_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response,
            )

            # Send response (with Discord's 2000 character limit)
            # Add RAG context (confidence + sources) if available
            response_to_send = response
            if rag_context and rag_context.chunks_usados:
                # Add confidence indicator and sources
                confianca_msg = self._format_confidence(rag_context.confianca.value)
                sources_msg = self._format_sources(rag_context.fontes)
                response_to_send = f"{confianca_msg}\n\n{response}\n\n{sources_msg}"

            for chunk in self._split_response(response_to_send):
                await ctx.send(chunk)

            log.info(
                LogEvents.COMANDO_ASK_CONCLUIDO,
                conversation_id=conversation.id,
                user_id=str(ctx.author.id),
                question_length=len(question),
                response_length=len(response),
            )

        except Exception as e:
            log.exception(
                LogEvents.COMANDO_ASK_FALHOU,
                user_id=str(ctx.author.id),
                error_type=type(e).__name__,
            )
            await ctx.send(
                "❌ Desculpe, ocorreu um erro ao processar sua pergunta. "
                "Por favor, tente novamente."
            )

    @commands.command(name="ping")  # type: ignore[type-var]
    async def ping_command(self, ctx: commands.Context) -> None:
        """Check bot latency."""
        latency_ms = round(self.latency * 1000)
        await ctx.send(f"🏓 Pong! {latency_ms}ms")

    @commands.command(name="ajuda", aliases=["help"])  # type: ignore[type-var]
    async def help_command(  # type: ignore[override]
        self, ctx: commands.Context
    ) -> None:
        """Show help information."""
        help_text = f"""
**BotSalinha** - Assistente de Direito e Concursos com RAG

**Comandos disponíveis:**
• `!ask <pergunta>` - Faça uma pergunta sobre direito ou concursos (com RAG)
• `!fontes` - Lista documentos jurídicos indexados no RAG
• `!ping` - Verifique a latência do bot
• `!limpar` - Limpe o histórico da conversa
• `!ajuda` - Mostra esta mensagem de ajuda

**Comandos de Admin:**
• `!reindexar` - Recria o índice RAG (apenas administrador)

**Sobre:**
Sou um assistente especializado em direito brasileiro e concursos públicos.
Com RAG, posso buscar informações em documentos jurídicos indexados (CF/88, Lei 8.112/90).

**Indicadores de Confiança:**
✅ **ALTA** - Resposta baseada em documentos indexados
⚠️ **MÉDIA** - Resposta parcialmente baseada em documentos
❌ **BAIXA** - Informações limitadas encontradas
ℹ️ **SEM RAG** - Resposta baseada em conhecimento geral

**Limitações:**
• Mantenho contexto de até {settings.history_runs} mensagens anteriores
• Respeito limites de taxa para uso justo

Desenvolvido com ❤️ usando Agno + OpenAI
        """

        await ctx.send(help_text)

    @commands.command(name="limpar", aliases=["clear"])  # type: ignore[type-var]
    async def clear_command(self, ctx: commands.Context) -> None:
        """Clear your conversation history."""
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        channel_id = str(ctx.channel.id)

        log.info(
            LogEvents.COMANDO_LIMPAR_INICIADO,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

        # Fetch conversations for user/guild; channel filtering happens in the loop below
        conversations = await self.repository.get_by_user_and_guild(
            user_id=user_id,
            guild_id=guild_id,
        )

        # Find conversation in this channel
        cleared = False
        for conv in conversations:
            if conv.channel_id == channel_id:
                await self.repository.delete_conversation(conv.id)
                log.info(
                    LogEvents.COMANDO_LIMPAR_SUCESSO,
                    conv_id=conv.id,
                    user_id=user_id,
                    channel_id=channel_id,
                )
                cleared = True
                break

        if cleared:
            await ctx.send("✅ Histórico da conversa limpo.")
        else:
            log.info(
                LogEvents.COMANDO_LIMPAR_SEM_CONVERSA,
                user_id=user_id,
                guild_id=guild_id,
                channel_id=channel_id,
            )
            await ctx.send("ℹ️ Nenhuma conversa encontrada para limpar.")

    @commands.command(name="info")  # type: ignore[type-var]
    async def info_command(self, ctx: commands.Context) -> None:
        """Show bot information."""
        embed = discord.Embed(
            title="BotSalinha",
            description="Assistente virtual especializado em direito e concursos",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Versão", value=settings.app_version, inline=True)
        embed.add_field(name="Modelo", value=yaml_config.model.model_id, inline=True)
        embed.add_field(
            name="Servidores",
            value=str(len(self.guilds)),
            inline=True,
        )

        await ctx.send(embed=embed)

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

    @commands.command(name="fontes")  # type: ignore[type-var]
    async def fontes_command(self, ctx: commands.Context) -> None:
        """List documents indexed in RAG."""
        if not self.agent.enable_rag:
            await ctx.send("ℹ️ RAG não está habilitado neste servidor.")
            return

        await ctx.typing()

        try:
            from sqlalchemy import func, select

            from src.models.rag_models import DocumentORM

            async with self.repository.session() as db_session:
                # Get document count
                doc_count_stmt = select(func.count(DocumentORM.id))
                doc_count_result = await db_session.execute(doc_count_stmt)
                doc_count = doc_count_result.scalar() or 0

                if doc_count == 0:
                    await ctx.send("ℹ️ Nenhum documento indexado no RAG.")
                    return

                # Get all documents
                doc_stmt = select(DocumentORM).order_by(DocumentORM.created_at)
                doc_result = await db_session.execute(doc_stmt)
                documents = doc_result.scalars().all()

            embed = discord.Embed(
                title="📚 Fontes RAG Indexadas",
                description="Documentos jurídicos disponíveis para consulta",
                color=discord.Color.blue(),
            )

            for doc in documents:
                # Use stored chunk count from document metadata
                chunk_count = doc.chunk_count

                embed.add_field(
                    name=doc.nome,
                    value=f"{chunk_count} chunks | {doc.token_count} tokens",
                    inline=False,
                )

            embed.set_footer(text=f"Total: {doc_count} documentos")

            await ctx.send(embed=embed)

            log.info(
                "rag_fontes_listadas",
                user_id=str(ctx.author.id),
                documentos=doc_count,
            )

        except Exception as e:
            log.error(
                LogEvents.ERRO_INESPERADO_PROCESSAR_MENSAGEM,
                error=str(e),
                error_type=type(e).__name__,
            )
            await ctx.send("❌ Erro ao listar fontes RAG.")

    @commands.command(name="reindexar")  # type: ignore[type-var]
    @commands.is_owner()  # Only bot owner can use this
    async def reindexar_command(self, ctx: commands.Context) -> None:
        """Rebuild the RAG index from scratch (admin only)."""
        if not self.agent.enable_rag:
            await ctx.send("ℹ️ RAG não está habilitado neste servidor.")
            return

        await ctx.typing()

        try:
            from src.rag.services.embedding_service import EmbeddingService
            from src.rag.services.ingestion_service import IngestionService

            async with self.repository.session() as db_session:
                # Create ingestion service
                embedding_service = EmbeddingService()
                ingestion_service = IngestionService(
                    session=db_session,
                    embedding_service=embedding_service,
                )

                # Send initial message
                start_msg = await ctx.send(
                    "🔄 Iniciando reindexação RAG...\n\n⏳ Isso pode levar alguns segundos."
                )

                # Reindex
                result = await ingestion_service.reindex()

            # Build response message
            if result["success"]:
                response = (
                    f"✅ **Reindexação RAG Concluída!**\n\n"
                    f"📄 Documentos processados: {result['documents_count']}\n"
                    f"📦 Chunks criados: {result['chunks_count']}\n"
                    f"⏱️ Tempo total: {result['duration_seconds']}s\n\n"
                    f"O índice RAG foi reconstruído com sucesso."
                )

                # Edit the original message
                await start_msg.edit(content=response)

                log.info(
                    "rag_reindex_command_success",
                    user_id=str(ctx.author.id),
                    documents_count=result["documents_count"],
                    chunks_count=result["chunks_count"],
                    duration=result["duration_seconds"],
                )
            else:
                await ctx.send(
                    "⚠️ Reindexação concluída sem erros, mas nenhum documento foi processado."
                )

        except Exception as e:
            log.error(
                LogEvents.ERRO_INESPERADO_PROCESSAR_MENSAGEM,
                error=str(e),
                error_type=type(e).__name__,
                user_id=str(ctx.author.id),
            )
            await ctx.send(
                f"❌ Erro ao reindexar: {str(e)}\n\nVerifique os logs para mais detalhes."
            )

    @commands.command(name="buscar")  # type: ignore[type-var]
    async def buscar_command(
        self, ctx: commands.Context, query: str = "", tipo: str = "todos"
    ) -> None:
        """
        Busca vetorial no RAG por tipo de documento.

        Usage: !buscar "termo de busca" [tipo: artigo|jurisprudencia|questao|nota|todos]
        """
        if not self.agent.enable_rag or self.agent._query_service is None:
            await ctx.send("ℹ️ RAG não está habilitado neste servidor.")
            return

        if not query:
            await ctx.send("❌ Por favor, forneça um termo para a busca.")
            return

        valid_tipos = ["artigo", "jurisprudencia", "questao", "nota", "todos"]
        if tipo not in valid_tipos:
            await ctx.send(f"❌ Tipo inválido. Use um dos seguintes: {', '.join(valid_tipos)}")
            return

        await ctx.typing()

        try:
            # Execute type-filtered query
            rag_context = await self.agent._query_service.query_by_tipo(
                query_text=query,
                tipo=tipo,
            )

            if not rag_context or not rag_context.chunks_usados:
                await ctx.send(f"❌ Nenhum resultado encontrado para '{query}' do tipo '{tipo}'.")
                return

            # Build and send results using augmentation text from QueryService
            # We skip instructions meant for the AI and just display the relevant context
            confianca_msg = self._format_confidence(rag_context.confianca.value)

            response = [
                f"**🔍 Resultados para:** `{query}`",
                f"**TIPO:** {tipo}",
                confianca_msg,
                "",
            ]

            for i, (chunk, score) in enumerate(
                zip(rag_context.chunks_usados, rag_context.similaridades, strict=False), 1
            ):
                prefix = "📄"  # Default
                if chunk.metadados.artigo:
                    prefix = "⚖️"
                elif chunk.metadados.marca_stf or chunk.metadados.marca_stj:
                    prefix = "📜"
                elif chunk.metadados.banca:
                    prefix = "❓"
                elif chunk.token_count < 100:
                    prefix = "📝"

                response.append(f"{prefix} **Resultado {i}** (Similaridade: {score:.2f})")
                response.append(
                    f"**Fonte:** {rag_context.fontes[i - 1] if i <= len(rag_context.fontes) else 'N/A'}"
                )
                response.append(f"{chunk.texto[:300]}...\n")

            response_to_send = "\n".join(response)

            for chunk_msg in self._split_response(response_to_send):
                await ctx.send(chunk_msg)

        except Exception as e:
            log.error(
                LogEvents.ERRO_INESPERADO_PROCESSAR_MENSAGEM,
                error=str(e),
                error_type=type(e).__name__,
                user_id=str(ctx.author.id),
            )
            await ctx.send(f"❌ Erro ao buscar: {str(e)}")

    @staticmethod
    def _format_confidence(confianca_level: str) -> str:
        """Format confidence level for Discord display."""
        emojis = {
            "alta": "✅",
            "media": "⚠️",
            "baixa": "❌",
            "sem_rag": "ℹ️",
        }
        labels = {
            "alta": "[ALTA CONFIANÇA]",
            "media": "[MÉDIA CONFIANÇA]",
            "baixa": "[BAIXA CONFIANÇA]",
            "sem_rag": "[SEM RAG]",
        }
        emoji = emojis.get(confianca_level, "ℹ️")
        label = labels.get(confianca_level, "[CONFIANÇA]")

        return f"{emoji} {label}"

    @staticmethod
    def _format_sources(fontes: list[str]) -> str:
        """Format sources for Discord display."""
        if not fontes:
            return "📎 Fontes: Nenhuma"

        # Limit to top 3 sources
        limited_fontes = fontes[:3]
        fonte_text = "\n".join(f"📎 {fonte}" for fonte in limited_fontes)

        if len(fontes) > 3:
            fonte_text += f"\n📎 ... e mais {len(fontes) - 3} fontes"

        return fonte_text

    @staticmethod
    def _split_response(response: str, max_len: int = 2000) -> list[str]:
        """Split a response respecting paragraph and word boundaries.

        Splits on line breaks first. If a single line exceeds max_len,
        splits at the last whitespace before the limit. Falls back to
        hard character slicing only when no whitespace is found.
        """
        if len(response) <= max_len:
            return [response]

        chunks: list[str] = []
        current = ""

        # Split by lines to preserve content structure
        lines = response.splitlines(keepends=True)
        for line in lines:
            if len(current) + len(line) > max_len:
                if current:
                    chunks.append(current)
                    current = ""

                # If a single line is too long, split respecting word boundaries
                if len(line) > max_len:
                    start = 0
                    while start < len(line):
                        if start + max_len >= len(line):
                            current = line[start:]
                            break
                        # Find last whitespace before max_len
                        split_pos = line.rfind(" ", start, start + max_len)
                        if split_pos <= start:
                            # No whitespace found; hard slice as fallback
                            split_pos = start + max_len

                        # Include the space in the chunk to preserve the exact string
                        chunk_end = split_pos if split_pos == start + max_len else split_pos + 1
                        chunk = line[start:chunk_end]
                        chunks.append(chunk)
                        start = chunk_end
                else:
                    current = line
            else:
                current += line

        if current:
            chunks.append(current)
        return chunks


__all__ = ["BotSalinhaBot"]
