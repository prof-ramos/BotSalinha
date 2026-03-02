"""add content_hash to rag_documents

Revision ID: 20260301_1200
Revises: 20260228_1000
Create Date: 2026-03-01 12:00:00.000000

"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260301_1200"
down_revision: str | None = "20260228_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add content_hash column with backfill and unique index."""
    op.add_column(
        "rag_documents",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )

    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Backfill using SQL expression with NULL normalization.
    # We keep a safe fallback for dialects without built-in SHA256 support.
    if dialect_name == "sqlite":
        raw_connection = bind.connection.dbapi_connection
        assert raw_connection is not None, "DBAPI connection must be available for SQLite"
        raw_connection.create_function(
            "sha256",
            1,
            lambda value: hashlib.sha256((value or "").encode("utf-8")).hexdigest(),
        )
        bind.execute(
            sa.text(
                """
                UPDATE rag_documents
                SET content_hash = sha256(COALESCE(nome, '') || '|' || COALESCE(arquivo_origem, ''))
                """
            )
        )
    elif dialect_name in {"postgres", "postgresql"}:
        # Criar extensão pgcrypto se não existir
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        bind.execute(
            sa.text(
                """
                UPDATE rag_documents
                SET content_hash = encode(
                    digest(COALESCE(nome, '') || '|' || COALESCE(arquivo_origem, ''), 'sha256'),
                    'hex'
                )
                """
            )
        )
    else:
        rows = bind.execute(sa.text("SELECT id, nome, arquivo_origem FROM rag_documents")).fetchall()
        for row in rows:
            payload = f"{row.nome or ''}|{row.arquivo_origem or ''}".encode()
            content_hash = hashlib.sha256(payload).hexdigest()
            bind.execute(
                sa.text("UPDATE rag_documents SET content_hash = :content_hash WHERE id = :id"),
                {"content_hash": content_hash, "id": row.id},
            )

    # Resolve duplicate hashes before creating unique index.
    duplicated_hashes = bind.execute(
        sa.text(
            """
            SELECT content_hash
            FROM rag_documents
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if duplicated_hashes:
        existing_hashes = {
            row[0]
            for row in bind.execute(
                sa.text("SELECT content_hash FROM rag_documents WHERE content_hash IS NOT NULL")
            ).fetchall()
        }
        for (duplicated_hash,) in duplicated_hashes:
            rows = bind.execute(
                sa.text(
                    """
                    SELECT id
                    FROM rag_documents
                    WHERE content_hash = :content_hash
                    ORDER BY id
                    """
                ),
                {"content_hash": duplicated_hash},
            ).fetchall()

            # Keep first row unchanged; re-hash remaining rows using deterministic salt.
            for row in rows[1:]:
                document_id = row[0]
                candidate_hash = hashlib.sha256(f"{duplicated_hash}:{document_id}".encode()).hexdigest()
                salt = 1
                while candidate_hash in existing_hashes:
                    candidate_hash = hashlib.sha256(
                        f"{duplicated_hash}:{document_id}:{salt}".encode()
                    ).hexdigest()
                    salt += 1

                bind.execute(
                    sa.text("UPDATE rag_documents SET content_hash = :content_hash WHERE id = :id"),
                    {"content_hash": candidate_hash, "id": document_id},
                )
                existing_hashes.add(candidate_hash)

    op.create_index(
        "ix_rag_documents_content_hash",
        "rag_documents",
        ["content_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Drop content_hash column and index."""
    op.drop_index("ix_rag_documents_content_hash", table_name="rag_documents")
    op.drop_column("rag_documents", "content_hash")
