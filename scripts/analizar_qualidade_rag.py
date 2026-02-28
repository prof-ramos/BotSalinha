#!/usr/bin/env python
"""Script para analisar a qualidade do RAG Jurídico.

Verifica se o sistema RAG está capturando adequadamente:
- Jurisprudências (STF, STJ, tribunais superiores)
- Metadados de concursos (banca, ano, cargo)
- Questões de prova
- Material didático e comentários

Uso:
    uv run python scripts/analizar_qualidade_rag.py
"""

import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.models.rag_models import ChunkORM, DocumentORM


async def main() -> None:
    """Analisa a qualidade do RAG Jurídico."""
    import structlog

    log = structlog.get_logger(__name__)
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
        print("🔍 Análise de Qualidade do RAG Jurídico")
        print("=" * 80)

        # 1. Estatísticas gerais
        stmt_total = select(
            func.count(DocumentORM.id).label('total_docs'),
            func.sum(DocumentORM.chunk_count).label('total_chunks'),
        )
        result = await session.execute(stmt_total)
        total_docs, total_chunks = result.one()

        print(f"\n📊 Estatísticas Gerais:")
        print(f"   Documentos: {total_docs}")
        print(f"   Chunks: {total_chunks}")

        # 2. Análise de jurisprudência
        print(f"\n⚖️  Jurisprudência:")

        stmt_stf = select(func.count()).where(
            func.json_extract(ChunkORM.metadados, '$.marca_stf') == text('true')
        )
        result_stf = await session.execute(stmt_stf)
        count_stf = result_stf.scalar()

        stmt_stj = select(func.count()).where(
            func.json_extract(ChunkORM.metadados, '$.marca_stj') == text('true')
        )
        result_stj = await session.execute(stmt_stj)
        count_stj = result_stj.scalar()

        print(f"   Chunks com STF: {count_stf} ({count_stf/total_chunks*100:.1f}%)")
        print(f"   Chunks com STJ: {count_stj} ({count_stj/total_chunks*100:.1f}%)")

        # 3. Análise de concursos
        print(f"\n📝 Concursos:")

        stmt_concurso = select(func.count()).where(
            func.json_extract(ChunkORM.metadados, '$.marca_concurso') == text('true')
        )
        result_concurso = await session.execute(stmt_concurso)
        count_concurso = result_concurso.scalar()

        print(f"   Chunks com referência a concurso: {count_concurso} ({count_concurso/total_chunks*100:.1f}%)")

        # Top bancas
        stmt_bancas = select(
            func.json_extract(ChunkORM.metadados, '$.banca').label('banca'),
            func.count().label('total')
        ).where(
            func.json_extract(ChunkORM.metadados, '$.banca') != 'null'
        ).group_by('banca').order_by(
            func.count().desc()
        )

        result_bancas = await session.execute(stmt_bancas)
        bancas = result_bancas.all()

        print(f"\n   Top 20 Bancas:")
        for banca, count in bancas[:20]:
            print(f"      {banca:<20} {count:>6} chunks")

        # Distribuição por anos
        stmt_anos = select(
            func.json_extract(ChunkORM.metadados, '$.ano').label('ano'),
            func.count().label('total')
        ).where(
            func.json_extract(ChunkORM.metadados, '$.ano') != 'null'
        ).group_by('ano').order_by('ano')

        result_anos = await session.execute(stmt_anos)
        anos = result_anos.all()

        print(f"\n   Distribuição por Ano:")
        for ano, count in anos[:20]:  # Últimos 20 anos
            print(f"      {ano:<10} {count:>6} chunks")

        # 4. Direito Penal (se existirem)
        stmt_crime = select(func.count()).where(
            func.json_extract(ChunkORM.metadados, '$.marca_crime') == text('true')
        )
        result_crime = await session.execute(stmt_crime)
        count_crime = result_crime.scalar()

        stmt_pena = select(func.count()).where(
            func.json_extract(ChunkORM.metadados, '$.marca_pena') == text('true')
        )
        result_pena = await session.execute(stmt_pena)
        count_pena = result_pena.scalar()

        if count_crime > 0 or count_pena > 0:
            print(f"\n⚖️  Direito Penal:")
            print(f"   Chunks com 'crime': {count_crime}")
            print(f"   Chunks com 'pena': {count_pena}")

        # 5. Exemplos de chunks com jurisprudência
        print(f"\n💡 Exemplos de Chunks com Jurisprudência STF/STJ:")

        stmt_exemplos = select(ChunkORM).where(
            func.json_extract(ChunkORM.metadados, '$.marca_stf') == text('true')
        ).limit(3)

        result_exemplos = await session.execute(stmt_exemplos)
        exemplos = result_exemplos.scalars().all()

        for i, chunk in enumerate(exemplos, 1):
            metadata = json.loads(chunk.metadados)
            print(f"\n   [{i}] {chunk.documento_id} - {chunk.id}")
            print(f"       Texto: {chunk.texto[:100]}...")
            print(f"       Artigo: {metadata.get('artigo', 'N/A')}")
            print(f"       Banca: {metadata.get('banca', 'N/A')}")
            print(f"       Ano: {metadata.get('ano', 'N/A')}")

        # 6. Score de qualidade
        print(f"\n⭐ Score de Qualidade do RAG:")

        scores = []

        # Jurisprudência (30%)
        jurisprudencia_score = min((count_stf + count_stj) / total_chunks * 5, 1.0) if total_chunks > 0 else 0
        scores.append(('Jurisprudência', jurisprudencia_score, 0.3))
        print(f"   Jurisprudência: {jurisprudencia_score:.2%} (peso: 30%)")

        # Concursos (40%)
        concurso_score = min(count_concurso / total_chunks * 1.5, 1.0) if total_chunks > 0 else 0
        scores.append(('Concursos', concurso_score, 0.4))
        print(f"   Concursos: {concurso_score:.2%} (peso: 40%)")

        # Bancas variadas (20%)
        variedade_bancas = min(len([b for b, c in bancas if c >= 10]) / 20, 1.0)  # Máx 20 bancas = 100%
        scores.append(('Variedade Bancas', variedade_bancas, 0.2))
        print(f"   Variedade de Bancas: {variedade_bancas:.2%} (peso: 20%)")

        # Anos recentes (10%)
        anos_recentes = sum(1 for a, c in anos if int(a) >= 2015) / len(anos) if anos else 0
        scores.append(('Anos Recentes', anos_recentes, 0.1))
        print(f"   Anos Recentes (>=2015): {anos_recentes:.2%} (peso: 10%)")

        # Score total
        score_total = sum(score * peso for _, score, peso in scores)
        print(f"\n   🎯 SCORE TOTAL: {score_total:.2%}")

        if score_total >= 0.8:
            print(f"   ✅ EXCELENTE - RAG bem implementado para concursos")
        elif score_total >= 0.6:
            print(f"   ⚠️  BOM - RAG adequado, mas pode melhorar")
        else:
            print(f"   ❌ PRECISA MELHORAR - Faltam metadados importantes")

        # Salvar relatório
        metrics_dir = Path(__file__).parent.parent / "metricas"
        metrics_dir.mkdir(exist_ok=True)
        report_file = metrics_dir / f"rag_quality_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"RELATÓRIO DE QUALIDADE RAG JURÍDICO\n")
            f.write(f"Gerado em: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"ESTATÍSTICAS GERAIS:\n")
            f.write(f"Documentos: {total_docs}\n")
            f.write(f"Chunks: {total_chunks}\n\n")

            f.write(f"JURISPRUDÊNCIA:\n")
            f.write(f"STF: {count_stf} chunks ({count_stf/total_chunks*100:.1f}%)\n")
            f.write(f"STJ: {count_stj} chunks ({count_stj/total_chunks*100:.1f}%)\n\n")

            f.write(f"CONCURSOS:\n")
            f.write(f"Referências a concurso: {count_concurso} chunks ({count_concurso/total_chunks*100:.1f}%)\n\n")

            f.write(f"BANCAS TOP 20:\n")
            for banca, count in bancas[:20]:
                f.write(f"  {banca}: {count}\n")

            f.write(f"\nSCORE DE QUALIDADE: {score_total:.2%}\n")
            for nome, score, peso in scores:
                f.write(f"  {nome}: {score:.2%} (peso {peso*100:.0f}%)\n")

        print(f"\n📁 Relatório salvo em: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
