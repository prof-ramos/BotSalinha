"""Storage layer for BotSalinha."""

from .factory import create_repository
from .repository import ConversationRepository, MessageRepository

__all__ = ["create_repository", "ConversationRepository", "MessageRepository"]
