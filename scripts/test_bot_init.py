#!/usr/bin/env python3
"""Test bot initialization with Convex."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

async def test():
    print("=" * 60)
    print("TESTING BOT INITIALIZATION")
    print("=" * 60)
    print()
    
    # Test repository factory
    print("1. Testing repository factory...")
    from src.storage.repository_factory import get_configured_repository
    
    repo = get_configured_repository()
    print(f"   Repository type: {type(repo).__name__}")
    print(f"   Has initialize_database: {hasattr(repo, 'initialize_database')}")
    print()
    
    # Test bot initialization
    print("2. Testing bot initialization...")
    from src.core.discord import BotSalinhaBot
    
    bot = BotSalinhaBot()
    print(f"   Bot created successfully")
    print(f"   Repository: {type(bot.repository).__name__}")
    print(f"   Agent: {type(bot.agent).__name__}")
    print()
    
    # Test repository operations
    print("3. Testing repository operations...")
    from src.models.conversation import ConversationCreate
    
    conversation = await repo.create_conversation(
        ConversationCreate(
            user_id="test_user",
            guild_id="test_guild",
            channel_id="test_channel",
        )
    )
    print(f"   Created conversation: {conversation.id}")
    
    # Cleanup
    await repo.delete_conversation(conversation.id)
    print(f"   Deleted conversation")
    print()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print(f"Using backend: {type(repo).__name__}")
    print()

if __name__ == "__main__":
    asyncio.run(test())
