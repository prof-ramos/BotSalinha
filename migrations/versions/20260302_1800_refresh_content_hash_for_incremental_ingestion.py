"""add chunk content_hash and backfill legacy hashes for incremental refresh

Revision ID: 20260302_1800
Revises: 20260302_1400
Create Date: 2026-03-02 18:00:00.000000

"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260302_1800"
down_revision: str | None = "20260302_1400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sha256_payload(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _backfill_chunk_hashes(bind: sa.Connection) -> None:
    """Backfill rag_chunks.content_hash from real chunk payload."""
    dialect_name = bind.dialect.name

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
                UPDATE rag_chunks
                SET content_hash = sha256(COALESCE(texto, '') || '|' || COALESCE(metadados, ''))
                WHERE content_hash IS NULL
                """
            )
        )
        return

    if dialect_name in {"postgres", "postgresql"}:
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        bind.execute(
            sa.text(
                """
                UPDATE rag_chunks
                SET content_hash = encode(
                    digest(COALESCE(texto, '') || '|' || COALESCE(metadados, ''), 'sha256'),
                    'hex'
                )
                WHERE content_hash IS NULL
                """
            )
        )
        return

    rows = bind.execute(
        sa.text("SELECT id, texto, metadados FROM rag_chunks WHERE content_hash IS NULL")
    ).fetchall()
    for row in rows:
        chunk_hash = _sha256_payload(f"{row.texto or ''}|{row.metadados or ''}")
        bind.execute(
            sa.text("UPDATE rag_chunks SET content_hash = :content_hash WHERE id = :id"),
            {"content_hash": chunk_hash, "id": row.id},
        )


def _backfill_document_hashes(bind: sa.Connection) -> None:
    """Backfill rag_documents.content_hash using ordered chunk content hashes."""
    document_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM rag_documents ORDER BY id")
        ).fetchall()
    ]

    assigned_hashes: set[str] = set()

    for document_id in document_ids:
        chunk_hash_rows = bind.execute(
            sa.text(
                """
                SELECT content_hash
                FROM rag_chunks
                WHERE documento_id = :document_id
                ORDER BY id
                """
            ),
            {"document_id": document_id},
        ).fetchall()

        if chunk_hash_rows:
            payload = "|".join(str(row[0] or "") for row in chunk_hash_rows)
        else:
            fallback_row = bind.execute(
                sa.text(
                    """
                    SELECT COALESCE(nome, '') AS nome, COALESCE(arquivo_origem, '') AS arquivo_origem
                    FROM rag_documents
                    WHERE id = :document_id
                    """
                ),
                {"document_id": document_id},
            ).fetchone()
            assert fallback_row is not None
            payload = f"{fallback_row.nome}|{fallback_row.arquivo_origem}|{document_id}"

        base_hash = _sha256_payload(payload)
        candidate_hash = base_hash
        salt = 1
        while candidate_hash in assigned_hashes:
            candidate_hash = _sha256_payload(f"{base_hash}:{document_id}:{salt}")
            salt += 1

        bind.execute(
            sa.text("UPDATE rag_documents SET content_hash = :content_hash WHERE id = :id"),
            {"content_hash": candidate_hash, "id": document_id},
        )
        assigned_hashes.add(candidate_hash)


def upgrade() -> None:
    """Add rag_chunks.content_hash and backfill legacy hashes for incremental refresh."""
    op.add_column(
        "rag_chunks",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_rag_chunks_content_hash",
        "rag_chunks",
        ["content_hash"],
        unique=False,
    )

    bind = op.get_bind()
    _backfill_chunk_hashes(bind)
    _backfill_document_hashes(bind)


def downgrade() -> None:
    """Drop rag_chunks.content_hash and its index."""
    op.drop_index("ix_rag_chunks_content_hash", table_name="rag_chunks")
    op.drop_column("rag_chunks", "content_hash")
