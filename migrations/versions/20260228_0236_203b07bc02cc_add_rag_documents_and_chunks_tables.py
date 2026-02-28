"""add RAG documents and chunks tables

Revision ID: 203b07bc02cc
Revises: 002
Create Date: 2026-02-28 02:36:00.597092+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "203b07bc02cc"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create rag_documents table."""
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(255), nullable=False, index=True),
        sa.Column("arquivo_origem", sa.String(500), nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    """Create rag_chunks table."""
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "documento_id",
            sa.Integer,
            sa.ForeignKey("rag_documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("metadados", sa.Text, nullable=False),  # JSON string
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop rag_chunks table."""
    op.drop_table("rag_chunks")

    """Drop rag_documents table."""
    op.drop_table("rag_documents")
