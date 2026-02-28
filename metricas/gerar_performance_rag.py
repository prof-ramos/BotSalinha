"""
Script for generating RAG Component Performance Metrics.
Measures latency for embedding generation and vector search.
"""

import asyncio
import csv
import time
from pathlib import Path

import structlog

from src.rag.services.embedding_service import EmbeddingService
from src.rag.storage.vector_store import VectorStore
from src.storage.factory import create_repository

log = structlog.get_logger(__name__)

TEST_TEXTS = [
    "o que é estágio probatório?",
    "quais os requisitos para ser presidente da república?",
    "como funciona a licença maternidade?",
    "princípios da administração pública, impessoalidade e moralidade.",
    "uma frase curta.",
    "um texto muito mais longo para avaliar se o tempo de geração do embedding muda significativamente com o número de tokens na mesma chamada de api da openai, testando assim o impacto do tamanho no delay.",
]


async def check_rag_performance() -> None:
    """Benchmark RAG components and save results to CSV."""
    log.info("rag_component_performance_started", texts_count=len(TEST_TEXTS))

    embedding_service = EmbeddingService()
    results = []

    async with create_repository() as repo:
        async with repo.async_session_maker() as session:
            vector_store = VectorStore(session)

            for text in TEST_TEXTS:
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
    output_file = Path("metricas/performance_rag_componentes.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
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

    log.info("rag_component_performance_completed", output_file=str(output_file))


if __name__ == "__main__":
    asyncio.run(check_rag_performance())
