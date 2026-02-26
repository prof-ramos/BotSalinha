"""
Main entry point for BotSalinha.

This module initializes the bot and starts the Discord client.
Supports both Discord mode (default) and CLI chat mode (--chat).
"""

import argparse
import asyncio

from dotenv import load_dotenv

from .config.settings import settings
from .core.agent import AgentWrapper
from .core.discord import BotSalinhaBot
from .core.lifecycle import run_with_lifecycle
from .storage.sqlite_repository import SQLiteRepository
from .utils.logger import setup_logging

# Load environment variables
load_dotenv()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="botsalinha",
        description="BotSalinha - Assistente de Direito e Concursos Públicos",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Iniciar modo chat interativo no terminal (sem Discord)",
    )
    return parser.parse_args()


async def run_discord_bot() -> None:
    """Run the Discord bot (default mode)."""
    log = setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        app_version=settings.app_version,
        app_env=settings.app_env,
        debug=settings.debug,
    )

    bot = BotSalinhaBot()

    async def shutdown_bot():
        log.info("closing_discord_connection")
        await bot.close()

    await run_with_lifecycle(
        start_coro=bot.start(settings.discord.token),
        shutdown_coro=shutdown_bot,
    )

    log.info("botsalinha_stopped")


async def run_cli_chat() -> None:
    """Run the interactive CLI chat mode with streaming."""
    # Use text logging for better terminal readability
    log = setup_logging(
        log_level="WARNING",
        log_format="text",
        app_version=settings.app_version,
        app_env=settings.app_env,
        debug=settings.debug,
    )

    # Initialize database for CLI mode
    # Note: initialize_database() enables WAL mode and PRAGMA settings
    # create_tables() creates the actual schema - both are required
    repo = SQLiteRepository()
    session_started = False
    try:
        await repo.initialize_database()
        await repo.create_tables()

        agent = AgentWrapper(repository=repo)
        session_started = True
        await agent.run_cli()
    finally:
        # Ensure repository is properly closed
        await repo.close()
        if session_started:
            log.info("cli_session_ended")
        else:
            log.warning("cli_session_init_failed")


def cli_main() -> None:
    """CLI entry point."""
    args = parse_args()

    try:
        if args.chat:
            asyncio.run(run_cli_chat())
        else:
            asyncio.run(run_discord_bot())
    except KeyboardInterrupt:
        print("\n👋 BotSalinha encerrado.")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        raise


if __name__ == "__main__":
    cli_main()
