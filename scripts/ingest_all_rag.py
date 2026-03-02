#!/usr/bin/env python
"""Ingestão operacional de documentos RAG (completo ou incremental).

Uso:
    uv run python scripts/ingest_all_rag.py --mode incremental
    uv run python scripts/ingest_all_rag.py --mode completo
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import structlog
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings  # noqa: E402
from src.models.rag_models import DocumentORM  # noqa: E402
from src.rag.services.embedding_service import EmbeddingService  # noqa: E402
from src.rag.services.ingestion_service import IngestionService  # noqa: E402
from src.utils.log_events import LogEvents  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse de argumentos CLI."""
    parser = argparse.ArgumentParser(
        prog="ingest_all_rag",
        description="Ingestão/reindexação operacional de documentos RAG",
    )
    parser.add_argument(
        "--mode",
        choices=["incremental", "completo"],
        default="incremental",
        help="Modo de execução (default: incremental)",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "plans" / "RAG",
        help="Diretório raiz de documentos DOCX",
    )
    parser.add_argument(
        "--pattern",
        default="*.docx",
        help="Glob de documentos (default: *.docx)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Busca recursiva de DOCX no diretório",
    )
    return parser.parse_args()


def _resolve_async_database_url(db_url: str) -> str:
    """Normaliza URL de banco para driver async."""
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return db_url


async def _run_incremental(
    session: AsyncSession,
    ingestion_service: IngestionService,
    docs_dir: Path,
    pattern: str,
    recursive: bool,
    metrics_writer: csv.writer,
    log: structlog.stdlib.BoundLogger,
) -> dict[str, int | float]:
    """Executa refresh incremental por hash de conteúdo."""
    files = sorted(docs_dir.rglob(pattern) if recursive else docs_dir.glob(pattern))
    if not files:
        print(f"❌ Nenhum arquivo encontrado em {docs_dir} para pattern={pattern}")
        return {
            "processed": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "chunks_total": 0,
            "tokens_total": 0,
            "duration_seconds": 0.0,
        }

    print(f"📚 Documentos encontrados: {len(files)}")
    print("🔁 Modo incremental ativado (hash de conteúdo)")
    print()
    print(f"{'Progresso':<12} {'Documento':<80} {'Status':<14} {'Chunks':>8}")
    print("-" * 122)

    start = time.perf_counter()
    updated = 0
    unchanged = 0
    failed = 0
    chunks_total = 0
    tokens_total = 0

    for index, docx_file in enumerate(files, 1):
        relative_display = str(docx_file.relative_to(docs_dir))
        doc_name_display = relative_display if len(relative_display) <= 80 else f"{relative_display[:77]}..."
        progress = f"{index}/{len(files)}"
        print(f"{progress:<12} {doc_name_display:<80}", end="", flush=True)

        existing = (
            await session.execute(select(DocumentORM).where(DocumentORM.arquivo_origem == str(docx_file)))
        ).scalar_one_or_none()
        previous_hash = existing.content_hash if existing else None
        previous_chunks = existing.chunk_count if existing else 0

        try:
            doc = await ingestion_service.ingest_document(
                file_path=str(docx_file),
                document_name=docx_file.stem,
            )
            chunks_total += doc.chunk_count
            tokens_total += doc.token_count

            if previous_hash == doc.content_hash and previous_chunks > 0:
                status = "UNCHANGED"
                unchanged += 1
            else:
                status = "UPDATED"
                updated += 1

            print(f" {status:<14} {doc.chunk_count:>8}")
            metrics_writer.writerow(
                [
                    datetime.now().isoformat(),
                    "incremental",
                    str(docx_file),
                    status.lower(),
                    doc.chunk_count,
                    doc.token_count,
                    "",
                ]
            )
        except Exception as exc:
            failed += 1
            print(f" {'FAILED':<14} {0:>8}")
            log.error(
                "rag_incremental_document_failed",
                document=str(docx_file),
                error_type=type(exc).__name__,
                error=str(exc),
                event_name="rag_incremental_document_failed",
            )
            metrics_writer.writerow(
                [
                    datetime.now().isoformat(),
                    "incremental",
                    str(docx_file),
                    "failed",
                    0,
                    0,
                    str(exc)[:200],
                ]
            )

    duration = time.perf_counter() - start
    print("-" * 122)
    print("✅ Incremental concluído")
    print(f"📄 Processados: {len(files)}")
    print(f"♻️ Atualizados: {updated}")
    print(f"⏭️ Sem alteração: {unchanged}")
    print(f"❌ Falhas: {failed}")
    print(f"📦 Chunks totais: {chunks_total:,}")
    print(f"🔤 Tokens totais: {tokens_total:,}")
    print(f"⏱️ Duração: {duration:.2f}s")

    return {
        "processed": len(files),
        "updated": updated,
        "unchanged": unchanged,
        "failed": failed,
        "chunks_total": chunks_total,
        "tokens_total": tokens_total,
        "duration_seconds": round(duration, 2),
    }


