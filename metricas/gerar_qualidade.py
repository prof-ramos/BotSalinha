"""
Script for generating RAG Quality Metrics.
Evaluates semantic similarity and confidence distribution for test queries.
"""

import argparse
import asyncio
import csv
import logging
import statistics
import sys
import time
from pathlib import Path

import structlog

from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.query_service import QueryService
from src.rag.storage.vector_store import VectorStore
from src.rag.utils.confianca_calculator import ConfiancaCalculator
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

DEFAULT_QUERIES = [
    "o que é estágio probatório?",
    "quais os requisitos para ser presidente da república?",
    "como funciona a licença maternidade?",
    "quais são os princípios da administração pública?",
    "o que é habeas corpus?",
    "qual o prazo para impetrar mandado de segurança?",
]


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging level based on verbosity flags."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


async def check_quality(
    output_file: str = "metricas/qualidade_rag.csv",
    num_queries: int | None = None,
) -> None:
    """Evaluate RAG search quality and save results to CSV."""
    queries_to_test = DEFAULT_QUERIES[:num_queries] if num_queries else DEFAULT_QUERIES
    log.info("rag_quality_check_started", queries_count=len(queries_to_test))

    results = []

    async with create_repository() as repo, repo.async_session_maker() as session:
        query_service = QueryService(
            session=session,
            embedding_service=EmbeddingService(),
            vector_store=VectorStore(session),
            confianca_calculator=ConfiancaCalculator(),
        )

        for query in queries_to_test:
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
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
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

    # Calculate and print statistical summary
    if results:
        # Confidence distribution
        confidence_counts = {}
        for r in results:
            conf = r["confidence"]
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        total_queries = len(results)
        confidence_dist = {k: (v / total_queries) * 100 for k, v in confidence_counts.items()}

        # Similarity statistics
        avg_similarities = [r["avg_similarity"] for r in results if r["avg_similarity"] > 0]
        mean_similarity = statistics.mean(avg_similarities) if avg_similarities else 0.0

        # Chunks statistics
        chunks_retrieved = [r["chunks_retrieved"] for r in results]
        mean_chunks = statistics.mean(chunks_retrieved) if chunks_retrieved else 0.0

        print("\n" + "=" * 60)
        print("SUMÁRIO ESTATÍSTICO - QUALIDADE RAG")
        print("=" * 60)
        print("Distribuição de Confiança:")
        for conf_level in ["ALTA", "MEDIA", "BAIXA", "SEM_RAG", "erro"]:
            if conf_level in confidence_dist:
                print(f"  {conf_level:12s}: {confidence_dist[conf_level]:5.1f}%")
        print(f"\nSimilaridade Média Agregada:   {mean_similarity:.4f}")
        print(f"Chunks Recuperados (Média):   {mean_chunks:.1f}")
        print(f"Total de Queries:              {total_queries}")
        print("=" * 60)

        # Also save summary to CSV
        summary_path = output_path.parent / f"{output_path.stem}_summary{output_path.suffix}"
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            for conf_level, percentage in confidence_dist.items():
                writer.writerow(
                    {"metric": f"confidence_{conf_level}_percent", "value": f"{percentage:.1f}"}
                )
            writer.writerow(
                {"metric": "avg_similarity_aggregated", "value": f"{mean_similarity:.4f}"}
            )
            writer.writerow({"metric": "avg_chunks_retrieved", "value": f"{mean_chunks:.1f}"})
            writer.writerow({"metric": "total_queries", "value": total_queries})

        log.info("quality_summary_saved", summary_file=str(summary_path))

    log.info("rag_quality_check_completed", output_file=str(output_path))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate RAG quality metrics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        default="metricas/qualidade_rag.csv",
        help="Path to the output CSV file",
    )
    parser.add_argument(
        "-q",
        "--queries",
        type=int,
        default=None,
        help="Number of queries to test (default: all available queries)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress info logs (only errors will be shown)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_quality(output_file=args.output, num_queries=args.queries))
