"""
BotSalinha facade - simplified interface for bot operations.

Provides a clean API for common operations while hiding internal complexity.
"""

import structlog

from .config.settings import settings
from .core.agent import AgentWrapper
from .services.conversation_service import ConversationService
from .storage.sqlite_repository import SQLiteRepository, get_repository
from .utils.message_splitter import MessageSplitter

log = structlog.get_logger()


class BotSalinha:
    """
    Facade for BotSalinha operations.

    This class provides a simplified interface for common bot operations,
    hiding the complexity of managing repositories, services, and agents.

    Usage:
        bot = BotSalinha()
        await bot.initialize()

        response = await bot.ask_question(
            question="What is habeas corpus?",
            user_id="123456",
            channel_id="789012",
        )

        await bot.shutdown()
    """

    def __init__(self, database_url: str | None = None) -> None:
        """
        Initialize the BotSalinha facade.

        Args:
            database_url: Optional database URL (defaults to settings)
        """
        self._database_url = database_url
        self._initialized = False

        # Components (initialized lazily)
        self._repository: SQLiteRepository | None = None
        self._agent: AgentWrapper | None = None
        self._conversation_service: ConversationService | None = None
        self._message_splitter: MessageSplitter | None = None

    async def initialize(self) -> None:
        """
        Initialize all components.

        Must be called before using other methods.
        """
        if self._initialized:
            return

        # Initialize repository
        self._repository = get_repository()
        await self._repository.initialize_database()
        await self._repository.create_tables()

        # Initialize agent
        self._agent = AgentWrapper(repository=self._repository)

        # Initialize message splitter
        self._message_splitter = MessageSplitter()

        # Initialize conversation service
        self._conversation_service = ConversationService(
            conversation_repo=self._repository,
            message_repo=self._repository,
            agent=self._agent,
            message_splitter=self._message_splitter,
        )

        self._initialized = True
        log.info("botsalinha_initialized")

    async def shutdown(self) -> None:
        """
        Shutdown and cleanup resources.

        Should be called when shutting down the bot.
        """
        if self._repository:
            await self._repository.close()

        self._initialized = False
        log.info("botsalinha_shutdown")

    async def ask_question(
        self,
        question: str,
        user_id: str,
        channel_id: str,
        guild_id: str | None = None,
    ) -> list[str]:
        """
        Ask a question and get a response.

        Args:
            question: User's question
            user_id: Discord user ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID (None for DMs)

        Returns:
            List of response chunks (split for Discord's character limit)

        Raises:
            RuntimeError: If not initialized
        """
        if not self._initialized or not self._conversation_service:
            raise RuntimeError("BotSalinha not initialized. Call initialize() first.")

        conversation = await self._conversation_service.get_or_create_conversation(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

        return await self._conversation_service.process_question(
            question=question,
            conversation=conversation,
            user_id=user_id,
            guild_id=guild_id,
        )

    async def clear_conversation(
        self,
        user_id: str,
        channel_id: str,
        guild_id: str | None = None,
    ) -> bool:
        """
        Clear a user's conversation in a channel.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID (None for DMs)

        Returns:
            True if conversation was deleted, False if not found

        Raises:
            RuntimeError: If not initialized
        """
        if not self._initialized or not self._conversation_service:
            raise RuntimeError("BotSalinha not initialized. Call initialize() first.")

        return await self._conversation_service.clear_conversation(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

    @property
    def repository(self) -> SQLiteRepository:
        """Get the repository instance."""
        if not self._repository:
            raise RuntimeError("BotSalinha not initialized. Call initialize() first.")
        return self._repository

    @property
    def agent(self) -> AgentWrapper:
        """Get the agent instance."""
        if not self._agent:
            raise RuntimeError("BotSalinha not initialized. Call initialize() first.")
        return self._agent

    @property
    def conversation_service(self) -> ConversationService:
        """Get the conversation service instance."""
        if not self._conversation_service:
            raise RuntimeError("BotSalinha not initialized. Call initialize() first.")
        return self._conversation_service

    @property
    def is_initialized(self) -> bool:
        """Check if the facade is initialized."""
        return self._initialized

    @property
    def version(self) -> str:
        """Get the bot version."""
        return settings.app_version

    @property
    def model_id(self) -> str:
        """Get the current AI model ID."""
        return settings.google.model_id


__all__ = ["BotSalinha"]
