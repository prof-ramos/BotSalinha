"""
Discord bot implementation using discord.py.

Implements the main bot with command handling, error handling,
and integration with the AI agent.
"""

import asyncio

import discord
import structlog
from discord.ext import commands

from ..config.settings import settings
from ..services.conversation_service import ConversationService
from ..storage.sqlite_repository import get_repository
from ..utils.errors import RateLimitError as BotRateLimitError
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

        # Initialize components
        self.repository = get_repository()
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

    async def setup_hook(self) -> None:
        """Called when the bot is setting up."""
        # Initialize database
        await self.repository.initialize_database()
        await self.repository.create_tables()

        log.info("database_initialized")

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
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
