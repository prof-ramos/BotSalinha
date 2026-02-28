"""
Conversation service - business logic for conversation handling.

Encapsulates the logic for managing conversations, messages,
and AI agent interactions.
"""

import structlog

from ..models.conversation import Conversation
from ..storage.repository import ConversationRepository, MessageRepository
from ..utils.message_splitter import MessageSplitter

log = structlog.get_logger()


class ConversationService:
    """
    Service for managing conversations and AI interactions.

    This service encapsulates the business logic for:
    - Getting or creating conversations
    - Managing message history
    - Generating AI responses
    - Splitting long messages for Discord
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        agent,  # AgentWrapper - avoid circular import
        message_splitter: MessageSplitter | None = None,
    ) -> None:
        """
        Initialize the conversation service.

        Args:
            conversation_repo: Repository for conversation persistence
            message_repo: Repository for message persistence
            agent: AI agent wrapper for generating responses
            message_splitter: Optional utility for splitting long messages
        """
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.agent = agent
        self.message_splitter = message_splitter or MessageSplitter()

    async def get_or_create_conversation(
        self,
        user_id: str,
        guild_id: str | None,
        channel_id: str,
    ) -> Conversation:
        """
        Get existing conversation or create a new one.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (None for DMs)
            channel_id: Discord channel ID

        Returns:
            Conversation instance
        """
        return await self.conversation_repo.get_or_create_conversation(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

    async def process_question(
        self,
        question: str,
        conversation: Conversation,
        user_id: str,
        guild_id: str | None,
        discord_message_id: str | None = None,
    ) -> list[str]:
        """
        Process a user question and return the response.

        This method:
        1. Saves the user's question
        2. Generates an AI response
        3. Saves the AI response
        4. Splits the response if needed

        Args:
            question: User's question
            conversation: Conversation instance
            user_id: Discord user ID
            guild_id: Discord guild ID
            discord_message_id: Discord message ID for the user's message

        Returns:
            List of message chunks (split for Discord's character limit)
        """
        # Save user message
        await self.agent.save_message(
            conversation_id=conversation.id,
            role="user",
            content=question,
            discord_message_id=discord_message_id,
        )

        # Generate response
        response = await self.agent.generate_response(
            prompt=question,
            conversation_id=conversation.id,
            user_id=user_id,
            guild_id=guild_id,
        )

        # Save assistant message
        await self.agent.save_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response,
        )

        log.info(
            "question_processed",
            conversation_id=conversation.id,
            user_id=user_id,
            question_length=len(question),
            response_length=len(response),
        )

        # Split for Discord
        return self.message_splitter.split(response)

    async def clear_conversation(
        self,
        user_id: str,
        guild_id: str | None,
        channel_id: str,
    ) -> bool:
        """
        Clear a user's conversation in a specific channel.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            channel_id: Discord channel ID

        Returns:
            True if conversation was deleted, False if not found
        """
        conversations = await self.conversation_repo.get_by_user_and_guild(
            user_id=user_id,
            guild_id=guild_id,
        )

        for conv in conversations:
            if conv.channel_id == channel_id:
                await self.conversation_repo.delete_conversation(conv.id)
                log.info(
                    "conversation_cleared",
                    conversation_id=conv.id,
                    user_id=user_id,
                    channel_id=channel_id,
                )
                return True

        return False

    async def get_conversation_info(
        self,
        conversation: Conversation,
    ) -> dict:
        """
        Get information about a conversation.

        Args:
            conversation: Conversation instance

        Returns:
            Dictionary with conversation info
        """
        messages = await self.message_repo.get_conversation_messages(
            conversation.id
        )

        return {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "guild_id": conversation.guild_id,
            "channel_id": conversation.channel_id,
            "message_count": len(messages),
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }


__all__ = ["ConversationService"]
