#!/usr/bin/env python3
"""
Warm the semantic cache with common legal queries.

This script pre-loads the semantic cache with frequently asked questions
about Brazilian law to improve cache hit rates and reduce latency.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import get_settings
from src.rag.models import RAGContext
from src.rag.services.query_service import QueryService
from src.storage.factory import create_repository
from src.utils.logger import setup_logging
import structlog

# Common legal queries for cache warming
COMMON_LEGAL_QUERIES = [
    # Constitutional Law
    "Quais são os direitos fundamentais previstos na Constituição Federal?",
    "O que é habeas corpus?",
    "Quais são os poderes da União?",
    "O que diz o artigo 5º da Constituição?",
    "Quais são as cláusulas pétreas?",

    # Civil Law
    "O que é código civil?",
    "Quais são os tipos de contratos?",
    "O que é prescrição civil?",
    "Quais são os direitos do consumidor?",
    "O que é responsabilidade civil?",

    # Criminal Law
    "O que é crime doloso?",
    "Quais são as penas previstas no código penal?",
    "O que é princípio da inocência?",
    "Quais são os tipos de crimes contra o patrimônio?",
    "O que é furto qualificado?",

    # Administrative Law
    "O que é ato administrativo?",
    "Quais são os princípios da administração pública?",
    "O que é licitação?",
    "Quais são os tipos de contratos administrativos?",
    "O que é impeachment?",

    # Labor Law
    "Quais são os direitos do trabalhador?",
    "O que é CLT?",
    "Quais são as horas extras?",
    "O que é FGTS?",
    "Quais são os tipos de rescisão contratual?",

    # Tax Law
    "O que é tributo?",
    "Quais são os tipos de impostos?",
    "O que é ICMS?",
    "Quais são as taxas?",
    "O que é contribuição de melhoria?",

    # Process Law
    "O que é due process legal?",
    "Quais são os recursos processuais?",
    "O que é jurisdição?",
    "Quais são as partes no processo?",
    "O que é coisa julgada?",

    # General/Study Questions
    "Como estudar direito constitucional para concursos?",
    "Quais são os principais temas de direito civil para provas?",
    "O que cai mais em direito penal?",
    "Como estudar direito administrativo?",
    "Dicas para prova de direito trabalhista?",
]


async def warm_cache(
    query_service: QueryService,
    queries: list[str],
    batch_size: int = 10,
) -> dict[str, int]:
    """
    Warm the semantic cache with common queries.

    Args:
        query_service: QueryService instance
        queries: List of queries to warm the cache with
        batch_size: Number of concurrent queries

    Returns:
        Dictionary with success/failure counts
    """
    log = structlog.get_logger(__name__)
    results = {"success": 0, "failed": 0, "total": len(queries)}

    log.info(
        "cache_warming_start",
        total_queries=len(queries),
        batch_size=batch_size,
    )

    # Process queries in batches to avoid overwhelming the system
    for i in range(0, len(queries), batch_size):
        batch = queries[i : i + batch_size]

        tasks = [query_service.query(query_text=q) for q in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for query, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                log.warning(
                    "cache_warming_query_failed",
                    query=query[:50],
                    error=str(result),
                )
                results["failed"] += 1
            elif isinstance(result, RAGContext):
                log.debug(
                    "cache_warming_query_success",
                    query=query[:50],
                    chunks=len(result.chunks_usados),
                    confidence=result.confianca.value,
                )
                results["success"] += 1

        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(queries):
            await asyncio.sleep(0.1)

    log.info(
        "cache_warming_complete",
        success=results["success"],
        failed=results["failed"],
        total=results["total"],
        success_rate=results["success"] / results["total"] * 100,
    )

    return results


async def main() -> None:
    """Main entry point for cache warming."""
    setup_logging()
    log = structlog.get_logger(__name__)

    settings = get_settings()

    log.info(
        "cache_warming_init",
        db_url=str(settings.database.url),
        rag_top_k=settings.rag.top_k,
        rag_min_similarity=settings.rag.min_similarity,
    )

    try:
        async with create_repository() as repository:
            session = repository.get_session()

            try:
                # Initialize QueryService with semantic cache
                query_service = QueryService(session=session)

                # Warm cache with common queries
                results = await warm_cache(
                    query_service=query_service,
                    queries=COMMON_LEGAL_QUERIES,
                    batch_size=10,
                )

                # Get cache statistics
                cache_stats = query_service.get_cache_stats()

                log.info(
                    "cache_warming_final_stats",
                    cache_hit_rate=cache_stats["cache_hit_rate"],
                    cache_memory_mb=cache_stats["cache_memory_mb"],
                    cache_entry_count=cache_stats["cache_entry_count"],
                    **results,
                )

                print(f"\n✅ Cache warming complete!")
                print(f"   Success: {results['success']}/{results['total']}")
                print(f"   Failed: {results['failed']}/{results['total']}")
                print(f"   Cache entries: {cache_stats['cache_entry_count']}")
                print(f"   Cache memory: {cache_stats['cache_memory_mb']:.2f} MB")

            finally:
                await session.close()

    except Exception as e:
        log.error("cache_warming_error", error=str(e))
        print(f"\n❌ Cache warming failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
