"""
RAG ORM models for BotSalinha.

Defines SQLAlchemy ORM models for RAG (Retrieval-Augmented Generation) functionality,
including documents and chunks storage.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .conversation import Base

RAG_CHUNKS_TABLE_NAME = "rag_chunks"
RAG_CHUNKS_FTS_TABLE_NAME = "rag_chunks_fts"


class DocumentORM(Base):
    """
    SQLAlchemy ORM model for RAG documents.

    Represents a document that has been processed and chunked for retrieval.
    """

    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    arquivo_origem: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        unique=True,
    )
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
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

    __tablename__ = RAG_CHUNKS_TABLE_NAME

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    metadados: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    metadata_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
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


class ContentLinkORM(Base):
    """Explicit links between legal parent chunks and related child chunks."""

    __tablename__ = "content_links"
    __table_args__ = (
        CheckConstraint(
            "link_type IN ('interprets', 'charged_in', 'updates')",
            name="ck_content_links_link_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    article_chunk_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("rag_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_chunk_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("rag_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ContentLinkORM(article_chunk_id={self.article_chunk_id!r}, "
            f"linked_chunk_id={self.linked_chunk_id!r}, link_type={self.link_type!r})>"
        )


__all__ = [
    "DocumentORM",
    "ChunkORM",
    "ContentLinkORM",
    "RAG_CHUNKS_TABLE_NAME",
    "RAG_CHUNKS_FTS_TABLE_NAME",
]
