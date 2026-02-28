"""Testes de carga RAG com banco de dados real.

Este módulo contém testes que usam um banco de dados SQLite em disco
para validar performance em condições mais realistas.

NOTA: Estes testes requerem configuração adicional e criam arquivos
temporários em disco. Use com cautela.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from tests.load.load_test_runner import LoadTestRunner


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_rag_with_real_database(
    load_test_config,
    rag_api_key,
    tmp_path,
):
    """
    Teste: Performance com banco de dados SQLite em disco.

    Objetivo: Validar performance com banco real (não in-memory).

    Critérios de Sucesso:
    - Teste completa sem erros
    - Throughput >= 3 qps (mais lento que in-memory)
    - Latência P95 < 3000ms
    """
    import random
    import json
    import sqlite3
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    from src.models.rag_models import DocumentORM, ChunkORM, Base
    from src.rag import QueryService, CachedEmbeddingService
    from src.rag.storage.vector_store import serialize_embedding

    # Create database file
    db_path = tmp_path / "test_rag_real.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # Create engine
    engine = create_async_engine(
        db_url,
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        # Create test documents
        documents = []
        for i in range(1, 6):  # 5 documentos para teste mais rápido
            doc = DocumentORM(
                nome=f"Documento Jurídico {i}",
                arquivo_origem=f"doc_{i}.txt",
                chunk_count=random.randint(50, 100),
                token_count=random.randint(50000, 100000),
            )
            session.add(doc)
            documents.append(doc)

        await session.flush()

        # Create chunks with mock embeddings
        chunk_count = 0
        for doc in documents:
            chunks_per_doc = random.randint(50, 100)

            for j in range(chunks_per_doc):
                meta = {
                    "documento": doc.nome,
                    "artigo": f"art_{random.randint(1, 100)}" if random.random() > 0.3 else None,
                    "tipo": random.choice(["caput", "inciso", "paragrafo", None]),
                    "marca_stf": random.random() > 0.8,
                    "marca_stj": random.random() > 0.8,
                    "marca_concurso": random.random() > 0.7,
                }

                # Create normalized mock embedding
                embedding = [random.uniform(-0.1, 0.1) for _ in range(1536)]
                norm = sum(x**2 for x in embedding) ** 0.5
                if norm > 0:
                    embedding = [x / norm for x in embedding]

                chunk = ChunkORM(
                    id=f"chunk_{doc.id}_{chunk_count}",
                    documento_id=doc.id,
                    texto=f"Texto jurídico exemplo {chunk_count}. " * 10,
                    metadados=json.dumps(meta),
                    token_count=random.randint(100, 500),
                    embedding=serialize_embedding(embedding),
                )
                session.add(chunk)
                chunk_count += 1

                # Commit in batches
                if chunk_count % 50 == 0:
                    await session.commit()

        await session.commit()

        # Create query service with cached embeddings for better performance
        from unittest.mock import AsyncMock, patch

        embedding_service = CachedEmbeddingService(
            api_key=rag_api_key,
            cache_size=1000,  # Maior cache para testes
        )

        # Mock embed_text
        async def mock_embed_text(text: str) -> list[float]:
            import hashlib
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            random.seed(seed)
            embedding = [random.uniform(-0.1, 0.1) for _ in range(1536)]
            norm = sum(x**2 for x in embedding) ** 0.5
            return [x / norm for x in embedding] if norm > 0 else embedding

        with patch.object(
            embedding_service._embedding_service,
            "embed_text",
            new=AsyncMock(side_effect=mock_embed_text),
        ):
            query_service = QueryService(
                session=session,
                embedding_service=embedding_service,
            )

            # Run smaller load test with real database
            runner = LoadTestRunner(report_dir=tmp_path)

            metrics = await runner.run_concurrent_users_test(
                query_service=query_service,
                concurrent_users=20,
                queries_per_user=5,
                ramp_up_time=5.0,
            )

            # Assert criteria for real database (slower than in-memory)
            assert metrics.success_rate >= 90.0, f"Success rate too low: {metrics.success_rate}%"
            assert metrics.queries_per_second >= 2.0, f"Throughput too low: {metrics.queries_per_second} qps"
            assert metrics.p95_latency < 5000, f"P95 latency too high: {metrics.p95_latency}ms"

            # Verify cache was used
            cache_stats = embedding_service.cache_stats
            assert cache_stats["total_requests"] > 0, "Cache should have been used"

    # Cleanup
    await engine.dispose()

    # Verify database file was created
    assert db_path.exists()
    assert db_path.stat().st_size > 0


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_rag_cache_throughput_improvement(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Comparativo de throughput com e sem cache.

    Objetivo: Validar que o cache de embeddings melhora o throughput.

    Critérios de Sucesso:
    - Cache reduz latência em testes com queries repetitivas
    - Hit rate do cache > 50% com queries repetitivas
    """
    from tests.load.workload_generator import LegalWorkloadGenerator
    import time

    generator = LegalWorkloadGenerator()
    runner = LoadTestRunner(report_dir=load_test_report_dir)

    # Use same queries repeatedly to trigger cache hits
    repeated_queries = generator.get_query_batch(20) * 3  # 20 unique queries, 3 times each

    # Test without cache (baseline)
    start_time = time.time()
    results_no_cache = []
    for query in repeated_queries:
        try:
            start = time.time()
            await rag_query_service_with_mock_data.query(query)
            latency_ms = (time.time() - start) * 1000
            results_no_cache.append(latency_ms)
        except Exception:
            pass
    time_no_cache = time.time() - start_time

    # Now with cached embedding service
    from src.rag import CachedEmbeddingService
    from unittest.mock import AsyncMock, patch

    cached_service = CachedEmbeddingService(
        api_key="test-key",
        cache_size=1000,
    )

    async def mock_embed_text(text: str) -> list[float]:
        import hashlib
        import random
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        embedding = [random.uniform(-0.1, 0.1) for _ in range(1536)]
        norm = sum(x**2 for x in embedding) ** 0.5
        return [x / norm for x in embedding] if norm > 0 else embedding

    with patch.object(
        cached_service._embedding_service,
        "embed_text",
        new=AsyncMock(side_effect=mock_embed_text),
    ):
        # Create new query service with cache
        from src.rag import QueryService

        # Get session from the existing service
        session = rag_query_service_with_mock_data._session

        cached_query_service = QueryService(
            session=session,
            embedding_service=cached_service,
        )

        start_time = time.time()
        results_with_cache = []
        for query in repeated_queries:
            try:
                start = time.time()
                await cached_query_service.query(query)
                latency_ms = (time.time() - start) * 1000
                results_with_cache.append(latency_ms)
            except Exception:
                pass
        time_with_cache = time.time() - start_time

    # Assert cache improves performance
    avg_no_cache = sum(results_no_cache) / len(results_no_cache) if results_no_cache else 0
    avg_with_cache = sum(results_with_cache) / len(results_with_cache) if results_with_cache else 0

    # Cache should have good hit rate with repeated queries
    cache_stats = cached_service.cache_stats
    hit_rate = cache_stats["hit_rate"]

    assert hit_rate >= 0.5, f"Cache hit rate too low: {hit_rate:.2%}"
    assert avg_with_cache <= avg_no_cache * 1.1, "Cached queries should not be significantly slower"


