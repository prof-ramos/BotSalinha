"""
Main entry point for BotSalinha.

This module initializes the bot and starts the Discord client.
"""

import asyncio
from contextlib import suppress

import structlog
from dotenv import load_dotenv

from .config.settings import settings
from .core.discord import BotSalinhaBot
from .core.lifecycle import managed_lifecycle, run_with_lifecycle
from .utils.logger import setup_logging

# Load environment variables
load_dotenv()


async def main() -> None:
    """Main entry point for the application."""
    # Setup logging
    log = setup_logging()

    log.info(
        "botsalinha_starting",
        version=settings.app_version,
        environment=settings.app_env,
    )

    # Create bot
    bot = BotSalinhaBot()

    # Define shutdown coroutine
    async def shutdown_bot():
        log.info("closing_discord_connection")
        await bot.close()

    # Run with lifecycle management
    await run_with_lifecycle(
        start_coro=bot.start(settings.discord.token),
        shutdown_coro=shutdown_bot,
    )

    log.info("botsalinha_stopped")


def cli_main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 BotSalinha encerrado.")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        raise


if __name__ == "__main__":
    cli_main()
