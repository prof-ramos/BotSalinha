"""add schema and metadata version columns for rag compatibility

Revision ID: 20260303_0915
Revises: 20260302_1800
Create Date: 2026-03-03 09:15:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260303_0915"
down_revision: str | None = "20260302_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add explicit version columns to support metadata/schema evolution."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    op.add_column(
        "rag_documents",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "rag_chunks",
        sa.Column("metadata_version", sa.Integer(), nullable=False, server_default="1"),
    )

    # SQLite does not support ALTER COLUMN DROP DEFAULT syntax directly.
    if dialect_name != "sqlite":
        op.alter_column("rag_documents", "schema_version", server_default=None)
        op.alter_column("rag_chunks", "metadata_version", server_default=None)


def downgrade() -> None:
    """Drop version columns."""
    op.drop_column("rag_chunks", "metadata_version")
    op.drop_column("rag_documents", "schema_version")
