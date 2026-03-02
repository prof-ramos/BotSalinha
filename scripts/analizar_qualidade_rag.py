#!/usr/bin/env python
"""Gera baseline offline de retrieval para o RAG jurídico.

Métricas calculadas (sem geração):
- Recall@1/3/5
- MRR
- nDCG@5
- Taxa de citação correta

Saídas versionadas:
- CSV por consulta
- CSV agregado por tipo
- JSON completo da execução
- arquivos *_latest para comparação rápida
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from metricas.baseline_retrieval import (
    aggregate_results,
    default_retrieval_benchmark,
    evaluate_case,
    summary_rows,
)
from src.config.settings import get_settings
from src.models.rag_models import DocumentORM
from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.query_service import QueryService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerar baseline offline de retrieval do RAG jurídico",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        default="metricas",
        help="Diretório de saída para snapshots",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Quantidade de chunks para avaliação por consulta",
    )
    return parser


def _ensure_async_db_url(db_url: str) -> str:
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return db_url


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_latest(latest_path: Path, content: str) -> None:
    latest_path.write_text(content, encoding="utf-8")


async def _run_baseline(output_dir: Path, top_k: int) -> dict[str, Path]:
    settings = get_settings()
    db_url = _ensure_async_db_url(str(settings.database.url))

    engine = create_async_engine(db_url)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    benchmark = default_retrieval_benchmark()

    query_rows: list[dict[str, Any]] = []

    async with async_session_maker() as session:
        doc_count_stmt = select(func.count(DocumentORM.id))
        doc_result = await session.execute(doc_count_stmt)
        doc_count = doc_result.scalar() or 0

        if doc_count == 0:
            raise RuntimeError(
                "Nenhum documento indexado no RAG. Rode a ingestão antes do baseline offline."
            )

        query_service = QueryService(
            session=session,
            embedding_service=EmbeddingService(),
        )

        query_results = []
        for case in benchmark:
            context = await query_service.query(query_text=case.query, top_k=top_k)
            result = evaluate_case(case=case, retrieved_chunks=context.chunks_usados)
            query_results.append(result)
            query_rows.append(result.to_dict())

    aggregated = aggregate_results(query_results)
    summary = summary_rows(aggregated)

    output_dir.mkdir(parents=True, exist_ok=True)

    queries_csv = output_dir / f"rag_retrieval_baseline_{timestamp}.csv"
    summary_csv = output_dir / f"rag_retrieval_baseline_summary_{timestamp}.csv"
    snapshot_json = output_dir / f"rag_retrieval_baseline_{timestamp}.json"

    query_fieldnames = [
        "case_id",
        "tipo",
        "query",
        "relevant_rank",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "citation_correct",
        "top_source",
    ]
    summary_fieldnames = [
        "segmento",
        "queries",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "citation_correct_rate",
    ]

    _write_csv(queries_csv, query_rows, query_fieldnames)
    _write_csv(summary_csv, summary, summary_fieldnames)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "top_k": top_k,
        "benchmark_size": len(benchmark),
        "results": query_rows,
        "summary": aggregated,
        "artifacts": {
            "queries_csv": str(queries_csv),
            "summary_csv": str(summary_csv),
        },
    }
    snapshot_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _write_latest(output_dir / "rag_retrieval_baseline_latest.csv", queries_csv.read_text(encoding="utf-8"))
    _write_latest(
        output_dir / "rag_retrieval_baseline_summary_latest.csv",
        summary_csv.read_text(encoding="utf-8"),
    )
    _write_latest(
        output_dir / "rag_retrieval_baseline_latest.json",
        snapshot_json.read_text(encoding="utf-8"),
    )

    await engine.dispose()

    return {
        "queries_csv": queries_csv,
        "summary_csv": summary_csv,
        "snapshot_json": snapshot_json,
    }


async def main() -> None:
    args = _build_parser().parse_args()
    output_dir = Path(args.output_dir)

    artifacts = await _run_baseline(output_dir=output_dir, top_k=args.top_k)

    print("Baseline offline de retrieval gerado com sucesso.")
    print(f"- CSV (consultas): {artifacts['queries_csv']}")
    print(f"- CSV (sumário): {artifacts['summary_csv']}")
    print(f"- Snapshot JSON: {artifacts['snapshot_json']}")


if __name__ == "__main__":
    asyncio.run(main())
