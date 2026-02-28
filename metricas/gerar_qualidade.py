"""
Script for generating RAG Quality Metrics.
Evaluates semantic similarity and confidence distribution for test queries.
"""

import asyncio
import csv
import time
from pathlib import Path

import structlog

from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.query_service import QueryService
from src.rag.storage.vector_store import VectorStore
from src.rag.utils.confianca_calculator import ConfiancaCalculator
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

TEST_QUERIES = [
    "o que é estágio probatório?",
    "quais os requisitos para ser presidente da república?",
    "como funciona a licença maternidade?",
    "quais são os princípios da administração pública?",
    "o que é habeas corpus?",
    "qual o prazo para impetrar mandado de segurança?",
]


async def check_quality() -> None:
    """Evaluate RAG search quality and save results to CSV."""
    log.info("rag_quality_check_started", queries_count=len(TEST_QUERIES))

    results = []

    async with create_repository() as repo:
        async with repo.async_session_maker() as session:
            query_service = QueryService(
                session=session,
                embedding_service=EmbeddingService(),
                vector_store=VectorStore(session),
                confianca_calculator=ConfiancaCalculator(),
            )

            for query in TEST_QUERIES:
                log.info("testing_rag_quality", query=query)
                start_time = time.perf_counter()

                try:
                    context = await query_service.query(query, top_k=3)
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    avg_similarity = (
                        sum(context.similaridades) / len(context.similaridades)
                        if context.similaridades
                        else 0.0
                    )
                    max_similarity = max(context.similaridades) if context.similaridades else 0.0

                    results.append(
                        {
                            "query": query,
                            "confidence": context.confianca.value,
                            "avg_similarity": round(avg_similarity, 4),
                            "max_similarity": round(max_similarity, 4),
                            "chunks_retrieved": len(context.chunks_usados),
                            "duration_ms": round(duration_ms, 2),
                        }
                    )
                    log.info("query_quality_finished", confidence=context.confianca.value)

                except Exception as e:
                    log.error("query_quality_failed", query=query, error=str(e))
                    results.append(
                        {
                            "query": query,
                            "confidence": "erro",
                            "avg_similarity": 0.0,
                            "max_similarity": 0.0,
                            "chunks_retrieved": 0,
                            "duration_ms": 0.0,
                        }
                    )

    # Save results
    output_file = Path("metricas/qualidade_rag.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "query",
                "confidence",
                "avg_similarity",
                "max_similarity",
                "chunks_retrieved",
                "duration_ms",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    log.info("rag_quality_check_completed", output_file=str(output_file))


if __name__ == "__main__":
    asyncio.run(check_quality())
