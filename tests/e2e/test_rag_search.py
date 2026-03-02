"""E2E tests for RAG search functionality."""

from __future__ import annotations

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from metricas.baseline_retrieval import RetrievalBenchmarkCase
from metricas.integrated_evaluation import (
    IntegratedSLOs,
    compare_baseline_candidate,
    evaluate_integrated_case,
)
from src.models.rag_models import ChunkORM, DocumentORM
from src.rag import ConfiancaCalculator, QueryService, VectorStore
from src.rag.models import Chunk, ChunkMetadata


class _FakeEmbeddingService:
    async def embed_text(self, _text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


@pytest.fixture
def rag_query_service(db_session: AsyncSession) -> QueryService:
    """Fixture local para consultas e2e sem dependência de API externa."""
    return QueryService(
        session=db_session,
        embedding_service=_FakeEmbeddingService(),
    )


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
        rag_query_service: QueryService,
        db_session: AsyncSession,
    ) -> None:
        """Test that a simple search returns relevant chunks."""
        # Check if documents are indexed
        from sqlalchemy import func, select

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
        from sqlalchemy import select

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
        from sqlalchemy import func, select

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
            await rag_query_service.query(query_text=query, top_k=5)
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
        from sqlalchemy import func, select

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
        from sqlalchemy import func, select

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
        from sqlalchemy import select

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
        from sqlalchemy import func, select

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
        from sqlalchemy import func, select

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

    def test_integrated_baseline_candidate_with_slos(self) -> None:
        """Valida avaliação integrada baseline/candidato com SLOs operacionais."""
        case = RetrievalBenchmarkCase(
            case_id="integrated_e2e_1",
            tipo="artigo",
            query="O que diz o Art. 5 da CF/88?",
            expected_doc="CF/88",
            expected_artigo="5",
            expected_keywords=("direitos",),
        )

        retrieved = [
            self._make_chunk(doc="CF/88", artigo="5", texto="Art. 5 direitos e garantias fundamentais."),
        ]

        baseline = evaluate_integrated_case(
            case=case,
            retrieved_chunks=retrieved,
            response_text="Não tenho base suficiente para responder com segurança.",
            latency_s=0.62,
            variant="baseline",
            context_tokens=180,
        )
        candidate = evaluate_integrated_case(
            case=case,
            retrieved_chunks=retrieved,
            response_text=(
                "Com base na CF/88, Art. 5, os direitos fundamentais protegem "
                "liberdade e igualdade. Fonte: CF/88, Art. 5."
            ),
            latency_s=0.34,
            variant="candidate",
            context_tokens=180,
        )

        slos = IntegratedSLOs(
            min_recall_at_5=0.8,
            min_response_citation_correct_rate=0.7,
            min_normative_coverage=0.5,
            max_p95_latency_s=0.8,
            max_cost_per_query_usd=0.01,
            max_timeout_rate=0.05,
            max_error_rate=0.05,
        )

        comparison = compare_baseline_candidate(
            baseline_results=[baseline],
            candidate_results=[candidate],
            slos=slos,
        )

        assert comparison["candidate_beats_baseline"] is True
        assert comparison["slos"]["all_pass"] is True
        assert comparison["deltas"]["response_citation_correct_rate"] > 0.0
        assert comparison["deltas"]["sem_base_rate"] < 0.0
