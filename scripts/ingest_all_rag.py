#!/usr/bin/env python
"""Script para ingerir TODOS os documentos RAG do diretório de legislação.

Uso:
    uv run python scripts/ingest_all_rag.py

Este script irá:
1. Varrer todos os subdiretórios de legislação grifada
2. Ingerir todos os arquivos DOCX encontrados
3. Gerar embeddings usando OpenAI API
4. Salvar chunks e embeddings no banco
5. Gerar métricas consolidadas
"""

import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.rag.services.ingestion_service import IngestionService
from src.rag.services.embedding_service import EmbeddingService
from src.models.rag_models import DocumentORM


async def main() -> None:
    """Executa a ingestão de todos os documentos."""
    import structlog

    log = structlog.get_logger(__name__)

    settings = get_settings()

    # Verificar API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.startswith("sk-"):
        print(f"❌ OPENAI_API_KEY não configurada")
        sys.exit(1)

    # Conectar ao banco
    db_url = str(settings.database.url)
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Diretório raiz da legislação
    legislacao_dir = Path("/Users/gabrielramos/Downloads/docs_rag/legislacao_grifada_e_anotada_atualiz_em_01_01_2026")

    # Encontrar todos os DOCX recursivamente
    docx_files = list(legislacao_dir.rglob("*.docx"))

    if not docx_files:
        print(f"❌ Nenhum arquivo DOCX encontrado em {legislacao_dir}")
        sys.exit(1)

    print(f"📚 Encontrados {len(docx_files)} documentos de legislação")
    print(f"💰 Custo estimado: ${len(docx_files) * 500 * 0.02 / 1_000_000:.2f} USD (estativa)")
    print()

    # Preparar arquivo de métricas
    metrics_dir = Path(__file__).parent.parent / "metricas"
    metrics_dir.mkdir(exist_ok=True)
    metrics_file = metrics_dir / f"rag_all_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    async with async_session_maker() as session:
        embedding_service = EmbeddingService(api_key=api_key)
        ingestion_service = IngestionService(
            session=session,
            embedding_service=embedding_service,
        )

        print(f"{'Progresso':<12} {'Documento':<80} {'Chunks':>8} {'Status':<10}")
        print("-" * 115)

        total_chunks = 0
        total_tokens = 0
        success_count = 0
        skipped_count = 0
        error_count = 0

        metrics_data = []
        csv_file = open(metrics_file, 'w', newline='', encoding='utf-8')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            'timestamp', 'categoria', 'documento', 'chunks', 'tokens',
            'custo_usd', 'status'
        ])

        for idx, docx_file in enumerate(sorted(docx_files), 1):
            # Determinar categoria (subdiretório)
            relative_path = docx_file.relative_to(legislacao_dir)
            categoria = relative_path.parts[0] if len(relative_path.parts) > 1 else "raiz"

            doc_name = docx_file.stem
            doc_name_display = f"{categoria}/{doc_name}"
            if len(doc_name_display) > 80:
                doc_name_display = doc_name_display[:77] + "..."

            progress = f"{idx}/{len(docx_files)}"
            print(f"{progress:<12} {doc_name_display:<80}", end="", flush=True)

            try:
                # Verificar se já existe
                stmt = select(DocumentORM).where(DocumentORM.arquivo_origem == str(docx_file))
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"{existing.chunk_count:>8} {'JÁ EXISTE':>10}")
                    skipped_count += 1
                    continue

                # Ingerir documento
                document = await ingestion_service.ingest_document(
                    file_path=str(docx_file),
                    document_name=doc_name,
                )

                print(f"{document.chunk_count:>8} {'✅':>10}")

                total_chunks += document.chunk_count
                total_tokens += document.token_count
                success_count += 1

                # Salvar métrica
                csv_writer.writerow([
                    datetime.now().isoformat(),
                    categoria,
                    doc_name,
                    document.chunk_count,
                    document.token_count,
                    round(document.token_count * 0.02 / 1_000_000, 6),
                    'success',
                ])

                # Mostrar progresso a cada 50 documentos
                if idx % 50 == 0:
                    print()
                    print(f"📊 Progresso: {idx}/{len(docx_files)} ({idx/len(docx_files)*100:.1f}%)")
                    print(f"   Tokens até agora: {total_tokens:,}")
                    print(f"   Custo até agora: ${total_tokens * 0.02 / 1_000_000:.4f} USD")
                    print()
                    print(f"{'Progresso':<12} {'Documento':<80} {'Chunks':>8} {'Status':<10}")
                    print("-" * 115)

            except Exception as e:
                print(f"{'ERRO':>22} ❌")
                error_count += 1
                log.error(
                    "ingest_document_failed",
                    document=doc_name,
                    file=str(docx_file),
                    error=str(e),
                    exc_info=True,
                )

                csv_writer.writerow([
                    datetime.now().isoformat(),
                    categoria,
                    doc_name,
                    0,
                    0,
                    0,
                    f'error: {str(e)[:50]}',
                ])

        csv_file.close()

        print("-" * 115)
        print(f"{'TOTAL':<12} {total_chunks:>8}")
        print()
        print(f"✅ {success_count}/{len(docx_files)} documentos ingeridos")
        print(f"⏭️  {skipped_count}/{len(docx_files)} documentos já existiam")
        print(f"❌ {error_count}/{len(docx_files)} documentos com erro")
        print()
        print(f"📊 Estatísticas Finais:")
        print(f"   • Total de chunks: {total_chunks:,}")
        print(f"   • Total de tokens: {total_tokens:,}")
        print(f"   • Custo estimado: ${total_tokens * 0.02 / 1_000_000:.2f} USD")
        print(f"\n📁 Métricas salvas em: {metrics_file}")


if __name__ == "__main__":
    asyncio.run(main())
