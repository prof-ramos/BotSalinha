"""add content_links table for explicit legal chunk relationships

Revision ID: 20260303_1200
Revises: 20260303_0915
Create Date: 2026-03-03 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260303_1200"
down_revision: str | None = "20260303_0915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create content_links for explicit relations between legal content chunks."""
    op.create_table(
        "content_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("article_chunk_id", sa.String(length=255), nullable=False),
        sa.Column("linked_chunk_id", sa.String(length=255), nullable=False),
        sa.Column("link_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "link_type IN ('interprets', 'charged_in', 'updates')",
            name="ck_content_links_link_type",
        ),
        sa.ForeignKeyConstraint(["article_chunk_id"], ["rag_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_chunk_id"], ["rag_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_links_article_link_type",
        "content_links",
        ["article_chunk_id", "link_type"],
    )
    op.create_index("ix_content_links_linked_chunk_id", "content_links", ["linked_chunk_id"])
    op.create_unique_constraint(
        "uq_content_links_relation",
        "content_links",
        ["article_chunk_id", "linked_chunk_id", "link_type"],
    )


def downgrade() -> None:
    """Drop content_links table and related indexes."""
    op.drop_constraint("uq_content_links_relation", "content_links", type_="unique")
    op.drop_index("ix_content_links_linked_chunk_id", table_name="content_links")
    op.drop_index("ix_content_links_article_link_type", table_name="content_links")
    op.drop_table("content_links")
