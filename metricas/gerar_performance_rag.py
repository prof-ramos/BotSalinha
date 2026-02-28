"""
Script for generating RAG Component Performance Metrics.
Measures latency for embedding generation and vector search.
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
    fieldnames = ["text_snippet", "char_length", "embedding_time_ms", "search_time_ms", "chunks_found"]
    save_results_csv(output_path, results, fieldnames)

    # Calculate and print statistical summary
    if results:
        embedding_times = [r["embedding_time_ms"] for r in results]
        search_times = [r["search_time_ms"] for r in results]
        char_lengths = [r["char_length"] for r in results]

        avg_embedding = statistics.mean(embedding_times)
        avg_search = statistics.mean(search_times)
        avg_length = statistics.mean(char_lengths)

        correlation = 0.0
        if len(results) >= 2:
            n = len(results)
            sum_x = sum(char_lengths)
            sum_y = sum(embedding_times)
            sum_xy = sum(x * y for x, y in zip(char_lengths, embedding_times, strict=False))
            sum_x2 = sum(x ** 2 for x in char_lengths)
            sum_y2 = sum(y ** 2 for y in embedding_times)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5
            correlation = numerator / denominator if denominator != 0 else 0.0

        metrics = [
            ("Tempo médio de embedding:", f"{avg_embedding:.2f}ms"),
            ("Tempo médio de busca:", f"{avg_search:.2f}ms"),
            ("Tamanho médio do texto:", f"{avg_length:.0f} caracteres"),
            (None, None), # Spacer
            ("Correlação Tamanho → Tempo:", f"{correlation:.3f}"),
            ("Total de textos testados:", len(results)),
        ]
        print_summary_box("PERFORMANCE RAG COMPONENTES", metrics)

        summary_data = [
            {"metric": "avg_embedding_time_ms", "value": f"{avg_embedding:.2f}"},
            {"metric": "avg_search_time_ms", "value": f"{avg_search:.2f}"},
            {"metric": "avg_text_length_chars", "value": f"{avg_length:.0f}"},
            {"metric": "length_time_correlation", "value": f"{correlation:.3f}"},
            {"metric": "total_texts_tested", "value": len(results)},
        ]
        save_summary_csv(output_path, summary_data)

if __name__ == "__main__":
    parser = get_base_parser("Generate RAG component performance metrics")
    parser.add_argument("-t", "--texts", type=int, default=None, help="Number of texts to test")
    args = parser.parse_args()
    
    output_file = args.output or "metricas/performance_rag_componentes.csv"
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(check_rag_performance(output_file=output_file, num_texts=args.texts))
