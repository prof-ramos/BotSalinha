"""
RAG ORM models for BotSalinha.

Defines SQLAlchemy ORM models for RAG (Retrieval-Augmented Generation) functionality,
including documents and chunks storage.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .conversation import Base


class DocumentORM(Base):
    """
    SQLAlchemy ORM model for RAG documents.

    Represents a document that has been processed and chunked for retrieval.
    """

    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    arquivo_origem: Mapped[str] = mapped_column(String(500), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship to chunks
    chunks: Mapped[list["ChunkORM"]] = relationship(
        "ChunkORM",
        back_populates="documento",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DocumentORM(id={self.id!r}, nome={self.nome!r}, chunk_count={self.chunk_count})>"


class ChunkORM(Base):
    """
    SQLAlchemy ORM model for RAG chunks.

    Represents a chunk of text from a document with metadata for retrieval.
    """

    __tablename__ = "rag_chunks"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    metadados: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, default=None
    )  # Serialized embedding (float32 array)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship to document
    documento: Mapped["DocumentORM"] = relationship(
        "DocumentORM",
        back_populates="chunks",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<ChunkORM(id={self.id!r}, documento_id={self.documento_id!r})>"


__all__ = [
    "DocumentORM",
    "ChunkORM",
]
