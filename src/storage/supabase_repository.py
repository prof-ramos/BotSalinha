"""
Supabase repository implementation.

Implements conversation and message repositories using the Supabase Python SDK
with async patterns via REST API.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import structlog
from cachetools import TTLCache
from supabase import AsyncClient, create_async_client

from ..config.settings import get_settings
from ..models.conversation import (
    Conversation,
    ConversationCreate,
    ConversationUpdate,
)
from ..models.message import (
    Message,
    MessageCreate,
    MessageRole,
    MessageUpdate,
)
from ..utils.errors import RepositoryConfigurationError
from ..utils.log_events import LogEvents
from .repository import ConversationRepository, MessageRepository

log = structlog.get_logger()


class SupabaseRepository(ConversationRepository, MessageRepository):
    """
    Supabase repository implementation.

    Handles all database operations using the Supabase REST API via supabase-py.
    """

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        """
        Initialize the Supabase repository.

        Args:
            url: Supabase URL (defaults to settings.supabase.url)
            key: Supabase Key (defaults to settings.supabase.key)
        """
        settings = get_settings()
        self.url = url or settings.supabase.url
        self.key = key or settings.supabase.key

        if not self.url or not self.key:
            raise RepositoryConfigurationError(
                "Supabase URL and Key must be provided either directly or via settings",
                config_key="supabase",
            )

        # Client is initialized in `initialize_database()` since it's async
        self.client: AsyncClient | None = None

        # TTL cache for conversation lookups
        self._conversation_cache: TTLCache[str, Any] = TTLCache(maxsize=256, ttl=300)

        # Per-key locks for race condition prevention
        self._conversation_locks: dict[str, asyncio.Lock] = {}

        log.info(LogEvents.REPOSITORIO_SQLITE_INICIALIZADO, database_type="supabase")

    async def initialize_database(self) -> None:
        """
        Initialize the async Supabase client.
        """
        if self.client is None:
            self.client = await create_async_client(self.url, self.key)

    async def create_tables(self) -> None:
        """
        Not applicable for Supabase REST API.
        Tables must be created via Supabase Dashboard or CLI.
        """
        log.info(
            "create_tables called on SupabaseRepository: schemas must be managed via Supabase manually."
        )

    async def close(self) -> None:
        """Close the Supabase HTTP connection."""
        if self.client:
            await self.client.auth.sign_out()
        log.info(LogEvents.REPOSITORIO_SQLITE_FECHADO, database_type="supabase")

    def _parse_datetime(self, date_str: str) -> datetime:
        """Helper to parse ISO format strings from Supabase."""
        # Supabase returns ISO format like "2024-02-28T10:00:00+00:00" or "...Z"
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str).astimezone(UTC)

    # Conversation Repository Methods

    async def create_conversation(self, conversation: ConversationCreate) -> Conversation:
        if not self.client:
            await self.initialize_database()

        if self.client is None:
            raise RepositoryConfigurationError(
                "Supabase client failed to initialize",
                config_key="supabase.client",
            )

        data = {
            "id": str(uuid4()),
            "user_id": conversation.user_id,
            "guild_id": conversation.guild_id,
            "channel_id": conversation.channel_id,
            "meta_data": conversation.meta_data,
        }

        try:
            response = await self.client.table("conversations").insert(data).execute()
        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error="Failed to create conversation in Supabase",
                details=str(e),
            )
            raise

        if response.error:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error="Supabase error in create_conversation",
                details=response.error.message,
            )
            raise

        if not response.data or not response.data[0]:
            raise ValueError("No data returned from Supabase after insert")

        row = response.data[0]
        row["created_at"] = self._parse_datetime(row["created_at"])
        row["updated_at"] = self._parse_datetime(row["updated_at"])
        return Conversation.model_validate(row)

    async def get_conversation_by_id(self, conversation_id: str) -> Conversation | None:
        if not self.client:
            await self.initialize_database()

        response = (
            await self.client.table("conversations").select("*").eq("id", conversation_id).execute()
        )
        if not response.data:
            return None

        row = response.data[0]
        row["created_at"] = self._parse_datetime(row["created_at"])
        row["updated_at"] = self._parse_datetime(row["updated_at"])
        return Conversation.model_validate(row)

    async def get_by_user_and_guild(
        self, user_id: str, guild_id: str | None = None
    ) -> list[Conversation]:
        if not self.client:
            await self.initialize_database()

        query = self.client.table("conversations").select("*").eq("user_id", user_id)
        if guild_id is not None:
            query = query.eq("guild_id", guild_id)
        else:
            query = query.is_("guild_id", "null")

        response = await query.order("updated_at", desc=True).execute()

        conversations = []
        for row in response.data:
            row["created_at"] = self._parse_datetime(row["created_at"])
            row["updated_at"] = self._parse_datetime(row["updated_at"])
            conversations.append(Conversation.model_validate(row))

        return conversations

    async def get_or_create_conversation(
        self, user_id: str, guild_id: str | None, channel_id: str
    ) -> Conversation:
        cache_key = f"{user_id}:{guild_id}:{channel_id}"

        # Check cache first (fast path without lock)
        if cache_key in self._conversation_cache:
            return cast(Conversation, self._conversation_cache[cache_key])

        # Get or create lock for this cache_key
        if cache_key not in self._conversation_locks:
            self._conversation_locks[cache_key] = asyncio.Lock()

        lock = self._conversation_locks[cache_key]

        # Serialize operations for this cache_key
        async with lock:
            # Double-check cache after acquiring lock
            if cache_key in self._conversation_cache:
                return cast(Conversation, self._conversation_cache[cache_key])

            if not self.client:
                await self.initialize_database()

            # Query existing
            query = (
                self.client.table("conversations")
                .select("*")
                .eq("user_id", user_id)
                .eq("channel_id", channel_id)
            )
            if guild_id is not None:
                query = query.eq("guild_id", guild_id)
            else:
                query = query.is_("guild_id", "null")

            response = await query.order("updated_at", desc=True).limit(1).execute()

            if response.data:
                row = response.data[0]
                row["created_at"] = self._parse_datetime(row["created_at"])
                row["updated_at"] = self._parse_datetime(row["updated_at"])
                conv = Conversation.model_validate(row)
                self._conversation_cache[cache_key] = conv
                return conv

            # Create new
            create_data = ConversationCreate(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=channel_id,
            )
            conv = await self.create_conversation(create_data)
            self._conversation_cache[cache_key] = conv

            # Clean up lock to prevent memory leak
            if cache_key in self._conversation_locks:
                del self._conversation_locks[cache_key]

            return conv

    async def update_conversation(
        self, conversation_id: str, updates: ConversationUpdate
    ) -> Conversation | None:
        if not self.client:
            await self.initialize_database()

        update_data = {}
        if updates.meta_data is not None:
            update_data["meta_data"] = updates.meta_data

        update_data["updated_at"] = datetime.now(UTC).isoformat()

        response = (
            await self.client.table("conversations")
            .update(update_data)
            .eq("id", conversation_id)
            .execute()
        )
        if not response.data:
            return None

        row = response.data[0]
        row["created_at"] = self._parse_datetime(row["created_at"])
        row["updated_at"] = self._parse_datetime(row["updated_at"])
        return Conversation.model_validate(row)

    async def delete_conversation(self, conversation_id: str) -> bool:
        if not self.client:
            await self.initialize_database()

        response = (
            await self.client.table("conversations").delete().eq("id", conversation_id).execute()
        )

        if response.data:
            # Clear cache
            keys_to_remove = [
                k
                for k, v in list(self._conversation_cache.items())
                if getattr(v, "id", None) == conversation_id
            ]
            for k in keys_to_remove:
                self._conversation_cache.pop(k, None)
            return True
        return False

    async def cleanup_old_conversations(self, days: int = 30) -> int:
        if not self.client:
            await self.initialize_database()

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        response = (
            await self.client.table("conversations").delete().lt("updated_at", cutoff).execute()
        )

        count = len(response.data) if response.data else 0
        if count > 0:
            log.info(LogEvents.CONVERSAS_ANTIGAS_LIMPAS, count=count, days=days)
        return count

    async def get_dm_conversations(self, user_id: str) -> list[Conversation]:
        return await self.get_by_user_and_guild(user_id=user_id, guild_id=None)

    # Message Repository Methods

    async def create_message(self, message: MessageCreate) -> Message:
        if not self.client:
            await self.initialize_database()

        if self.client is None:
            raise RepositoryConfigurationError(
                "Supabase client failed to initialize",
                config_key="supabase.client",
            )

        data = {
            "id": str(uuid4()),
            "conversation_id": message.conversation_id,
            "role": message.role.value,
            "content": message.content,
            "discord_message_id": message.discord_message_id,
            "meta_data": message.meta_data,
        }

        try:
            response = await self.client.table("messages").insert(data).execute()
        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error="Failed to create message in Supabase",
                details=str(e),
            )
            raise

        if response.error:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error="Supabase error in create_message",
                details=response.error.message,
            )
            raise

        if not response.data or not response.data[0]:
            raise ValueError("No data returned from Supabase after insert")

        row = response.data[0]
        row["created_at"] = self._parse_datetime(row["created_at"])
        return Message.model_validate(row)

    async def get_message_by_id(self, message_id: str) -> Message | None:
        if not self.client:
            await self.initialize_database()

        response = await self.client.table("messages").select("*").eq("id", message_id).execute()
        if not response.data:
            return None

        row = response.data[0]
        row["created_at"] = self._parse_datetime(row["created_at"])
        return Message.model_validate(row)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
        role: MessageRole | None = None,
    ) -> list[Message]:
        if not self.client:
            await self.initialize_database()

        query = self.client.table("messages").select("*").eq("conversation_id", conversation_id)
        if role is not None:
            query = query.eq("role", role.value)

        query = query.order("created_at", desc=False)
        if limit is not None:
            query = query.limit(limit)

        response = await query.execute()

        messages = []
        for row in response.data:
            row["created_at"] = self._parse_datetime(row["created_at"])
            messages.append(Message.model_validate(row))
        return messages

    async def get_conversation_history(
        self,
        conversation_id: str,
        max_runs: int = 3,
    ) -> list[dict[str, Any]]:
        """Get history directly formatted via Supabase API."""
        if not self.client:
            await self.initialize_database()

        # Get latest 2 * max_runs user/assistant messages
        response = await (
            self.client.table("messages")
            .select("role, content")
            .eq("conversation_id", conversation_id)
            .in_("role", ["user", "assistant"])
            .order("created_at", desc=True)
            .limit(max_runs * 2)
            .execute()
        )

        # Return in chronological order
        return [{"role": r["role"], "content": r["content"]} for r in reversed(response.data)]

    async def update_message(self, message_id: str, updates: MessageUpdate) -> Message | None:
        if not self.client:
            await self.initialize_database()

        update_data = {}
        if updates.content is not None:
            update_data["content"] = updates.content
        if updates.meta_data is not None:
            update_data["meta_data"] = updates.meta_data

        if not update_data:
            return await self.get_message_by_id(message_id)

        response = (
            await self.client.table("messages").update(update_data).eq("id", message_id).execute()
        )
        if not response.data:
            return None

        row = response.data[0]
        row["created_at"] = self._parse_datetime(row["created_at"])
        return Message.model_validate(row)

    async def delete_message(self, message_id: str) -> bool:
        if not self.client:
            await self.initialize_database()

        response = await self.client.table("messages").delete().eq("id", message_id).execute()
        return bool(response.data)

    async def delete_conversation_messages(self, conversation_id: str) -> int:
        if not self.client:
            await self.initialize_database()

        response = (
            await self.client.table("messages")
            .delete()
            .eq("conversation_id", conversation_id)
            .execute()
        )
        return len(response.data) if response.data else 0

    async def clear_all_history(self) -> dict[str, int]:
        """Clear all messages and conversations using fetch-then-delete pattern."""
        if not self.client:
            await self.initialize_database()

        # Fetch all IDs first (messages)
        msg_ids_response = await self.client.table("messages").select("id").execute()
        msg_ids = [row["id"] for row in msg_ids_response.data] if msg_ids_response.data else []

        # Fetch all IDs first (conversations)
        conv_ids_response = await self.client.table("conversations").select("id").execute()
        conv_ids = [row["id"] for row in conv_ids_response.data] if conv_ids_response.data else []

        # Delete using IN filter (only if IDs exist)
        msg_count = 0
        if msg_ids:
            msg_response = await self.client.table("messages").delete().in_("id", msg_ids).execute()
            msg_count = len(msg_response.data) if msg_response.data else 0

        conv_count = 0
        if conv_ids:
            conv_response = await self.client.table("conversations").delete().in_("id", conv_ids).execute()
            conv_count = len(conv_response.data) if conv_response.data else 0

        self._conversation_cache.clear()

        counts = {
            "messages": msg_count,
            "conversations": conv_count,
        }

        log.info(LogEvents.BANCO_DADOS_LIMPO, **counts)
        return counts


__all__ = [
    "SupabaseRepository",
]
