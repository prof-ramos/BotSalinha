#!/usr/bin/env python3
"""
Test Convex configuration and connectivity.

Run this script to verify that Convex is properly configured.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env manually
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

from src.config.convex_config import ConvexConfig
from src.storage.convex_repository import ConvexRepository


async def test_convex():
    """Test Convex configuration and basic operations."""

    print("=" * 60)
    print("CONVEX CONFIGURATION TEST")
    print("=" * 60)
    print()

    # Read config from environment
    config = ConvexConfig(
        enabled=os.getenv('BOTSALINHA_CONVEX__ENABLED', 'false').lower() == 'true',
        url=os.getenv('BOTSALINHA_CONVEX__URL'),
        deploy_key=os.getenv('BOTSALINHA_CONVEX__DEPLOY_KEY'),
    )

    print("Configuration:")
    print(f"  Enabled: {config.enabled}")
    print(f"  URL: {config.url}")
    print(f"  Deploy Key: {config.deploy_key[:30] if config.deploy_key else 'None'}...")
    print(f"  Is Configured: {config.is_configured}")
    print()

    if not config.is_configured:
        print("❌ Convex is not configured. Check your .env file.")
        return False

    # Test connection
    print("Testing connection...")
    try:
        repo = ConvexRepository(config.url)
        print(f"  ✅ Client initialized: {repo.client}")
    except Exception as e:
        print(f"  ❌ Failed to initialize client: {e}")
        return False

    # Test basic operations
    print()
    print("Testing basic operations...")

    try:
        # Create test conversation
        print("  Creating test conversation...")
        from src.models.conversation import ConversationCreate

        conversation = await repo.create_conversation(
            ConversationCreate(
                user_id="test_user",
                guild_id="test_guild",
                channel_id="test_channel",
            )
        )
        print(f"  ✅ Created: {conversation.id}")

        # Get history
        print("  Getting history...")
        history = await repo.get_conversation_history(conversation.id, max_runs=1)
        print(f"  ✅ History: {len(history)} messages")

        # Delete test conversation
        print("  Cleaning up...")
        await repo.delete_conversation(conversation.id)
        print(f"  ✅ Deleted: {conversation.id}")

    except Exception as e:
        print(f"  ❌ Operations failed: {e}")
        return False

    print()
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("Convex is ready to use!")
    print()
    print("Next steps:")
    print("  1. Set BOTSALINHA_CONVEX__ENABLED=true in .env")
    print("  2. Use ConvexRepository in your code")
    print("  3. See examples/convex_example.py for usage")
    print()

    return True


if __name__ == "__main__":
    success = asyncio.run(test_convex())
    sys.exit(0 if success else 1)
