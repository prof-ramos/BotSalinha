#!/usr/bin/env python
"""Script para ingerir documentos RAG de legislação penal e gerar métricas.

Uso:
    uv run python scripts/ingest_penal.py

Este script irá:
1. Conectar ao banco SQLite
2. Ingerir todos os documentos DOCX da pasta de legislação penal
3. Gerar embeddings usando OpenAI API
4. Salvar chunks e embeddings no banco
5. Gerar métricas detalhadas em metricas/rag_penal_metrics.csv
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.rag.services.ingestion_service import IngestionService
from src.rag.services.embedding_service import EmbeddingService


async def main() -> None:
    """Executa a ingestão de documentos penais."""
    import structlog

    log = structlog.get_logger(__name__)

    settings = get_settings()

    # Obter API key via settings (suporta formato canônico e legado)
    api_key = settings.get_openai_api_key()
    if not api_key:
        print("❌ BOTSALINHA_OPENAI__API_KEY não configurada")
        print("💡 Defina BOTSALINHA_OPENAI__API_KEY no .env")
        print("   (ou use OPENAI_API_KEY para compatibilidade legada)")
        sys.exit(1)

    # Conectar ao banco
    db_url = str(settings.database.url)
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Diretório dos documentos penais
    penal_dir = Path("/Users/gabrielramos/Downloads/docs_rag/legislacao_grifada_e_anotada_atualiz_em_01_01_2026/penal")
    docx_files = list(penal_dir.glob("**/*.docx"))

    if not docx_files:
        print(f"❌ Nenhum arquivo DOCX encontrado em {penal_dir}")
        sys.exit(1)

    print(f"📚 Encontrados {len(docx_files)} documentos de legislação penal")
    print()

    # Preparar arquivo de métricas
    metrics_dir = Path(__file__).parent.parent / "metricas"
    metrics_dir.mkdir(exist_ok=True)
    metrics_file = metrics_dir / f"rag_penal_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Header do CSV
    csv_headers = [
        'timestamp',
        'documento',
        'arquivo',
        'chunks',
        'tokens',
        'custo_usd',
        'marca_concurso_count',
        'marca_stf_count',
        'marca_stj_count',
        'bancas_top_5',
        'anos_top_5',
        'status',
    ]

    metrics_data = []

    async with async_session_maker() as session:
        embedding_service = EmbeddingService(api_key=api_key)
        ingestion_service = IngestionService(
            session=session,
            embedding_service=embedding_service,
        )

        print(f"{'Documento':<60} {'Chunks':>10} {'Tokens':>10} {'Status':>10}")
        print("-" * 95)

        total_chunks = 0
        total_tokens = 0
        success_count = 0
        skipped_count = 0

        for docx_file in sorted(docx_files):
            doc_name = docx_file.stem
            doc_name_display = doc_name.replace("_", " ")[:60]

            try:
                print(f"{doc_name_display:<60}", end="", flush=True)

                # Verificar se já existe
                from src.models.rag_models import DocumentORM
                from sqlalchemy import select

                stmt = select(DocumentORM).where(DocumentORM.arquivo_origem == str(docx_file))
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"{existing.chunk_count:>10} {existing.token_count:>10} {'JÁ EXISTE':>10}")
                    skipped_count += 1
                    continue

                # Ingerir documento
                document = await ingestion_service.ingest_document(
                    file_path=str(docx_file),
                    document_name=doc_name,
                )

                print(f"{document.chunk_count:>10} {document.token_count:>10} {'✅':>10}")

                total_chunks += document.chunk_count
                total_tokens += document.token_count
                success_count += 1

                # Coletar métricas detalhadas
                from sqlalchemy import func

                chunk_stmt = select(
                    func.sum(func.json_extract(DocumentORM.chunks.property.mapper.class_.metadados, '$.marca_concurso')).label('concurso'),
                    func.sum(func.json_extract(DocumentORM.chunks.property.mapper.class_.metadados, '$.marca_stf')).label('stf'),
                    func.sum(func.json_extract(DocumentORM.chunks.property.mapper.class_.metadados, '$.marca_stj')).label('stj'),
                ).select_from(DocumentORM).where(DocumentORM.id == document.id)

                # Adicionar métrica ao CSV
                metrics_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'documento': doc_name,
                    'arquivo': str(docx_file),
                    'chunks': document.chunk_count,
                    'tokens': document.token_count,
                    'custo_usd': round(document.token_count * 0.02 / 1_000_000, 6),
                    'marca_concurso_count': 0,  # Preencher depois
                    'marca_stf_count': 0,
                    'marca_stj_count': 0,
                    'bancas_top_5': '',
                    'anos_top_5': '',
                    'status': 'success',
                })

            except Exception as e:
                print(f"{'ERRO':>22} ❌")
                log.error(
                    "ingest_document_failed",
                    document=doc_name,
                    file=str(docx_file),
                    error=str(e),
                    exc_info=True,
                )
                metrics_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'documento': doc_name,
                    'arquivo': str(docx_file),
                    'chunks': 0,
                    'tokens': 0,
                    'custo_usd': 0,
                    'marca_concurso_count': 0,
                    'marca_stf_count': 0,
                    'marca_stj_count': 0,
                    'bancas_top_5': '',
                    'anos_top_5': '',
                    'status': f'error: {str(e)[:50]}',
                })

        print("-" * 95)
        print(f"{'TOTAL':<60} {total_chunks:>10} {total_tokens:>10}")
        print()
        print(f"✅ {success_count}/{len(docx_files)} documentos ingeridos")
        print(f"⏭️  {skipped_count}/{len(docx_files)} documentos já existiam")
        print()
        print("📊 Estatísticas:")
        print(f"   • Total de chunks: {total_chunks}")
        print(f"   • Total de tokens: {total_tokens:,}")
        print(f"   • Custo estimado: ${total_tokens * 0.02 / 1_000_000:.4f} USD")

        # Salvar métricas em CSV
        with open(metrics_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(metrics_data)

        print(f"\n📁 Métricas salvas em: {metrics_file}")


if __name__ == "__main__":
    asyncio.run(main())