async def _run_full_reindex(
    ingestion_service: IngestionService,
    docs_dir: Path,
    pattern: str,
    recursive: bool,
) -> dict[str, int | float]:
    """Executa rebuild completo do índice RAG."""
    resolved_pattern = f"**/{pattern}" if recursive else pattern
    print("🧹 Reindexação completa: removendo índice atual e reconstruindo...")
    stats = await ingestion_service.reindex(
        documents_dir=str(docs_dir),
        pattern=resolved_pattern,
    )
    print("✅ Reindexação completa concluída")
    print(f"📄 Documentos: {int(stats['documents_count'])}")
    print(f"📦 Chunks: {int(stats['chunks_count'])}")
    print(f"⏱️ Duração: {float(stats['duration_seconds']):.2f}s")
    return stats


async def main() -> None:
    """Ponto de entrada do script."""
    args = parse_args()
    log = structlog.get_logger(__name__)
    settings = get_settings()

    api_key = settings.get_openai_api_key()
    if not api_key:
        print("❌ OPENAI_API_KEY não configurada")
        raise SystemExit(1)

    docs_dir = args.docs_dir.resolve()
    if not docs_dir.exists():
        print(f"❌ Diretório não encontrado: {docs_dir}")
        raise SystemExit(1)

    db_url = _resolve_async_database_url(str(settings.database.url))
    engine = create_async_engine(db_url, echo=settings.database.echo)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    metrics_dir = Path(__file__).resolve().parents[1] / "metricas"
    metrics_dir.mkdir(exist_ok=True)
    metrics_file = metrics_dir / f"rag_ingest_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    log.info(
        LogEvents.RAG_REINDEXACAO_INICIADA,
        mode=args.mode,
        docs_dir=str(docs_dir),
        pattern=args.pattern,
        recursive=args.recursive,
        event_name="rag_ingest_all_started",
    )

    try:
        with metrics_file.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                ["timestamp", "mode", "document", "status", "chunks", "tokens", "error"]
            )

            async with session_factory() as session:
                embedding_service = EmbeddingService(api_key=api_key)
                ingestion_service = IngestionService(
                    session=session,
                    embedding_service=embedding_service,
                )

                if args.mode == "completo":
                    stats = await _run_full_reindex(
                        ingestion_service=ingestion_service,
                        docs_dir=docs_dir,
                        pattern=args.pattern,
                        recursive=args.recursive,
                    )
                else:
                    stats = await _run_incremental(
                        session=session,
                        ingestion_service=ingestion_service,
                        docs_dir=docs_dir,
                        pattern=args.pattern,
                        recursive=args.recursive,
                        metrics_writer=writer,
                        log=log,
                    )

        log.info(
            LogEvents.RAG_REINDEXACAO_CONCLUIDA,
            mode=args.mode,
            docs_dir=str(docs_dir),
            stats=stats,
            metrics_file=str(metrics_file),
            event_name="rag_ingest_all_completed",
        )
        print(f"\n📁 Métricas salvas em: {metrics_file}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
