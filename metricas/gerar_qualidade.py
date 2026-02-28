"""
Script for generating RAG Quality Metrics.
Evaluates semantic similarity and confidence distribution for test queries.
"""

import asyncio
import statistics
import time
from pathlib import Path

import structlog

from metricas.utils import (
    configure_logging,
    get_base_parser,
    print_summary_box,
    save_results_csv,
    save_summary_csv,
)
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
    fieldnames = ["query", "confidence", "avg_similarity", "max_similarity", "chunks_retrieved", "duration_ms"]
    save_results_csv(output_path, results, fieldnames)

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

        metrics = [
            ("Distribuição de Confiança:", None),
        ]
        for conf_level in ["ALTA", "MEDIA", "BAIXA", "SEM_RAG", "erro"]:
            if conf_level in confidence_dist:
                metrics.append((f"  {conf_level}:", f"{confidence_dist[conf_level]:.1f}%"))
        
        metrics.extend([
            (None, None), # Spacer
            ("Similaridade Média Agregada:", f"{mean_similarity:.4f}"),
            ("Chunks Recuperados (Média):", f"{mean_chunks:.1f}"),
            ("Total de Queries:", total_queries),
        ])
        print_summary_box("QUALIDADE RAG", metrics)

        # Save summary
        summary_data = []
        for conf_level, percentage in confidence_dist.items():
            summary_data.append({"metric": f"confidence_{conf_level}_percent", "value": f"{percentage:.1f}"})
        summary_data.extend([
            {"metric": "avg_similarity_aggregated", "value": f"{mean_similarity:.4f}"},
            {"metric": "avg_chunks_retrieved", "value": f"{mean_chunks:.1f}"},
            {"metric": "total_queries", "value": total_queries},
        ])
        save_summary_csv(output_path, summary_data)

if __name__ == "__main__":
    parser = get_base_parser("Generate RAG quality metrics")
    parser.add_argument("-q", "--queries", type=int, default=None, help="Number of queries to test")
    args = parser.parse_args()
    
    output_file = args.output or "metricas/qualidade_rag.csv"
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_quality(output_file=output_file, num_queries=args.queries))
