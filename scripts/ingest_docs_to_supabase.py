from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from supabase import create_client

from src.config.settings import get_settings
from src.models.rag_models import ChunkORM, ContentLinkORM
from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.ingestion_service import IngestionService

DOC_DIRS = [
    Path('/root/BotSalinha/data/sumulas_tse_stj_stf_e_tnu_atualiz_01_01_2026_2'),
    Path('/root/BotSalinha/data/legislacao_grifada_e_anotada_atualiz_em_01_01_2026'),
]

MAX_DOCS = int(os.getenv('MAX_DOCS', '0'))
BATCH_SIZE = int(os.getenv('SUPABASE_BATCH_SIZE', '100'))
UPSERT_RETRIES = int(os.getenv('SUPABASE_UPSERT_RETRIES', '5'))
UPSERT_RETRY_DELAY_SEC = float(os.getenv('SUPABASE_UPSERT_RETRY_DELAY_SEC', '2'))
CHECKPOINT_FILE = Path(
    os.getenv(
        'INGEST_CHECKPOINT_FILE',
        '/root/BotSalinha/data/ingest_supabase_checkpoint.jsonl',
    )
)
ERROR_LOG_FILE = Path(
    os.getenv(
        'INGEST_ERROR_LOG_FILE',
        '/root/BotSalinha/data/ingest_supabase_errors.log',
    )
)


def _to_async_db_url(url: str) -> str:
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    return url


def _chunk_payload(c: ChunkORM) -> dict:
    emb = np.frombuffer(c.embedding, dtype=np.float32).tolist() if c.embedding else None
    return {
        'id': c.id,
        'documento_id': c.documento_id,
        'texto': c.texto,
        'metadados': json.loads(c.metadados),
        'content_hash': c.content_hash,
        'metadata_version': c.metadata_version,
        'token_count': c.token_count,
        'embedding': emb,
    }


def _upsert_batched(table: Any, rows: list[dict[str, Any]], batch_size: int) -> None:
    if not rows:
        return
    for start in range(0, len(rows), batch_size):
        payload = rows[start:start + batch_size]
        attempt = 0
        while True:
            try:
                table.upsert(payload).execute()
                break
            except Exception:
                attempt += 1
                if attempt >= UPSERT_RETRIES:
                    raise
                time.sleep(UPSERT_RETRY_DELAY_SEC * attempt)


def _load_completed_paths() -> set[str]:
    if not CHECKPOINT_FILE.exists():
        return set()
    completed: set[str] = set()
    for line in CHECKPOINT_FILE.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            path = payload.get('file_path')
            if isinstance(path, str):
                completed.add(path)
        except json.JSONDecodeError:
            continue
    return completed


def _append_checkpoint(file_path: str, status: str, details: dict[str, Any]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'ts': int(time.time()),
        'status': status,
        'file_path': file_path,
        **details,
    }
    with CHECKPOINT_FILE.open('a', encoding='utf-8') as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + '\n')


def _append_error(file_path: str, err: str) -> None:
    ERROR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ERROR_LOG_FILE.open('a', encoding='utf-8') as fp:
        fp.write(f'[{int(time.time())}] file={file_path} err={err}\n')


async def main() -> None:
    supabase_url = os.environ['BOTSALINHA_RAG__SUPABASE__URL']
    supabase_key = os.environ['BOTSALINHA_RAG__SUPABASE__SERVICE_KEY']

    settings = get_settings()
    db_url = _to_async_db_url(str(settings.database.url))

    engine = create_async_engine(db_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    embedding_service = EmbeddingService()
    supa = create_client(supabase_url, supabase_key)

    files: list[Path] = []
    for d in DOC_DIRS:
        files.extend(sorted(d.rglob('*.docx')))
    if MAX_DOCS > 0:
        files = files[:MAX_DOCS]
    completed_paths = _load_completed_paths()
    files = [f for f in files if str(f) not in completed_paths]

    print(f'total_docx_pending={len(files)} already_completed={len(completed_paths)}', flush=True)

    ok = 0
    failed = 0

    async with session_maker() as session:
        ingestion = IngestionService(session=session, embedding_service=embedding_service)

        for i, docx in enumerate(files, 1):
            print(f'[{i}/{len(files)}] ingest {docx}', flush=True)
            try:
                doc = await ingestion.ingest_document(str(docx), docx.stem)

                doc_row = {
                    'id': doc.id,
                    'nome': doc.nome,
                    'arquivo_origem': doc.arquivo_origem,
                    'content_hash': doc.content_hash,
                    'schema_version': 3,
                    'chunk_count': doc.chunk_count,
                    'token_count': doc.token_count,
                }
                supa.table('rag_documents').upsert(doc_row).execute()

                chunks = (
                    await session.execute(select(ChunkORM).where(ChunkORM.documento_id == doc.id))
                ).scalars().all()
                _upsert_batched(supa.table('rag_chunks'), [_chunk_payload(c) for c in chunks], BATCH_SIZE)

                chunk_ids = [c.id for c in chunks]
                links = []
                if chunk_ids:
                    try:
                        links = (
                            await session.execute(
                                select(ContentLinkORM).where(ContentLinkORM.article_chunk_id.in_(chunk_ids))
                            )
                        ).scalars().all()
                    except OperationalError:
                        links = []
                link_rows = [
                    {
                        'id': l.id,
                        'article_chunk_id': l.article_chunk_id,
                        'linked_chunk_id': l.linked_chunk_id,
                        'link_type': l.link_type,
                    }
                    for l in links
                ]
                _upsert_batched(supa.table('content_links'), link_rows, BATCH_SIZE)

                ok += 1
                _append_checkpoint(
                    file_path=str(docx),
                    status='ok',
                    details={
                        'document_id': doc.id,
                        'chunks': len(chunks),
                        'links': len(link_rows),
                    },
                )
                print(
                    f'  ok document_id={doc.id} chunks={len(chunks)} links={len(link_rows)}',
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                _append_checkpoint(
                    file_path=str(docx),
                    status='error',
                    details={'error': str(exc)},
                )
                _append_error(str(docx), str(exc))
                print(f'  error file={docx} err={exc}', flush=True)

    await engine.dispose()
    print(f'finished ok={ok} failed={failed} total={len(files)}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
