#!/usr/bin/env python3
"""Teste de latência do cache semântico RAG.

Demonstra a diferença de latência entre:
1. Primeira query (sem cache) - faz embedding + vector search + LLM
2. Segunda query (com cache) - retorna resposta cacheada

Execução:
    uv run python scripts/test_semantic_cache_latency.py
"""

import asyncio
import time
from pathlib import Path

from src.config.settings import get_settings
from src.config.yaml_config import yaml_config
from src.rag import QueryService, RAGContext, SemanticCache
from src.rag.services.embedding_service import EmbeddingService
from src.storage.factory import create_repository
from src.core.agent import AgentWrapper


async def test_cache_latency():
    """Testa latência com e sem cache semântico."""

    print("=" * 60)
    print("Teste de Latência - Cache Semântico RAG")
    print("=" * 60)

    # Setup
    settings = get_settings()
    print(f"\n📊 Configuração:")
    print(f"  - Top-K: {settings.rag.top_k}")
    print(f"  - Min Similarity: {settings.rag.min_similarity}")
    print(f"  - Retrieval Mode: {settings.rag.effective_retrieval_mode}")
    print(f"  - Chunking Mode: {settings.rag.effective_chunking_mode}")
    print(f"  - Cache Enabled: {settings.rag.cache.enabled}")

    # Query de teste (jurídica brasileira)
    test_query = "Quais são os direitos fundamentais previstos na Constituição Federal?"

    print(f"\n🔍 Query de teste:")
    print(f'  "{test_query}"')
    print()

    # Criar cache e repository
    cache = SemanticCache(
        max_memory_mb=settings.rag.cache.max_memory_mb,
        default_ttl_seconds=settings.rag.cache.ttl_seconds,
    )

    # Criar AgentWrapper com cache E db_session
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    database_url = settings.database.url
    if database_url.startswith("sqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as db_session:
        async with create_repository() as repository:
            agent = AgentWrapper(
                repository=repository,
                db_session=db_session,  # Obrigatório para RAG funcionar
                enable_rag=True,
                semantic_cache=cache,
            )

        print("=" * 60)
        print("🚀 PRIMEIRA EXECUÇÃO (sem cache)")
        print("=" * 60)

        # PRIMEIRA EXECUÇÃO (sem cache)
        start = time.perf_counter()
        response1, rag_context1 = await agent.generate_response_with_rag(
            prompt=test_query,
            conversation_id="test_cache_session",
            user_id="test_user",
        )
        first_duration = (time.perf_counter() - start) * 1000

        print(f"\n✅ Resposta 1 obtida em {first_duration:.0f}ms")
        print(f"  - RAG Confidence: {rag_context1.confianca.value if rag_context1 else 'N/A'}")
        print(f"  - Chunks usados: {len(rag_context1.chunks_usados) if rag_context1 else 0}")
        print(f"  - Resposta ({len(response1)} chars): {response1[:100]}...")

        # Obter telemetria do RAG
        if rag_context1 and rag_context1.retrieval_meta:
            print(f"\n⏱️ Breakdown RAG:")
            print(f"  - Embedding: {rag_context1.retrieval_meta.get('embedding_duration_ms', 0):.0f}ms")
            print(f"  - Vector Search: {rag_context1.retrieval_meta.get('vector_search_duration_ms', 0):.0f}ms")
            print(f"  - Rerank: {rag_context1.retrieval_meta.get('rerank_duration_ms', 0):.0f}ms")
            print(f"  - Total RAG: {rag_context1.retrieval_meta.get('total_query_duration_ms', 0):.0f}ms")

        print("\n" + "=" * 60)
        print("💾 SEGUNDA EXECUÇÃO (com cache)")
        print("=" * 60)

        # SEGUNDA EXECUÇÃO (deve usar cache)
        start = time.perf_counter()
        response2, rag_context2 = await agent.generate_response_with_rag(
            prompt=test_query,
            conversation_id="test_cache_session_2",
            user_id="test_user",
        )
        second_duration = (time.perf_counter() - start) * 1000

        print(f"\n✅ Resposta 2 obtida em {second_duration:.0f}ms")
        print(f"  - RAG Confidence: {rag_context2.confianca.value if rag_context2 else 'N/A'}")
        print(f"  - Chunks usados: {len(rag_context2.chunks_usados) if rag_context2 else 0}")
        print(f"  - Resposta ({len(response2)} chars): {response2[:100]}...")

        # Verificar estatísticas do cache
        stats = cache.get_stats()
        cache_hit_rate = stats.hit_rate if (stats.hits + stats.misses) > 0 else 0

        print("\n" + "=" * 60)
        print("📊 RESULTADOS")
        print("=" * 60)

        speedup = first_duration / second_duration if second_duration > 0 else 0
        time_saved = first_duration - second_duration

        print(f"\n⏱️ Latência:")
        print(f"  - Primeira execução (sem cache): {first_duration:.0f}ms")
        print(f"  - Segunda execução (com cache): {second_duration:.0f}ms")
        print(f"  - Tempo economizado: {time_saved:.0f}ms")
        print(f"  - Speedup: {speedup:.1f}x")

        print(f"\n💾 Cache Stats:")
        print(f"  - Hits: {stats.hits}")
        print(f"  - Misses: {stats.misses}")
        print(f"  - Hit Rate: {cache_hit_rate:.1%}")
        print(f"  - Memória usada: {stats.current_memory_mb:.1f}MB / {settings.rag.cache.max_memory_mb}MB")
        print(f"  - Entradas: {stats.entry_count}")

        print(f"\n✅ Sucesso!" if speedup > 2 else f"⚠️ Cache não efetivo (speedup: {speedup:.1f}x)")

        # SLO Check
        if second_duration <= 100:
            print(f"  🎯 SLO atingido: latência cache <= 100ms ✅")
        elif second_duration <= 500:
            print(f"  ⚠️ SLO marginal: latência cache <= 500ms (target: <=100ms)")
        else:
            print(f"  ❌ SLO violado: latência cache > 500ms (target: <=100ms)")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_cache_latency())
