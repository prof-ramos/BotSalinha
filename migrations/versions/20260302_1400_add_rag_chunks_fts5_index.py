"""add FTS5 lexical index for rag_chunks

Revision ID: 20260302_1400
Revises: 20260301_1200
Create Date: 2026-03-02 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260302_1400"
down_revision: str | None = "20260301_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create FTS5 index and sync triggers for rag_chunks lexical retrieval."""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    op.execute(
        sa.text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts
            USING fts5(
                texto,
                content='rag_chunks',
                content_rowid='rowid',
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO rag_chunks_fts(rowid, texto)
            SELECT rowid, texto
            FROM rag_chunks
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER IF NOT EXISTS rag_chunks_fts_ai
            AFTER INSERT ON rag_chunks
            BEGIN
                INSERT INTO rag_chunks_fts(rowid, texto)
                VALUES (new.rowid, new.texto);
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER IF NOT EXISTS rag_chunks_fts_ad
            AFTER DELETE ON rag_chunks
            BEGIN
                INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, texto)
                VALUES ('delete', old.rowid, old.texto);
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER IF NOT EXISTS rag_chunks_fts_au
            AFTER UPDATE ON rag_chunks
            BEGIN
                INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, texto)
                VALUES ('delete', old.rowid, old.texto);
                INSERT INTO rag_chunks_fts(rowid, texto)
                VALUES (new.rowid, new.texto);
            END
            """
        )
    )


def downgrade() -> None:
    """Drop FTS5 index and sync triggers for rag_chunks."""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS rag_chunks_fts_au"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS rag_chunks_fts_ad"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS rag_chunks_fts_ai"))
    op.execute(sa.text("DROP TABLE IF EXISTS rag_chunks_fts"))
