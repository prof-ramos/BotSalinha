"""
Convex repository implementation for BotSalinha.

Implements ConversationRepository and MessageRepository interfaces
using Convex as the backend.

NOTE: The Convex Python SDK is synchronous, not async.
"""

from typing import Any

from convex import ConvexClient

from ..models.conversation import (
    Conversation,
    ConversationCreate,
    ConversationUpdate,
)
from ..models.message import Message, MessageCreate, MessageRole, MessageUpdate
from .repository import ConversationRepository, MessageRepository


class ConvexRepository(ConversationRepository, MessageRepository):
    """
    Repository implementation using Convex as backend.

    Provides real-time sync, vector search, and cloud persistence.
    
    NOTE: The Convex Python SDK is synchronous. All methods are synchronous
    even though they implement async interfaces.
    """

    def __init__(self, convex_url: str) -> None:
        """
        Initialize Convex repository.

        Args:
            convex_url: Convex deployment URL
        """
        self.client = ConvexClient(convex_url)

    # ==================== ConversationRepository ====================

    async def create_conversation(self, conversation: ConversationCreate) -> Conversation:
        """Create a new conversation in Convex."""
        result = self.client.mutation("conversations:create", {
            "userId": conversation.user_id,
            "guildId": conversation.guild_id,
            "channelId": conversation.channel_id,
        })

        return Conversation(
            id=str(result),
            user_id=conversation.user_id,
            guild_id=conversation.guild_id,
            channel_id=conversation.channel_id,
            created_at=0,  # Convex doesn't return timestamps in create
            updated_at=0,
        )

    async def get_conversation_by_id(self, conversation_id: str) -> Conversation | None:
        """Get conversation by ID."""
        result = self.client.query("conversations:getById", {
            "conversationId": conversation_id,
        })

        if not result:
            return None

        return Conversation(
            id=str(result["_id"]),
            user_id=result["userId"],
            guild_id=result.get("guildId"),
            channel_id=result["channelId"],
            created_at=result["createdAt"],
            updated_at=result["updatedAt"],
        )

    async def get_by_user_and_guild(
        self, user_id: str, guild_id: str | None = None
    ) -> list[Conversation]:
        """Get conversations for a user in a guild."""
        results = self.client.query("conversations:getByUserAndGuild", {
            "userId": user_id,
            "guildId": guild_id,
        })

        return [
            Conversation(
                id=str(r["_id"]),
                user_id=r["userId"],
                guild_id=r.get("guildId"),
                channel_id=r["channelId"],
                created_at=r["createdAt"],
                updated_at=r["updatedAt"],
            )
            for r in results
        ]

    async def get_or_create_conversation(
        self, user_id: str, guild_id: str | None, channel_id: str
    ) -> Conversation:
        """Get existing conversation or create a new one."""
        result = self.client.mutation("conversations:getOrCreate", {
            "userId": user_id,
            "guildId": guild_id,
            "channelId": channel_id,
        })

        return Conversation(
            id=str(result["_id"]),
            user_id=result["userId"],
            guild_id=result.get("guildId"),
            channel_id=result["channelId"],
            created_at=result["createdAt"],
            updated_at=result["updatedAt"],
        )

    async def update_conversation(
        self, conversation_id: str, updates: ConversationUpdate
    ) -> Conversation | None:
        """Update a conversation."""
        update_data = {}
        if updates.guild_id is not None:
            update_data["guildId"] = updates.guild_id
        if updates.channel_id is not None:
            update_data["channelId"] = updates.channel_id

        result = self.client.mutation("conversations:update", {
            "conversationId": conversation_id,
            "updates": update_data,
        })

        if not result:
            return None

        return Conversation(
            id=str(result["_id"]),
            user_id=result["userId"],
            guild_id=result.get("guildId"),
            channel_id=result["channelId"],
            created_at=result["createdAt"],
            updated_at=result["updatedAt"],
        )

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        result = self.client.mutation("conversations:remove", {
            "conversationId": conversation_id,
        })
        return result

    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """Delete conversations older than specified days."""
        result = self.client.mutation("conversations:cleanupOld", {
            "days": days,
        })
        return result

    # ==================== MessageRepository ====================

    async def create_message(self, message: MessageCreate) -> Message:
        """Create a new message."""
        result = self.client.mutation("messages:create", {
            "conversationId": message.conversation_id,
            "role": message.role.value,
            "content": message.content,
            "discordMessageId": message.discord_message_id,
        })

        return Message(
            id=str(result),
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            discord_message_id=message.discord_message_id,
            created_at=0,
        )

    async def get_message_by_id(self, message_id: str) -> Message | None:
        """Get message by ID."""
        result = self.client.query("messages:getById", {
            "messageId": message_id,
        })

        if not result:
            return None

        return Message(
            id=str(result["_id"]),
            conversation_id=str(result["conversationId"]),
            role=MessageRole(result["role"]),
            content=result["content"],
            discord_message_id=result.get("discordMessageId"),
            created_at=result["createdAt"],
        )

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
        role: MessageRole | None = None,
    ) -> list[Message]:
        """Get messages for a conversation."""
        results = self.client.query("messages:getByConversation", {
            "conversationId": conversation_id,
            "limit": limit,
            "role": role.value if role else None,
        })

        return [
            Message(
                id=str(r["_id"]),
                conversation_id=str(r["conversationId"]),
                role=MessageRole(r["role"]),
                content=r["content"],
                discord_message_id=r.get("discordMessageId"),
                created_at=r["createdAt"],
            )
            for r in results
        ]

    async def get_conversation_history(
        self,
        conversation_id: str,
        max_runs: int = 3,
    ) -> list[dict[str, Any]]:
        """Get conversation history formatted for LLM context."""
        results = self.client.query("messages:getHistory", {
            "conversationId": conversation_id,
            "maxRuns": max_runs,
        })

        return [
            {"role": r["role"], "content": r["content"]}
            for r in results
        ]

    async def update_message(self, message_id: str, updates: MessageUpdate) -> Message | None:
        """Update a message."""
        update_data = {}
        if updates.content is not None:
            update_data["content"] = updates.content

        result = self.client.mutation("messages:update", {
            "messageId": message_id,
            "updates": update_data,
        })

        if not result:
            return None

        return Message(
            id=str(result["_id"]),
            conversation_id=str(result["conversationId"]),
            role=MessageRole(result["role"]),
            content=result["content"],
            discord_message_id=result.get("discordMessageId"),
            created_at=result["createdAt"],
        )

    async def delete_message(self, message_id: str) -> bool:
        """Delete a message."""
        result = self.client.mutation("messages:remove", {
            "messageId": message_id,
        })
        return result

    async def delete_conversation_messages(self, conversation_id: str) -> int:
        """Delete all messages in a conversation."""
        result = self.client.mutation("messages:deleteByConversation", {
            "conversationId": conversation_id,
        })
        return result


__all__ = ["ConvexRepository"]
