"""
Ingestão especializada para o arquivo CF/88 misto.

Uso:
    uv run python scripts/ingest_cf_rag.py <caminho_do_docx> [opções]

O script executa o pipeline completo de ingestão e, após persistir os chunks,
cria os ``content_links`` entre chunks de lei (``lei_cf``) e chunks vizinhos de
jurisprudência/questão de prova ligados ao mesmo artigo.

Exemplos:
    uv run python scripts/ingest_cf_rag.py data/documents/cf_de_1988_atualiz_ate_ec_138.docx
    uv run python scripts/ingest_cf_rag.py data/documents/cf.docx --name "CF/88" --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root is in path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings
from src.models.rag_models import ChunkORM, ContentLinkORM
from src.rag.parser.cf_parser import CFContentClassifier
from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.ingestion_service import IngestionService

log = structlog.get_logger(__name__)


async def _create_content_links(
    session: AsyncSession,
    documento_id: int,
    window: int = 5,
) -> int:
    """
    Scan chunks from a document and create content_links between ``lei_cf`` chunks
    and their neighboring ``jurisprudencia`` / ``questao_prova`` chunks.

    A sliding window of ``window`` chunks is used to find adjacent non-lei chunks
    that belong to the same article context.

    Returns the number of links created.
    """
    # Load all chunks for this document ordered by creation (proxy for position)
    result = await session.execute(
        select(ChunkORM)
        .where(ChunkORM.documento_id == documento_id)
        .order_by(ChunkORM.created_at, ChunkORM.id)
    )
    chunks: list[ChunkORM] = list(result.scalars().all())

    if not chunks:
        return 0

    links_created = 0
    lei_indices = [i for i, c in enumerate(chunks) if c.source_type == "lei_cf"]

    link_type_map: dict[str, str] = {
        "jurisprudencia": "interpreta",
        "questao_prova": "cobrada_em",
        "emenda_constitucional": "atualizacao",
        "comentario": "interpreta",
    }

    for lei_idx in lei_indices:
        lei_chunk = chunks[lei_idx]
        lei_meta: dict = {}
        try:
            lei_meta = json.loads(lei_chunk.metadados)
        except Exception:
            pass
        lei_artigo = lei_meta.get("artigo") or lei_meta.get("article")

        # Look forward and backward within the window for related chunks
        start = max(0, lei_idx - window)
        end = min(len(chunks), lei_idx + window + 1)

        for j in range(start, end):
            if j == lei_idx:
                continue
            neighbor = chunks[j]
            if neighbor.source_type not in link_type_map:
                continue

            # Only link if they share the same artigo context, or the neighbor
            # has no artigo (i.e., it's a comment right next to this lei chunk)
            neighbor_meta: dict = {}
            try:
                neighbor_meta = json.loads(neighbor.metadados)
            except Exception:
                pass
            neighbor_artigo = neighbor_meta.get("artigo") or neighbor_meta.get("article")

            if lei_artigo and neighbor_artigo and lei_artigo != neighbor_artigo:
                continue  # Different article — skip

            link = ContentLinkORM(
                id=str(uuid.uuid4()),
                chunk_id=lei_chunk.id,
                linked_chunk_id=neighbor.id,
                link_type=link_type_map[neighbor.source_type],
                created_at=datetime.now(UTC),
            )
            session.add(link)
            links_created += 1

    await session.commit()
    return links_created


async def _run(
    file_path: str,
    document_name: str,
    dry_run: bool,
    replace: bool,
) -> None:
    settings = get_settings()
    db_url = settings.database.url.replace("sqlite:///", "sqlite+aiosqlite:///")

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        embedding_service = EmbeddingService()
        service = IngestionService(session=session, embedding_service=embedding_service)

        if dry_run:
            # Validate file and show classification preview without writing
            clf = CFContentClassifier()
            from src.rag.parser.docx_parser import DOCXParser

            parser = DOCXParser()
            paragraphs = await parser.parse(file_path)
            counts: dict[str, int] = {}
            for para in paragraphs:
                result = clf.classify(para.get("text", ""))
                counts[result.source_type] = counts.get(result.source_type, 0) + 1
            print("\nDry-run — classification preview:")
            for st, count in sorted(counts.items()):
                print(f"  {st:30s}: {count:5d} parágrafos")
            print(f"\nTotal parágrafos: {sum(counts.values())}")
            await engine.dispose()
            return

        if replace:
            from sqlalchemy import delete as sa_delete

            from src.models.rag_models import DocumentORM

            existing = await session.execute(
                select(DocumentORM).where(DocumentORM.nome == document_name)
            )
            doc_orm = existing.scalar_one_or_none()
            if doc_orm is not None:
                await session.execute(
                    sa_delete(ChunkORM).where(ChunkORM.documento_id == doc_orm.id)
                )
                await session.delete(doc_orm)
                await session.commit()
                print(f"Documento '{document_name}' removido para reindexação.")

        print(f"Ingerindo '{document_name}' de {file_path} …")
        doc = await service.ingest_document(file_path=file_path, document_name=document_name)

        print(f"  chunks criados   : {doc.chunk_count}")
        print(f"  tokens estimados : {doc.token_count}")

        # Build content_links
        print("Criando content_links …")
        links = await _create_content_links(session, documento_id=doc.id)
        print(f"  links criados    : {links}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestão especializada para CF/88 (documento misto)."
    )
    parser.add_argument("file", help="Caminho para o arquivo .docx")
    parser.add_argument(
        "--name",
        default="CF/88",
        help="Nome do documento no banco (padrão: 'CF/88')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra classificação sem gravar no banco",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remove documento existente antes de reingerir",
    )
    args = parser.parse_args()

    asyncio.run(
        _run(
            file_path=args.file,
            document_name=args.name,
            dry_run=args.dry_run,
            replace=args.replace,
        )
    )


if __name__ == "__main__":
    main()
