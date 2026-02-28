"""
Example usage of ConvexRepository with BotSalinha.

This demonstrates how to use Convex as a backend for the bot.
"""

import asyncio

from src.config.convex_config import ConvexConfig
from src.models.conversation import ConversationCreate
from src.models.message import MessageCreate, MessageRole
from src.storage.convex_repository import ConvexRepository


async def main():
    """Example of using ConvexRepository."""
    
    # Configure Convex
    config = ConvexConfig(
        url="https://beaming-mongoose-330.convex.cloud",
        deploy_key="prod:beaming-mongoose-330|eyJ2MiI6ImU0NzcxMzBjZDEwMTQyNmQ4NmIxMDQ0YzI5ZmUxYzI1In0=",
        enabled=True,
    )
    
    # Initialize repository
    repo = ConvexRepository(config.url)
    
    # Create or get conversation
    conversation = await repo.get_or_create_conversation(
        user_id="user_123",
        guild_id="guild_456",
        channel_id="channel_789",
    )
    
    print(f"Conversation: {conversation.id}")
    
    # Create user message
    user_message = await repo.create_message(
        MessageCreate(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Olá, BotSalinha!",
        )
    )
    
    print(f"User message: {user_message.content}")
    
    # Create assistant message
    assistant_message = await repo.create_message(
        MessageCreate(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Olá! Como posso ajudar?",
        )
    )
    
    print(f"Assistant message: {assistant_message.content}")
    
    # Get conversation history
    history = await repo.get_conversation_history(
        conversation_id=conversation.id,
        max_runs=2,
    )
    
    print(f"History: {history}")
    
    # Cleanup
    await repo.delete_conversation(conversation.id)
    print("Conversation deleted")


if __name__ == "__main__":
    asyncio.run(main())
