#!/usr/bin/env python
"""Script para gerar relatório consolidado de métricas RAG.

Gera estatísticas detalhadas do sistema RAG incluindo:
- Estatísticas gerais de documentos e chunks
- Análise de metadados (concurso, STF, STJ)
- Distribuição por tipo de documento
- Performance de ingestão
"""

import asyncio
import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.models.rag_models import ChunkORM, DocumentORM


async def main() -> None:
    """Gera relatório de métricas RAG."""
    settings = get_settings()

    # Conectar ao banco
    db_url = str(settings.database.url)
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        print("📊 Gerando Relatório de Métricas RAG")
        print("=" * 80)

        # Estatísticas gerais
        stmt_docs = select(
            func.count(DocumentORM.id).label('total_docs'),
            func.sum(DocumentORM.chunk_count).label('total_chunks'),
            func.sum(DocumentORM.token_count).label('total_tokens')
        )
        result = await session.execute(stmt_docs)
        row = result.one()

        print(f"\n📈 Estatísticas Gerais:")
        print(f"   Documentos: {row.total_docs}")
        print(f"   Chunks: {row.total_chunks:,}")
        print(f"   Tokens: {row.total_tokens:,}")
        print(f"   Custo estimado: ${row.total_tokens * 0.02 / 1_000_000:.2f} USD")

        # Top documentos por tamanho
        stmt_top = select(DocumentORM).order_by(
            DocumentORM.token_count.desc()
        ).limit(10)
        result_top = await session.execute(stmt_top)
        top_docs = result_top.scalars().all()

        print(f"\n📚 Top 10 Documentos por Tokens:")
        for doc in top_docs:
            print(f"   {doc.nome:<50} {doc.token_count:>10,} tokens | {doc.chunk_count:>4} chunks")

        # Análise de metadados
        stmt_meta = select(
            func.sum(func.json_extract(ChunkORM.metadados, '$.marca_concurso')).label('concurso'),
            func.sum(func.json_extract(ChunkORM.metadados, '$.marca_stf')).label('stf'),
            func.sum(func.json_extract(ChunkORM.metadados, '$.marca_stj')).label('stj'),
            func.count(ChunkORM.id).label('total')
        )
        result_meta = await session.execute(stmt_meta)
        meta_row = result_meta.one()

        print(f"\n🏷️  Metadados de Jurisprudência/Concurso:")
        print(f"   marca_concurso: {meta_row.concurso} ({meta_row.concurso / meta_row.total * 100:.1f}%)")
        print(f"   marca_stf: {meta_row.stf} ({meta_row.stf / meta_row.total * 100:.1f}%)")
        print(f"   marca_stj: {meta_row.stj} ({meta_row.stj / meta_row.total * 100:.1f}%)")

        # Bancas mais comuns
        stmt_bancas = select(
            func.json_extract(ChunkORM.metadados, '$.banca').label('banca'),
            func.count().label('total')
        ).where(
            func.json_extract(ChunkORM.metadados, '$.banca') != 'null'
        ).group_by('banca').order_by(
            func.count().desc()
        ).limit(15)

        result_bancas = await session.execute(stmt_bancas)
        bancas = result_bancas.all()

        print(f"\n🏛️  Top 15 Bancas:")
        for banca, count in bancas:
            print(f"   {banca:<15} {count:>6} chunks")

        # Distribuição por tipo de documento
        print(f"\n📂 Distribuição por Tipo:")

        tipos = {
            'CF/88': 'cf de 1988',
            'Lei 8.112/90': 'regime juridico dos servidores',
            'Código Penal': 'codigo_penal',
            'Súmulas': 'sumulas',
            'Leis Penais': ['penal', 'crime', 'hediondos', 'drogas', 'lavagem', 'tortura'],
        }

        for tipo_nome, padrão in tipos.items():
            if isinstance(padrão, str):
                stmt_tipo = select(func.count()).where(DocumentORM.nome.like(f'%{padrão}%'))
            else:
                conditions = [DocumentORM.nome.like(f'%{p}%') for p in padrão]
                stmt_tipo = select(func.count()).where(
                    *conditions
                )

            result_tipo = await session.execute(stmt_tipo)
            count = result_tipo.scalar()

            print(f"   {tipo_nome:<20} {count:>6} documentos")

        # Salvar relatório CSV
        metrics_dir = Path(__file__).parent.parent / "metricas"
        metrics_dir.mkdir(exist_ok=True)
        report_file = metrics_dir / f"rag_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(report_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Métrica', 'Valor'])

            writer.writerow(['Total Documentos', row.total_docs])
            writer.writerow(['Total Chunks', row.total_chunks])
            writer.writerow(['Total Tokens', row.total_tokens])
            writer.writerow(['Custo Estimado USD', f"${row.total_tokens * 0.02 / 1_000_000:.2f}"])
            writer.writerow(['Chunks com marca_concurso', meta_row.concurso])
            writer.writerow(['Chunks com marca_stf', meta_row.stf])
            writer.writerow(['Chunks com marca_stj', meta_row.stj])
            writer.writerow(['Timestamp', datetime.now().isoformat()])

        print(f"\n📁 Relatório salvo em: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
