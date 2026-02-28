"""add_file_hash_to_rag_documents

Adds a SHA-256 file hash column to rag_documents and a UNIQUE constraint on it
so that the same file cannot be ingested twice.

NULL values are allowed for backward-compatibility with rows created before this
migration (SQLite allows multiple NULLs in a UNIQUE column by design).

Revision ID: 20260228_1100
Revises: 20260228_1000
Create Date: 2026-02-28 11:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260228_1100"
down_revision: str | None = "20260228_1000"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # SQLite requires batch mode for ADD COLUMN with constraints
    with op.batch_alter_table("rag_documents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "file_hash",
                sa.String(64),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_rag_documents_file_hash",
            ["file_hash"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_rag_documents_file_hash",
            ["file_hash"],
        )


def downgrade() -> None:
    with op.batch_alter_table("rag_documents", schema=None) as batch_op:
        batch_op.drop_constraint("uq_rag_documents_file_hash", type_="unique")
        batch_op.drop_index("ix_rag_documents_file_hash")
        batch_op.drop_column("file_hash")
