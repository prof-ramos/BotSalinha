"""
Repository interfaces for data access.

Defines abstract interfaces for conversation and message repositories.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..models.conversation import (
    Conversation,
    ConversationCreate,
    ConversationUpdate,
    ConversationWithMessages,
)
from ..models.message import Message, MessageCreate, MessageRole, MessageUpdate


class ConversationRepository(ABC):
    """
    Abstract repository for conversation data access.

    Defines the interface for conversation CRUD operations.
    """

    @abstractmethod
    async def create_conversation(self, conversation: ConversationCreate) -> Conversation:
        """
        Create a new conversation.

        Args:
            conversation: Conversation data to create

        Returns:
            Created conversation with ID
        """
        pass

    @abstractmethod
    async def get_conversation_by_id(self, conversation_id: str) -> Conversation | None:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation or None if not found
        """
        pass

    @abstractmethod
    async def get_by_user_and_guild(
        self, user_id: str, guild_id: str | None = None
    ) -> list[Conversation]:
        """
        Get conversations for a user in a guild.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (None for DMs)

        Returns:
            List of conversations
        """
        pass

    @abstractmethod
    async def get_or_create_conversation(
        self, user_id: str, guild_id: str | None, channel_id: str
    ) -> Conversation:
        """
        Get existing conversation or create a new one.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (None for DMs)
            channel_id: Discord channel ID

        Returns:
            Existing or new conversation
        """
        pass

    @abstractmethod
    async def update_conversation(
        self, conversation_id: str, updates: ConversationUpdate
    ) -> Conversation | None:
        """
        Update a conversation.

        Args:
            conversation_id: Conversation ID
            updates: Fields to update

        Returns:
            Updated conversation or None if not found
        """
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """
        Delete conversations older than specified days.

        Args:
            days: Maximum age in days

        Returns:
            Number of conversations deleted
        """
        pass


class MessageRepository(ABC):
    """
    Abstract repository for message data access.

    Defines the interface for message CRUD operations.
    """

    @abstractmethod
    async def create_message(self, message: MessageCreate) -> Message:
        """
        Create a new message.

        Args:
            message: Message data to create

        Returns:
            Created message with ID
        """
        pass

    @abstractmethod
    async def get_message_by_id(self, message_id: str) -> Message | None:
        """
        Get a message by ID.

        Args:
            message_id: Message ID

        Returns:
            Message or None if not found
        """
        pass

    @abstractmethod
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
        role: MessageRole | None = None,
    ) -> list[Message]:
        """
        Get messages for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return
            role: Filter by message role (optional)

        Returns:
            List of messages ordered by creation time
        """
        pass

    @abstractmethod
    async def get_conversation_history(
        self,
        conversation_id: str,
        max_runs: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history formatted for LLM context.

        Returns the last N user/assistant pairs for context.

        Args:
            conversation_id: Conversation ID
            max_runs: Maximum number of conversation runs to include

        Returns:
            List of message dictionaries for LLM
        """
        pass

    @abstractmethod
    async def update_message(
        self, message_id: str, updates: MessageUpdate
    ) -> Message | None:
        """
        Update a message.

        Args:
            message_id: Message ID
            updates: Fields to update

        Returns:
            Updated message or None if not found
        """
        pass

    @abstractmethod
    async def delete_message(self, message_id: str) -> bool:
        """
        Delete a message.

        Args:
            message_id: Message ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def delete_conversation_messages(
        self, conversation_id: str
    ) -> int:
        """
        Delete all messages in a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of messages deleted
        """
        pass


__all__ = ["ConversationRepository", "MessageRepository"]
