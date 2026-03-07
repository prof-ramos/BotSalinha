"""add source_type column to rag_chunks and content_links table

Revision ID: 20260303_2100
Revises: 20260303_0915
Create Date: 2026-03-03 21:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260303_2100"
down_revision: str | None = "20260303_0915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Valid values for source_type
SOURCE_TYPES = ("lei_cf", "emenda_constitucional", "jurisprudencia", "comentario", "questao_prova")


def upgrade() -> None:
    """Add source_type to rag_chunks and create content_links table."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    # --- source_type column on rag_chunks ---
    op.add_column(
        "rag_chunks",
        sa.Column(
            "source_type",
            sa.String(32),
            nullable=True,
            server_default=None,
        ),
    )
    op.create_index("ix_rag_chunks_source_type", "rag_chunks", ["source_type"])

    # Backfill source_type from the metadados JSON field where possible.
    # SQLite and PostgreSQL differ on JSON extraction syntax.
    if dialect_name == "sqlite":
        op.execute(
            """
            UPDATE rag_chunks
            SET source_type = json_extract(metadados, '$.source_type')
            WHERE json_extract(metadados, '$.source_type') IS NOT NULL
            """
        )
    elif dialect_name == "postgresql":
        op.execute(
            """
            UPDATE rag_chunks
            SET source_type = metadados::json->>'source_type'
            WHERE metadados::json->>'source_type' IS NOT NULL
            """
        )

    # --- content_links table (idempotent: table may already exist) ---
    from sqlalchemy import inspect as sa_inspect

    bind = op.get_bind()
    existing_tables = sa_inspect(bind).get_table_names()

    if "content_links" not in existing_tables:
        op.create_table(
            "content_links",
            sa.Column("id", sa.String(36), primary_key=True),  # UUID string
            sa.Column(
                "chunk_id",
                sa.String(255),
                sa.ForeignKey("rag_chunks.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "linked_chunk_id",
                sa.String(255),
                sa.ForeignKey("rag_chunks.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "link_type",
                sa.String(32),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # Composite index (create only if absent)
    existing_indexes = {
        idx["name"]
        for idx in sa_inspect(bind).get_indexes("content_links")
    }
    if "ix_content_links_chunk_id_link_type" not in existing_indexes:
        op.create_index(
            "ix_content_links_chunk_id_link_type",
            "content_links",
            ["chunk_id", "link_type"],
        )


def downgrade() -> None:
    """Reverse: drop content_links and source_type column."""
    op.drop_table("content_links")
    op.drop_index("ix_rag_chunks_source_type", table_name="rag_chunks")
    op.drop_column("rag_chunks", "source_type")
