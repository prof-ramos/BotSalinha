"""E2E tests for RAG search functionality."""

from __future__ import annotations

import os
import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: metricas scripts não são mais módulos Python
# As classes de avaliação foram movidas para testes separados
# Este teste foi simplificado para validar apenas o RAG básico
from src.models.rag_models import ChunkORM, DocumentORM
from src.rag import ConfiancaCalculator, QueryService, VectorStore
from src.rag.models import Chunk, ChunkMetadata


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGSearchE2E:
    """End-to-end tests for RAG search."""

    @staticmethod
    def _make_chunk(*, doc: str, artigo: str, texto: str) -> Chunk:
        return Chunk(
            chunk_id=f"chunk-{doc}-{artigo}",
            documento_id=1,
            texto=texto,
            metadados=ChunkMetadata(documento=doc, artigo=artigo),
            token_count=120,
            posicao_documento=0.1,
        )

    @pytest.mark.asyncio
    async def test_simple_search_returns_results(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
        monkeypatch,
    ) -> None:
        """Test that a simple search returns relevant chunks."""
        # Disable ChromaDB timeout for E2E test to avoid transaction issues
        monkeypatch.setenv("BOTSALINHA_RAG__CHROMA__FALLBACK_TIMEOUT_MS", "5000")
        from src.config.settings import get_settings
        get_settings.cache_clear()

        # Check if documents are indexed
        from sqlalchemy import func, select

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        # Initialize service

        # Perform search
        context = await prod_rag_query_service.query(
            query_text="direitos fundamentais constituição",
            top_k=3,
        )

        # Assertions
        assert len(context.chunks_usados) <= 3
        assert len(context.similaridades) == len(context.chunks_usados)
        assert len(context.fontes) == len(context.chunks_usados)

        # Should have at least some result
        if chunk_count > 0:
            assert len(context.chunks_usados) > 0 or context.confianca.value == "sem_rag"

        # All similarities should be positive
        for score in context.similaridades:
            assert score >= 0.0, f"Negative similarity: {score}"

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test search with document filter."""
        from sqlalchemy import select

        # Get a document ID
        doc_stmt = select(DocumentORM).limit(1)
        doc_result = await prod_db_session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            pytest.skip("No indexed documents found")


        # Search with document filter
        context = await prod_rag_query_service.query(
            query_text="servidor",
            top_k=5,
            documento_id=document.id,
        )

        # All results should be from the specified document
        for chunk in context.chunks_usados:
            assert chunk.documento_id == document.id

    @pytest.mark.asyncio
    async def test_search_no_results(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test search with query that should return no results."""

        # Query about unrelated topic
        context = await prod_rag_query_service.query(
            query_text="fórmula química da água",
            top_k=5,
        )

        # Should have SEM_RAG confidence or very low confidence
        assert context.confianca.value in ["sem_rag", "baixa"]

    @pytest.mark.asyncio
    async def test_search_latency(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test that search completes within acceptable latency."""
        from sqlalchemy import func, select

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        # Measure latency
        queries = [
            "direitos fundamentais",
            "servidor público",
            "deveres do servidor",
        ]

        latencies: list[float] = []
        for query in queries:
            start_time = time.time()
            await prod_rag_query_service.query(query_text=query, top_k=5)
            latency = time.time() - start_time
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Network/API variance in E2E can be significant; keep threshold configurable.
        max_avg_latency_s = float(os.getenv("BOTSALINHA_TEST_MAX_AVG_LATENCY_S", "2.0"))
        assert avg_latency < max_avg_latency_s, (
            f"Average latency {avg_latency*1000:.1f}ms exceeds "
            f"{max_avg_latency_s*1000:.0f}ms threshold"
        )

    @pytest.mark.asyncio
    async def test_response_structure(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test that RAG context has proper structure."""
        from sqlalchemy import func, select

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        context = await prod_rag_query_service.query(
            query_text="constituição federal",
            top_k=3,
        )

        # Validate RAGContext structure
        assert hasattr(context, "chunks_usados")
        assert hasattr(context, "similaridades")
        assert hasattr(context, "confianca")
        assert hasattr(context, "fontes")

        # Validate types
        assert isinstance(context.chunks_usados, list)
        assert isinstance(context.similaridades, list)
        assert isinstance(context.fontes, list)

        # Validate Chunk structure
        for chunk in context.chunks_usados:
            assert isinstance(chunk, Chunk)
            assert hasattr(chunk, "chunk_id")
            assert hasattr(chunk, "texto")
            assert hasattr(chunk, "metadados")
            assert isinstance(chunk.metadados, ChunkMetadata)

    @pytest.mark.asyncio
    async def test_confidence_levels(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test confidence calculation for different queries."""
        from sqlalchemy import func, select

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        calculator = ConfiancaCalculator()

        # High confidence query (specific legal term)
        high_context = await prod_rag_query_service.query(
            query_text="artigo 5 constituição federal direitos",
            top_k=5,
        )
        high_confidence = calculator.calculate_from_context(high_context)

        # Low confidence query (unrelated topic)
        low_context = await prod_rag_query_service.query(
            query_text="receita de bolo de chocolate",
            top_k=5,
        )
        low_confidence = calculator.calculate_from_context(low_context)

        # High confidence should be >= low confidence
        high_value = {"alta": 1.0, "media": 0.7, "baixa": 0.4, "sem_rag": 0.0}[high_confidence.value]
        low_value = {"alta": 1.0, "media": 0.7, "baixa": 0.4, "sem_rag": 0.0}[low_confidence.value]

        assert high_value >= low_value

    @pytest.mark.asyncio
    async def test_vector_store_retrieval(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test VectorStore direct retrieval."""
        from sqlalchemy import select

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        vector_store = VectorStore(session=prod_db_session)

        # Retrieve by ID
        chunk = await vector_store.get_chunk_by_id(chunk_orm.id)

        assert chunk is not None
        assert chunk.chunk_id == chunk_orm.id
        assert chunk.texto == chunk_orm.texto

        # Count chunks
        count = await vector_store.count_chunks()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_query_by_tipo(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test QueryService query_by_tipo method."""
        from sqlalchemy import func, select

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        # Query by "artigo" type
        context = await prod_rag_query_service.query_by_tipo(
            query_text="servidor",
            tipo="artigo",
            top_k=3,
        )

        # Should return results
        assert isinstance(context, type(await prod_rag_query_service.query("servidor", top_k=3)))

    @pytest.mark.asyncio
    async def test_prompt_augmentation(
        self,
        prod_rag_query_service: QueryService,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test prompt augmentation with RAG context."""
        from sqlalchemy import func, select

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        context = await prod_rag_query_service.query(
            query_text="direitos fundamentais",
            top_k=2,
        )

        # Check if should augment
        should_augment = prod_rag_query_service.should_augment_prompt(context)

        if context.chunks_usados:
            assert should_augment == (context.confianca.value != "sem_rag")

        # Get augmentation text
        aug_text = prod_rag_query_service.get_augmentation_text(context)

        # Should contain context if chunks found
        if context.chunks_usados:
            assert len(aug_text) > 0
            assert "CONTEXTO JURÍDICO" in aug_text or "SEM RAG" in aug_text

    # NOTE: test_integrated_baseline_candidate_with_slos removido
    # As classes de avaliação (RetrievalBenchmarkCase, IntegratedSLOs)
    # foram movidas para scripts em metricas/ e não são mais importáveis
    # Este teste deve ser executado via metricas/run_all_metrics.py


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGVectorStoreBackends:
    """Test RAG search with different vector store backends (SQLite, ChromaDB, Hybrid)."""

    @pytest.mark.asyncio
    async def test_vector_store_retrieval_by_backend_sqlite(
        self,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test VectorStore direct retrieval with SQLite backend."""
        from sqlalchemy import select
        from src.rag import VectorStore

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        vector_store = VectorStore(session=prod_db_session)

        # Retrieve by ID
        chunk = await vector_store.get_chunk_by_id(chunk_orm.id)

        assert chunk is not None
        assert chunk.chunk_id == chunk_orm.id
        assert chunk.texto == chunk_orm.texto

        # Count chunks
        count = await vector_store.count_chunks()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_vector_store_retrieval_by_backend_chroma(
        self,
        prod_db_session: AsyncSession,
        chroma_vector_store_e2e,
    ) -> None:
        """Test VectorStore direct retrieval with ChromaDB backend."""
        from sqlalchemy import select

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        # Retrieve by ID
        chunk = await chroma_vector_store_e2e.get_chunk_by_id(chunk_orm.id)

        assert chunk is not None
        assert chunk.chunk_id == chunk_orm.id
        assert chunk.texto == chunk_orm.texto

        # Count chunks
        count = await chroma_vector_store_e2e.count_chunks()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_vector_store_retrieval_by_backend_hybrid(
        self,
        prod_db_session: AsyncSession,
        hybrid_vector_store_e2e,
    ) -> None:
        """Test VectorStore direct retrieval with Hybrid backend."""
        from sqlalchemy import select

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        # Retrieve by ID
        chunk = await hybrid_vector_store_e2e.get_chunk_by_id(chunk_orm.id)

        assert chunk is not None
        assert chunk.chunk_id == chunk_orm.id
        assert chunk.texto == chunk_orm.texto

        # Count chunks
        count = await hybrid_vector_store_e2e.count_chunks()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_vector_store_search_by_backend_sqlite(
        self,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test vector search with SQLite backend."""
        from sqlalchemy import func, select
        from src.rag import VectorStore

        # Check if we have chunks
        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        # Get a chunk with embedding for query
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        vector_store = VectorStore(session=prod_db_session)

        # Search using the chunk's embedding
        results = await vector_store.search(
            query_embedding=chunk_orm.embedding,
            query_text="direitos fundamentais",
            limit=5,
            min_similarity=0.6,
        )

        # Verify results
        assert isinstance(results, list)
        assert len(results) <= 5

        for chunk, score in results:
            assert isinstance(chunk, Chunk)
            assert isinstance(score, float)
            assert score >= 0.0
            assert hasattr(chunk, "chunk_id")
            assert hasattr(chunk, "texto")

    @pytest.mark.asyncio
    async def test_vector_store_search_by_backend_chroma(
        self,
        prod_db_session: AsyncSession,
        chroma_vector_store_e2e,
    ) -> None:
        """Test vector search with ChromaDB backend."""
        from sqlalchemy import func, select

        # Check if we have chunks
        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        # Get a chunk with embedding for query
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        # Search using the chunk's embedding
        results = await chroma_vector_store_e2e.search(
            query_embedding=chunk_orm.embedding,
            query_text="direitos fundamentais",
            limit=5,
            min_similarity=0.6,
        )

        # Verify results
        assert isinstance(results, list)
        assert len(results) <= 5

        for chunk, score in results:
            assert isinstance(chunk, Chunk)
            assert isinstance(score, float)
            assert score >= 0.0
            assert hasattr(chunk, "chunk_id")
            assert hasattr(chunk, "texto")

    @pytest.mark.asyncio
    async def test_vector_store_search_by_backend_hybrid(
        self,
        prod_db_session: AsyncSession,
        hybrid_vector_store_e2e,
    ) -> None:
        """Test vector search with Hybrid backend."""
        from sqlalchemy import func, select

        # Check if we have chunks
        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await prod_db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        # Get a chunk with embedding for query
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        # Search using the chunk's embedding
        results = await hybrid_vector_store_e2e.search(
            query_embedding=chunk_orm.embedding,
            query_text="direitos fundamentais",
            limit=5,
            min_similarity=0.6,
        )

        # Verify results
        assert isinstance(results, list)
        assert len(results) <= 5

        for chunk, score in results:
            assert isinstance(chunk, Chunk)
            assert isinstance(score, float)
            assert score >= 0.0
            assert hasattr(chunk, "chunk_id")
            assert hasattr(chunk, "texto")

    @pytest.mark.asyncio
    async def test_vector_store_filters_by_backend_sqlite(
        self,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test vector search with metadata filters using SQLite backend."""
        from sqlalchemy import select
        from src.rag import VectorStore

        # Get a document ID
        doc_stmt = select(DocumentORM).limit(1)
        doc_result = await prod_db_session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            pytest.skip("No indexed documents found")

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        vector_store = VectorStore(session=prod_db_session)

        # Search with document filter
        results = await vector_store.search(
            query_embedding=chunk_orm.embedding,
            query_text="servidor",
            limit=5,
            documento_id=document.id,
        )

        # All results should be from the specified document
        for chunk, score in results:
            assert chunk.documento_id == document.id

    @pytest.mark.asyncio
    async def test_vector_store_filters_by_backend_chroma(
        self,
        prod_db_session: AsyncSession,
        chroma_vector_store_e2e,
    ) -> None:
        """Test vector search with metadata filters using ChromaDB backend."""
        from sqlalchemy import select

        # Get a document ID
        doc_stmt = select(DocumentORM).limit(1)
        doc_result = await prod_db_session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            pytest.skip("No indexed documents found")

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        # Search with document filter
        results = await chroma_vector_store_e2e.search(
            query_embedding=chunk_orm.embedding,
            query_text="servidor",
            limit=5,
            documento_id=document.id,
        )

        # All results should be from the specified document
        for chunk, score in results:
            assert chunk.documento_id == document.id

    @pytest.mark.asyncio
    async def test_vector_store_filters_by_backend_hybrid(
        self,
        prod_db_session: AsyncSession,
        hybrid_vector_store_e2e,
    ) -> None:
        """Test vector search with metadata filters using Hybrid backend."""
        from sqlalchemy import select

        # Get a document ID
        doc_stmt = select(DocumentORM).limit(1)
        doc_result = await prod_db_session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            pytest.skip("No indexed documents found")

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await prod_db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        # Search with document filter
        results = await hybrid_vector_store_e2e.search(
            query_embedding=chunk_orm.embedding,
            query_text="servidor",
            limit=5,
            documento_id=document.id,
        )

        # All results should be from the specified document
        for chunk, score in results:
            assert chunk.documento_id == document.id

    @pytest.mark.asyncio
    async def test_vector_store_count_by_backend_sqlite(
        self,
        prod_db_session: AsyncSession,
    ) -> None:
        """Test chunk counting with SQLite backend."""
        from sqlalchemy import func, select
        from src.rag import VectorStore

        # Get expected count from SQLite
        count_stmt = select(func.count(ChunkORM.id))
        count_result = await prod_db_session.execute(count_stmt)
        expected_count = count_result.scalar() or 0

        if expected_count == 0:
            pytest.skip("No indexed chunks found")

        vector_store = VectorStore(session=prod_db_session)

        # Count chunks
        count = await vector_store.count_chunks()

        # ChromaDB and SQLite should have the same count
        # Hybrid uses SQLite as source of truth
        assert count >= 1
        assert count == expected_count

    @pytest.mark.asyncio
    async def test_vector_store_count_by_backend_chroma(
        self,
        prod_db_session: AsyncSession,
        chroma_vector_store_e2e,
    ) -> None:
        """Test chunk counting with ChromaDB backend."""
        from sqlalchemy import func, select

        # Get expected count from SQLite
        count_stmt = select(func.count(ChunkORM.id))
        count_result = await prod_db_session.execute(count_stmt)
        expected_count = count_result.scalar() or 0

        if expected_count == 0:
            pytest.skip("No indexed chunks found")

        # Count chunks
        count = await chroma_vector_store_e2e.count_chunks()

        # ChromaDB and SQLite should have the same count
        # Hybrid uses SQLite as source of truth
        assert count >= 1
        assert count == expected_count

    @pytest.mark.asyncio
    async def test_vector_store_count_by_backend_hybrid(
        self,
        prod_db_session: AsyncSession,
        hybrid_vector_store_e2e,
    ) -> None:
        """Test chunk counting with Hybrid backend."""
        from sqlalchemy import func, select

        # Get expected count from SQLite
        count_stmt = select(func.count(ChunkORM.id))
        count_result = await prod_db_session.execute(count_stmt)
        expected_count = count_result.scalar() or 0

        if expected_count == 0:
            pytest.skip("No indexed chunks found")

        # Count chunks
        count = await hybrid_vector_store_e2e.count_chunks()

        # ChromaDB and SQLite should have the same count
        # Hybrid uses SQLite as source of truth
        assert count >= 1
        assert count == expected_count
