"""E2E tests for RAG search functionality."""

from __future__ import annotations

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.rag import QueryService, VectorStore, ConfiancaCalculator
from src.rag.services.embedding_service import EmbeddingService
from src.models.rag_models import ChunkORM, DocumentORM
from src.rag.models import Chunk, ChunkMetadata


@pytest.mark.e2e
@pytest.mark.rag
@pytest.mark.database
class TestRAGSearchE2E:
    """End-to-end tests for RAG search."""

    @pytest.mark.asyncio
    async def test_simple_search_returns_results(
        self,
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test that a simple search returns relevant chunks."""
        # Check if documents are indexed
        from sqlalchemy import select, func

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        # Initialize service

        # Perform search
        context = await rag_query_service.query(
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
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test search with document filter."""
        from sqlalchemy import select, func

        # Get a document ID
        doc_stmt = select(DocumentORM).limit(1)
        doc_result = await db_session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            pytest.skip("No indexed documents found")


        # Search with document filter
        context = await rag_query_service.query(
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
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test search with query that should return no results."""

        # Query about unrelated topic
        context = await rag_query_service.query(
            query_text="fórmula química da água",
            top_k=5,
        )

        # Should have SEM_RAG confidence or very low confidence
        assert context.confianca.value in ["sem_rag", "baixa"]

    @pytest.mark.asyncio
    async def test_search_latency(
        self,
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test that search completes within acceptable latency."""
        from sqlalchemy import select, func

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await db_session.execute(chunk_count_stmt)
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
            context = await rag_query_service.query(query_text=query, top_k=5)
            latency = time.time() - start_time
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Assert average latency < 500ms
        assert avg_latency < 0.5, f"Average latency {avg_latency*1000:.1f}ms exceeds 500ms"

    @pytest.mark.asyncio
    async def test_response_structure(
        self,
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test that RAG context has proper structure."""
        from sqlalchemy import select, func

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        context = await rag_query_service.query(
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
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test confidence calculation for different queries."""
        from sqlalchemy import select, func

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")

        calculator = ConfiancaCalculator()

        # High confidence query (specific legal term)
        high_context = await rag_query_service.query(
            query_text="artigo 5 constituição federal direitos",
            top_k=5,
        )
        high_confidence = calculator.calculate_from_context(high_context)

        # Low confidence query (unrelated topic)
        low_context = await rag_query_service.query(
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
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test VectorStore direct retrieval."""
        from sqlalchemy import select, func

        # Get a chunk with embedding
        chunk_stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None)).limit(1)
        chunk_result = await db_session.execute(chunk_stmt)
        chunk_orm = chunk_result.scalar_one_or_none()

        if not chunk_orm:
            pytest.skip("No chunks with embeddings found")

        vector_store = VectorStore(session=db_session)

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
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test QueryService query_by_tipo method."""
        from sqlalchemy import select, func

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        # Query by "artigo" type
        context = await rag_query_service.query_by_tipo(
            query_text="servidor",
            tipo="artigo",
            top_k=3,
        )

        # Should return results
        assert isinstance(context, type(await rag_query_service.query("servidor", top_k=3)))

    @pytest.mark.asyncio
    async def test_prompt_augmentation(
        self,
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test prompt augmentation with RAG context."""
        from sqlalchemy import select, func

        chunk_count_stmt = select(func.count(ChunkORM.id))
        chunk_result = await db_session.execute(chunk_count_stmt)
        chunk_count = chunk_result.scalar() or 0

        if chunk_count == 0:
            pytest.skip("No indexed chunks found")


        context = await rag_query_service.query(
            query_text="direitos fundamentais",
            top_k=2,
        )

        # Check if should augment
        should_augment = rag_query_service.should_augment_prompt(context)

        if context.chunks_usados:
            assert should_augment == (context.confianca.value != "sem_rag")

        # Get augmentation text
        aug_text = rag_query_service.get_augmentation_text(context)

        # Should contain context if chunks found
        if context.chunks_usados:
            assert len(aug_text) > 0
            assert "CONTEXTO JURÍDICO" in aug_text or "SEM RAG" in aug_text
