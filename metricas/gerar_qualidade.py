"""
Script for generating RAG Quality Metrics.
Evaluates semantic similarity and confidence distribution for test queries.
"""

import asyncio
import csv
import structlog
import time
from pathlib import Path

from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.query_service import QueryService
from src.rag.storage.vector_store import VectorStore
from src.rag.utils.confianca_calculator import ConfiancaCalculator
from src.storage.sqlite_repository import get_repository

TEST_QUERIES = [
    "o que é estágio probatório?",
    "quais os requisitos para ser presidente da república?",
    "como funciona a licença maternidade?",
    "quais são os princípios da administração pública?",
    "o que é habeas corpus?",
]

log = structlog.get_logger(__name__)


async def check_quality() -> None:
    log.info("rag_quality_check_started")

    # Setup
    repository = get_repository()
    await repository.initialize_database()

    # We need the async session for QueryService
    # In botsalinha, repository.async_session_maker() is an async context manager
    async with repository.async_session_maker() as session:
        query_service = QueryService(
            session=session,
            embedding_service=EmbeddingService(),
            vector_store=VectorStore(session),
            confianca_calculator=ConfiancaCalculator(),
        )

        results = []
        for query in TEST_QUERIES:
            print(f"Testando query: '{query}'")
            start_time = time.perf_counter()
            try:
                context = await query_service.query(query, top_k=3)
                duration = time.perf_counter() - start_time

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
                        "duration_ms": round(duration * 1000, 2),
                    }
                )
            except Exception as e:
                print(f"Erro na query '{query}': {e}")
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

        # Save results to CSV
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

        print(f"Métricas de qualidade salvas em {output_file}")


if __name__ == "__main__":
    asyncio.run(check_quality())