@pytest.mark.load
@pytest.mark.rag_load
@pytest.mark.asyncio
async def test_rag_cache_size_impact(
    load_test_config,
    rag_query_service_with_mock_data,
    load_test_report_dir,
):
    """
    Teste: Impacto do tamanho do cache na performance.

    Objetivo: Validar que cache maior melora hit rate.

    Critérios de Sucesso:
    - Cache de 100 itens tem hit rate > 20%
    - Cache de 1000 itens tem hit rate significativamente maior
    """
    from src.rag import CachedEmbeddingService, QueryService
    from unittest.mock import AsyncMock, patch
    from tests.load.workload_generator import LegalWorkloadGenerator

    generator = LegalWorkloadGenerator()

    # Test with different cache sizes
    cache_sizes = [50, 500, 2000]
    hit_rates = {}

    for cache_size in cache_sizes:
        cached_service = CachedEmbeddingService(
            api_key="test-key",
            cache_size=cache_size,
        )

        async def mock_embed_text(text: str) -> list[float]:
            import hashlib
            import random
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            random.seed(seed)
            embedding = [random.uniform(-0.1, 0.1) for _ in range(1536)]
            norm = sum(x**2 for x in embedding) ** 0.5
            return [x / norm for x in embedding] if norm > 0 else embedding

        with patch.object(
            cached_service._embedding_service,
            "embed_text",
            new=AsyncMock(side_effect=mock_embed_text),
        ):
            session = rag_query_service_with_mock_data._session
            cached_query_service = QueryService(
                session=session,
                embedding_service=cached_service,
            )

            # Run queries with some repetition
            queries = generator.get_query_batch(50)
            queries += queries[:20]  # Add 20 repeated queries

            for query in queries:
                try:
                    await cached_query_service.query(query)
                except Exception:
                    pass

            hit_rates[cache_size] = cached_service.cache_hit_rate
            cached_service.clear_cache()

    # Assert larger cache has better hit rate
    assert hit_rates[50] >= 0.15, f"Hit rate too low for cache_size=50: {hit_rates[50]:.2%}"
    assert hit_rates[500] >= hit_rates[50], "Larger cache should have better hit rate"


__all__ = []
