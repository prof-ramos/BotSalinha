"""
Script for generating RAG Component Performance Metrics.
Measures latency for embedding generation and vector search.
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
from src.rag.storage.vector_store import VectorStore
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

DEFAULT_TEXTS = [
    "o que é estágio probatório?",
    "quais os requisitos para ser presidente da república?",
    "como funciona a licença maternidade?",
    "princípios da administração pública, impessoalidade e moralidade.",
    "uma frase curta.",
    "um texto muito mais longo para avaliar se o tempo de geração do embedding muda significativamente com o número de tokens na mesma chamada de api da openai, testando assim o impacto do tamanho no delay.",
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


async def check_rag_performance(
    output_file: str = "metricas/performance_rag_componentes.csv",
    num_texts: int | None = None,
) -> None:
    """Benchmark RAG components and save results to CSV."""
    texts_to_test = DEFAULT_TEXTS[:num_texts] if num_texts else DEFAULT_TEXTS
    log.info("rag_component_performance_started", texts_count=len(texts_to_test))

    embedding_service = EmbeddingService()
    results = []

    async with create_repository() as repo, repo.async_session_maker() as session:
        vector_store = VectorStore(session)

        for text in texts_to_test:
            log.info("benchmarking_rag_components", text_snippet=text[:30])

            # 1. Measure Embedding API Latency
            start_emb = time.perf_counter()
            try:
                embedding = await embedding_service.embed_text(text)
                emb_duration = (time.perf_counter() - start_emb) * 1000
            except Exception as e:
                log.error("embedding_failed", error=str(e))
                continue

            # 2. Measure Vector Search Latency (Local)
            start_search = time.perf_counter()
            try:
                chunks = await vector_store.search(embedding, limit=5, min_similarity=0.3)
                search_duration = (time.perf_counter() - start_search) * 1000
            except Exception as e:
                log.error("vector_search_failed", error=str(e))
                search_duration = 0.0
                chunks = []

            results.append(
                {
                    "text_snippet": text[:50],
                    "char_length": len(text),
                    "embedding_time_ms": round(emb_duration, 2),
                    "search_time_ms": round(search_duration, 2),
                    "chunks_found": len(chunks),
                }
            )

    # Save results
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "text_snippet",
                "char_length",
                "embedding_time_ms",
                "search_time_ms",
                "chunks_found",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    # Calculate and print statistical summary
    if results:
        embedding_times = [r["embedding_time_ms"] for r in results]
        search_times = [r["search_time_ms"] for r in results]
        char_lengths = [r["char_length"] for r in results]

        avg_embedding = statistics.mean(embedding_times)
        avg_search = statistics.mean(search_times)
        avg_length = statistics.mean(char_lengths)

        # Calculate correlation between text length and embedding time
        if len(results) >= 2:
            # Simple correlation coefficient
            n = len(results)
            sum_x = sum(char_lengths)
            sum_y = sum(embedding_times)
            sum_xy = sum(x * y for x, y in zip(char_lengths, embedding_times, strict=False))
            sum_x2 = sum(x ** 2 for x in char_lengths)
            sum_y2 = sum(y ** 2 for y in embedding_times)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5
            correlation = numerator / denominator if denominator != 0 else 0.0
        else:
            correlation = 0.0

        print("\n" + "="*60)
        print("SUMÁRIO ESTATÍSTICO - PERFORMANCE RAG COMPONENTES")
        print("="*60)
        print(f"Tempo médio de embedding:      {avg_embedding:.2f}ms")
        print(f"Tempo médio de busca:          {avg_search:.2f}ms")
        print(f"Tamanho médio do texto:        {avg_length:.0f} caracteres")
        print(f"\nCorrelação Tamanho → Tempo:    {correlation:.3f}")
        if correlation > 0.5:
            print("  (Forte correlação positiva: textos maiores causam mais delay)")
        elif correlation < -0.5:
            print("  (Correlação negativa inesperada)")
        else:
            print("  (Baixa correlação: tamanho tem pouco impacto)")
        print(f"\nTotal de textos testados:       {len(results)}")
        print("="*60)

        # Also save summary to CSV
        summary_path = output_path.parent / f"{output_path.stem}_summary{output_path.suffix}"
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerow({"metric": "avg_embedding_time_ms", "value": f"{avg_embedding:.2f}"})
            writer.writerow({"metric": "avg_search_time_ms", "value": f"{avg_search:.2f}"})
            writer.writerow({"metric": "avg_text_length_chars", "value": f"{avg_length:.0f}"})
            writer.writerow({"metric": "length_time_correlation", "value": f"{correlation:.3f}"})
            writer.writerow({"metric": "total_texts_tested", "value": len(results)})

        log.info("rag_performance_summary_saved", summary_file=str(summary_path))

    log.info("rag_component_performance_completed", output_file=str(output_path))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate RAG component performance metrics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-o", "--output",
        default="metricas/performance_rag_componentes.csv",
        help="Path to the output CSV file",
    )
    parser.add_argument(
        "-t", "--texts",
        type=int,
        default=None,
        help="Number of texts to test (default: all available texts)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress info logs (only errors will be shown)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_rag_performance(output_file=args.output, num_texts=args.texts))
