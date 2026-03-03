#!/usr/bin/env python3
"""
Migrate embeddings from SQLite to ChromaDB.

Usage:
    uv run python scripts/migrate_to_chroma.py [--dry-run] [--batch-size N]
"""

import asyncio
import sys
from pathlib import Path

import click
import structlog
from tqdm import tqdm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.models.rag_models import ChunkORM
from src.rag.storage.chroma_store import ChromaStore
from src.storage.factory import create_repository
from src.storage.sqlite_repository import SQLiteRepository
from src.utils.logger import setup_logging

log = structlog.get_logger(__name__)


def migrate_embeddings_to_chroma(
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    """
    Migrate embeddings from SQLite to ChromaDB.

    Args:
        batch_size: Number of chunks per batch
        dry_run: Simulate migration without writing

    Returns:
        Number of chunks migrated
    """
    settings = get_settings()

    # Ativar ChromaDB temporariamente
    original_enabled = settings.rag.chroma.enabled
    settings.rag.chroma.enabled = True

    async def _migrate() -> int:
        async with create_repository() as repo:
            # Cast to SQLiteRepository to access session maker
            sqlite_repo: SQLiteRepository = repo  # type: ignore[assignment]

            # Create session from the session maker
            async with sqlite_repo.async_session_maker() as session:
                # Buscar todos os chunks com embeddings
                stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None))
                result = await session.execute(stmt)
                chunk_orms = result.scalars().all()

                total_chunks = len(chunk_orms)
                log.info("migration_start", total_chunks=total_chunks, batch_size=batch_size)

                if dry_run:
                    log.info("dry_run_mode", chunks_to_migrate=total_chunks)
                    return total_chunks

                # Criar ChromaStore
                chroma_store = ChromaStore(session)

            # Processar em batches
            migrated = 0
            with tqdm(total=total_chunks, desc="Migrando chunks") as pbar:
                for i in range(0, total_chunks, batch_size):
                    batch = chunk_orms[i:i + batch_size]

                    # Converter para (Chunk, embedding)
                    chunks_with_embeddings = []
                    for chunk_orm in batch:
                        from src.rag.models import Chunk, ChunkMetadata
                        import json

                        metadata_dict = json.loads(chunk_orm.metadados)
                        metadata = ChunkMetadata(**metadata_dict)

                        chunk = Chunk(
                            chunk_id=chunk_orm.id,
                            documento_id=chunk_orm.documento_id,
                            texto=chunk_orm.texto,
                            metadados=metadata,
                            token_count=chunk_orm.token_count,
                            posicao_documento=0.0,
                        )

                        from src.rag.storage.vector_store import deserialize_embedding
                        # Type: ignore because WHERE clause ensures embedding is not None
                        embedding = deserialize_embedding(chunk_orm.embedding)  # type: ignore[arg-type]

                        chunks_with_embeddings.append((chunk, embedding))

                    # Escrever no ChromaDB
                    await chroma_store.add_embeddings(chunks_with_embeddings)

                    migrated += len(batch)
                    pbar.update(len(batch))

                    log.debug(
                        "migration_batch",
                        batch_num=i // batch_size + 1,
                        batch_size=len(batch),
                        migrated_total=migrated,
                    )

            log.info("migration_complete", migrated=migrated)
            return migrated

    try:
        result = asyncio.run(_migrate())
        return result
    finally:
        settings.rag.chroma.enabled = original_enabled


def validate_migration() -> dict[str, int]:
    """Validate migration by comparing counts."""
    async def _validate() -> dict[str, int]:
        async with create_repository() as repo:
            # Cast to SQLiteRepository to access session maker
            sqlite_repo: SQLiteRepository = repo  # type: ignore[assignment]

            # Create session from the session maker
            async with sqlite_repo.async_session_maker() as session:
                # Contar chunks no SQLite
                stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None))
                result = await session.execute(stmt)
                sqlite_count = len(result.scalars().all())

                # Contar chunks no ChromaDB
                chroma_store = ChromaStore(session)
                chroma_count = await chroma_store.count_chunks()

                return {
                    "sqlite_count": sqlite_count,
                    "chroma_count": chroma_count,
                    "match": 1 if sqlite_count == chroma_count else 0,
                }

    return asyncio.run(_validate())


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate migration without writing to ChromaDB",
)
@click.option(
    "--batch-size",
    default=100,
    type=int,
    help="Number of chunks per batch (default: 100)",
)
@click.option(
    "--validate",
    is_flag=True,
    help="Validate migration by comparing counts",
)
def main(dry_run: bool = False, batch_size: int = 100, validate: bool = False) -> None:
    """Migrate embeddings from SQLite to ChromaDB."""
    setup_logging()

    if validate:
        log.info("validating_migration")
        results = validate_migration()
        click.echo(f"SQLite chunks: {results['sqlite_count']}")
        click.echo(f"ChromaDB chunks: {results['chroma_count']}")
        click.echo(f"Match: {'YES' if results['match'] else 'NO'}")
        return

    log.info("migration_starting", dry_run=dry_run, batch_size=batch_size)

    try:
        migrated = migrate_embeddings_to_chroma(batch_size=batch_size, dry_run=dry_run)
        click.echo(f"\n✓ Migration complete: {migrated} chunks migrated")

        if not dry_run:
            # Automatic validation
            results = validate_migration()
            if results["match"]:
                click.echo(f"✓ Validation passed: {results['chroma_count']} chunks in ChromaDB")
            else:
                click.echo(f"⚠ Validation warning: SQLite={results['sqlite_count']}, ChromaDB={results['chroma_count']}")

    except Exception as e:
        log.error("migration_failed", error=str(e))
        click.echo(f"\n✗ Migration failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
