"""
Message data models for BotSalinha.

Defines SQLAlchemy ORM models and Pydantic schemas for messages.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    from .conversation import ConversationORM, Conversation


class MessageRole(str, Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageORM:
    """
    SQLAlchemy ORM model for messages.

    Note: This uses string-based forward references since ConversationORM
    is in a different module. The actual declarative model is defined
    in the repository module to avoid circular imports.
    """

    # This is a placeholder - actual ORM class is created dynamically
    # to avoid SQLAlchemy's declarative base issues with circular imports
    pass


# Pydantic schemas
class MessageBase(BaseModel):
    """Base schema for message."""

    role: MessageRole = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    meta_data: str | None = Field(None, description="Additional metadata as JSON", alias="metadata")


class MessageCreate(MessageBase):
    """Schema for creating a message."""

    conversation_id: str = Field(..., description="Associated conversation ID")
    discord_message_id: str | None = Field(None, description="Discord message ID if applicable")


class MessageUpdate(BaseModel):
    """Schema for updating a message."""

    content: str | None = None
    meta_data: str | None = Field(None, alias="metadata")


class Message(MessageBase):
    """Schema for message response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Associated conversation ID")
    discord_message_id: str | None = Field(None, description="Discord message ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Optional conversation reference
    conversation: "Conversation | None" = None


class MessageWithConversation(Message):
    """Schema for message with conversation included."""

    conversation: "Conversation" = Field(..., description="Associated conversation")


# Forward reference resolution already handled at top of file


# Full ORM class definition for use in repository
def create_message_orm(base: type) -> type:
    """
    Create the MessageORM class dynamically to avoid circular imports.

    Args:
        base: The SQLAlchemy declarative base

    Returns:
        MessageORM class
    """

    class MessageORMImpl(base):
        """SQLAlchemy ORM model for messages."""

        __tablename__ = "messages"

        id: Mapped[str] = mapped_column(
            String(36), primary_key=True, default=lambda: str(uuid4())
        )
        conversation_id: Mapped[str] = mapped_column(
            String(36),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
        role: Mapped[str] = mapped_column(String(20), nullable=False)
        content: Mapped[str] = mapped_column(Text, nullable=False)
        discord_message_id: Mapped[str | None] = mapped_column(
            String(255), index=True, nullable=True
        )
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            nullable=False,
        )
        meta_data: Mapped[str | None] = mapped_column(Text, nullable=True, name="meta_data")

        def __repr__(self) -> str:
            return (
                f"<MessageORM(id={self.id!r}, conversation_id={self.conversation_id!r}, "
                f"role={self.role!r})>"
            )

    return MessageORMImpl


__all__ = [
    "MessageRole",
    "MessageBase",
    "MessageCreate",
    "MessageUpdate",
    "Message",
    "MessageWithConversation",
    "create_message_orm",
    "MessageORM",  # Will be set by sqlite_repository
]
