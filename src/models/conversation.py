"""
Conversation data models for BotSalinha.

Defines SQLAlchemy ORM models and Pydantic schemas for conversations.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from .message import Message


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class ConversationORM(Base):
    """
    SQLAlchemy ORM model for conversations.

    Represents a conversation between a user and the bot in a specific guild.

    Note: Relationship to messages is not defined here to avoid circular import
    issues since MessageORM is created dynamically. Messages are queried separately
    through the repository.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    guild_id: Mapped[str] = mapped_column(String(255), index=True, nullable=True)
    channel_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    meta_data: Mapped[str | None] = mapped_column(Text, nullable=True, name="meta_data")

    def __repr__(self) -> str:
        return f"<ConversationORM(id={self.id!r}, user_id={self.user_id!r}, guild_id={self.guild_id!r})>"


# Pydantic schemas
class ConversationBase(BaseModel):
    """Base schema for conversation."""

    user_id: str = Field(..., description="Discord user ID")
    guild_id: str | None = Field(None, description="Discord guild/server ID")
    channel_id: str = Field(..., description="Discord channel ID")
    meta_data: str | None = Field(None, description="Additional metadata as JSON")


class ConversationCreate(ConversationBase):
    """Schema for creating a conversation."""

    pass


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    meta_data: str | None = Field(None, description="Additional metadata as JSON")


class Conversation(ConversationBase):
    """Schema for conversation response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Conversation ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(0, description="Number of messages in conversation")


class ConversationWithMessages(Conversation):
    """Schema for conversation with messages included."""

    messages: list["Message"] = Field(default_factory=list)


# Forward reference resolution
from .message import Message

ConversationWithMessages.model_rebuild()


__all__ = [
    "Base",
    "ConversationORM",
    "ConversationBase",
    "ConversationCreate",
    "ConversationUpdate",
    "Conversation",
    "ConversationWithMessages",
]
