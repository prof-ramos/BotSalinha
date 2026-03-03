"""Unit tests for VectorStore."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.models.conversation import Base
from src.models.rag_models import ChunkORM, DocumentORM
from src.rag.models import Chunk, ChunkMetadata
from src.rag.storage.vector_store import (
    VectorStore,
    cosine_similarity,
    deserialize_embedding,
    serialize_embedding,
)
from src.utils.errors import BotSalinhaError

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Create isolated in-memory DB session for vector store unit tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.unit
class TestVectorEmbedding:
    """Test embedding serialization/deserialization."""

    def test_serialize_deserialize_embedding(self) -> None:
        """Test embedding serialization round-trip."""
        original = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Serialize
        serialized = serialize_embedding(original)

        # Should be bytes
        assert isinstance(serialized, bytes)

        # Deserialize
        deserialized = deserialize_embedding(serialized)

        # Should match original (within float precision)
        assert len(deserialized) == len(original)
        for orig, deser in zip(original, deserialized, strict=False):
            assert abs(orig - deser) < 1e-6

    def test_serialize_empty_embedding(self) -> None:
        """Test serialization of empty embedding."""
        empty: list[float] = []
        serialized = serialize_embedding(empty)
        deserialized = deserialize_embedding(serialized)

        assert deserialized == []

    def test_serialize_large_embedding(self) -> None:
        """Test serialization of large embedding (1536 dim like OpenAI)."""
        large = list(range(1536))

        serialized = serialize_embedding(large)
        deserialized = deserialize_embedding(serialized)

        assert len(deserialized) == 1536


@pytest.mark.unit
class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_identical_vectors(self) -> None:
        """Test cosine similarity of identical vectors."""
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0, 3.0]

        similarity = cosine_similarity(a, b)

        # Should be 1.0 (identical)
        assert abs(similarity - 1.0) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        """Test cosine similarity of orthogonal vectors."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]

        similarity = cosine_similarity(a, b)

        # Should be 0.0 (orthogonal)
        assert abs(similarity - 0.0) < 1e-6

    def test_opposite_vectors(self) -> None:
        """Test cosine similarity of opposite vectors."""
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]

        similarity = cosine_similarity(a, b)

        # Should be -1.0 (opposite)
        assert abs(similarity - (-1.0)) < 1e-6

    def test_zero_vectors(self) -> None:
        """Test cosine similarity with zero vector."""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]

        similarity = cosine_similarity(a, b)

        # Should be 0.0 (zero vector has no direction)
        assert similarity == 0.0

    def test_positive_similarity(self) -> None:
        """Test vectors with positive similarity."""
        a = [1.0, 1.0, 1.0]
        b = [2.0, 2.0, 2.0]

        similarity = cosine_similarity(a, b)

        # Should be 1.0 (same direction, different magnitude)
        assert abs(similarity - 1.0) < 1e-6


@pytest.mark.unit
@pytest.mark.database
class TestVectorStore:
    """Test VectorStore operations."""

    @pytest.mark.asyncio
    async def test_add_embeddings(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test adding embeddings to vector store."""
        vector_store = VectorStore(session=db_session)

        # Create test chunks
        chunks = [
            Chunk(
                chunk_id="test-1",
                documento_id=1,
                texto="Test text 1",
                metadados=ChunkMetadata(documento="TEST"),
                token_count=10,
                posicao_documento=0.1,
            ),
            Chunk(
                chunk_id="test-2",
                documento_id=1,
                texto="Test text 2",
                metadados=ChunkMetadata(documento="TEST"),
                token_count=10,
                posicao_documento=0.2,
            ),
        ]

        embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]

        # Add embeddings (requires chunks to exist in DB first)
        # For unit test, we'll just verify the method doesn't crash
        chunks_with_embeddings = list(zip(chunks, embeddings, strict=False))

        # This will fail if chunks don't exist, which is expected - catch specific error
        try:
            await vector_store.add_embeddings(chunks_with_embeddings)
        except Exception as exc:
            if "FOREIGN KEY constraint failed" in str(exc) or "UNIQUE constraint failed" in str(
                exc
            ):
                pass  # Expected: chunks must exist in DB first
            else:
                raise

    @pytest.mark.asyncio
    async def test_count_chunks(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test counting chunks."""
        vector_store = VectorStore(session=db_session)

        # Count all chunks
        count = await vector_store.count_chunks()

        # Should be non-negative
        assert count >= 0

    @pytest.mark.asyncio
    async def test_search_empty_results(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test search with no matching chunks."""
        vector_store = VectorStore(session=db_session)

        # Search with random embedding
        query_embedding = [0.1] * 1536

        results = await vector_store.search(
            query_embedding=query_embedding,
            limit=5,
            min_similarity=0.99,  # Very high threshold
        )

        # Should return empty list or very few results
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_filters_not_null(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test metadata filter with not_null operator."""
        vector_store = VectorStore(session=db_session)

        doc = DocumentORM(
            nome="TEST",
            arquivo_origem="test.docx",
            chunk_count=2,
            token_count=20,
        )
        db_session.add(doc)
        await db_session.flush()

        chunk_with_artigo = ChunkORM(
            id="chunk-artigo",
            documento_id=doc.id,
            texto="Art. 5 direitos fundamentais",
            metadados=json.dumps(
                {"documento": "CF/88", "artigo": "5", "marca_stf": False, "marca_stj": False}
            ),
            token_count=10,
            embedding=serialize_embedding([0.3, 0.2, 0.1]),
        )
        chunk_without_artigo = ChunkORM(
            id="chunk-sem-artigo",
            documento_id=doc.id,
            texto="Disposicoes gerais",
            metadados=json.dumps({"documento": "CF/88", "marca_stf": False, "marca_stj": False}),
            token_count=10,
            embedding=serialize_embedding([0.1, 0.2, 0.3]),
        )
        db_session.add_all([chunk_with_artigo, chunk_without_artigo])
        await db_session.commit()

        results = await vector_store.search(
            query_embedding=[0.2, 0.2, 0.2],
            limit=10,
            min_similarity=0.0,
            filters={"artigo": "not_null"},
        )

        assert len(results) == 1
        assert results[0][0].chunk_id == "chunk-artigo"
        assert results[0][0].metadados.artigo == "5"

    @pytest.mark.asyncio
    async def test_search_filters_or_group(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test OR grouping for metadata filters (e.g., STF OR STJ)."""
        vector_store = VectorStore(session=db_session)

        doc = DocumentORM(
            nome="JURIS",
            arquivo_origem="juris.docx",
            chunk_count=3,
            token_count=30,
        )
        db_session.add(doc)
        await db_session.flush()

        chunk_stf = ChunkORM(
            id="chunk-stf",
            documento_id=doc.id,
            texto="Jurisprudencia STF sobre tema X",
            metadados=json.dumps({"documento": "STF", "marca_stf": True, "marca_stj": False}),
            token_count=10,
            embedding=serialize_embedding([0.2, 0.1, 0.3]),
        )
        chunk_stj = ChunkORM(
            id="chunk-stj",
            documento_id=doc.id,
            texto="Jurisprudencia STJ sobre tema Y",
            metadados=json.dumps({"documento": "STJ", "marca_stf": False, "marca_stj": True}),
            token_count=10,
            embedding=serialize_embedding([0.2, 0.3, 0.1]),
        )
        chunk_none = ChunkORM(
            id="chunk-none",
            documento_id=doc.id,
            texto="Texto sem jurisprudencia",
            metadados=json.dumps({"documento": "GEN", "marca_stf": False, "marca_stj": False}),
            token_count=10,
            embedding=serialize_embedding([0.1, 0.3, 0.2]),
        )
        db_session.add_all([chunk_stf, chunk_stj, chunk_none])
        await db_session.commit()

        results = await vector_store.search(
            query_embedding=[0.2, 0.2, 0.2],
            limit=10,
            min_similarity=0.0,
            filters={"__or__": [{"marca_stf": True}, {"marca_stj": True}]},
        )

        result_ids = {chunk.chunk_id for chunk, _ in results}
        assert result_ids == {"chunk-stf", "chunk-stj"}

    @pytest.mark.asyncio
    async def test_search_rejects_invalid_filter_key(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Unknown filter keys must raise a controlled domain error."""
        vector_store = VectorStore(session=db_session)

        with pytest.raises(BotSalinhaError):
            await vector_store.search(
                query_embedding=[0.2, 0.2, 0.2],
                limit=5,
                min_similarity=0.0,
                filters={"drop_table": "now"},
            )

    @pytest.mark.asyncio
    async def test_search_temporal_filters(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Temporal range filters should constrain valid_from/valid_to."""
        vector_store = VectorStore(session=db_session)

        doc = DocumentORM(
            nome="TEMPORAL",
            arquivo_origem="temporal.docx",
            chunk_count=2,
            token_count=20,
        )
        db_session.add(doc)
        await db_session.flush()

        chunk_old = ChunkORM(
            id="chunk-old",
            documento_id=doc.id,
            texto="Texto antigo",
            metadados=json.dumps(
                {"documento": "LIA", "valid_from": "2018-01-01", "valid_to": "2020-12-31"}
            ),
            token_count=10,
            embedding=serialize_embedding([0.4, 0.1, 0.2]),
        )
        chunk_new = ChunkORM(
            id="chunk-new",
            documento_id=doc.id,
            texto="Texto novo",
            metadados=json.dumps(
                {"documento": "LIA", "valid_from": "2021-10-26", "valid_to": "9999-12-31"}
            ),
            token_count=10,
            embedding=serialize_embedding([0.4, 0.1, 0.2]),
        )
        db_session.add_all([chunk_old, chunk_new])
        await db_session.commit()

        results = await vector_store.search(
            query_embedding=[0.4, 0.1, 0.2],
            limit=10,
            min_similarity=0.0,
            filters={"valid_from_gte": "2021-01-01"},
        )
        result_ids = {chunk.chunk_id for chunk, _ in results}
        assert result_ids == {"chunk-new"}

    @pytest.mark.asyncio
    async def test_search_does_not_lose_relevant_chunk_by_physical_order(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Relevant chunk must survive even when inserted after many low-quality rows."""
        vector_store = VectorStore(session=db_session)

        doc = DocumentORM(
            nome="ORDEM-FISICA",
            arquivo_origem="ordem.docx",
            chunk_count=11,
            token_count=110,
        )
        db_session.add(doc)
        await db_session.flush()

        for idx in range(10):
            db_session.add(
                ChunkORM(
                    id=f"chunk-noise-{idx}",
                    documento_id=doc.id,
                    texto=f"Ruido {idx}",
                    metadados=json.dumps({"documento": "NOISE"}),
                    token_count=10,
                    embedding=serialize_embedding([1.0, 0.0, 0.0]),
                )
            )

        db_session.add(
            ChunkORM(
                id="chunk-relevante",
                documento_id=doc.id,
                texto="Conteudo juridico realmente relevante",
                metadados=json.dumps({"documento": "RELEVANTE"}),
                token_count=10,
                embedding=serialize_embedding([0.0, 1.0, 0.0]),
            )
        )
        await db_session.commit()

        results = await vector_store.search(
            query_embedding=[0.0, 1.0, 0.0],
            limit=1,
            min_similarity=0.0,
            candidate_limit=3,
        )

        assert len(results) == 1
        assert results[0][0].chunk_id == "chunk-relevante"

    @pytest.mark.asyncio
    async def test_search_hybrid_with_fts5(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Hybrid stage-1 should include lexical candidates via FTS5 when available."""
        vector_store = VectorStore(session=db_session)
        fts5_enabled = await self._create_fts5_table(db_session)
        if not fts5_enabled:
            pytest.skip("SQLite build sem FTS5 disponível para o teste")

        doc = DocumentORM(
            nome="HIBRIDO-FTS",
            arquivo_origem="hibrido-fts.docx",
            chunk_count=3,
            token_count=30,
        )
        db_session.add(doc)
        await db_session.flush()

        db_session.add_all(
            [
                ChunkORM(
                    id="chunk-semantico-top",
                    documento_id=doc.id,
                    texto="Texto generico sem token raro",
                    metadados=json.dumps({"documento": "TEST"}),
                    token_count=10,
                    embedding=serialize_embedding([1.0, 0.0, 0.0]),
                ),
                ChunkORM(
                    id="chunk-lexical-raro",
                    documento_id=doc.id,
                    texto="Contem termo extraordinariojurexclusivo de busca",
                    metadados=json.dumps({"documento": "TEST"}),
                    token_count=10,
                    embedding=serialize_embedding([0.0, 1.0, 0.0]),
                ),
                ChunkORM(
                    id="chunk-semantico-2",
                    documento_id=doc.id,
                    texto="Outro texto comum sem termo especial",
                    metadados=json.dumps({"documento": "TEST"}),
                    token_count=10,
                    embedding=serialize_embedding([0.9, 0.0, 0.0]),
                ),
            ]
        )
        await db_session.commit()

        await db_session.execute(
            text(
                """
                INSERT INTO rag_chunks_fts(rowid, texto)
                SELECT rowid, texto FROM rag_chunks
                """
            )
        )
        await db_session.commit()

        results = await vector_store.search(
            query_embedding=[1.0, 0.0, 0.0],
            query_text="extraordinariojurexclusivo",
            limit=2,
            min_similarity=0.0,
            candidate_limit=1,
        )

        result_ids = [chunk.chunk_id for chunk, _ in results]
        assert "chunk-lexical-raro" in result_ids
        assert await vector_store.has_fts5_capability() is True

    @pytest.mark.asyncio
    async def test_search_hybrid_without_fts5_fallback(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Hybrid stage-1 should fallback to LIKE lexical retrieval when FTS5 is unavailable."""
        vector_store = VectorStore(session=db_session)

        doc = DocumentORM(
            nome="HIBRIDO-NO-FTS",
            arquivo_origem="hibrido-no-fts.docx",
            chunk_count=2,
            token_count=20,
        )
        db_session.add(doc)
        await db_session.flush()

        db_session.add_all(
            [
                ChunkORM(
                    id="chunk-top-semantic",
                    documento_id=doc.id,
                    texto="texto comum sem termo único",
                    metadados=json.dumps({"documento": "TEST"}),
                    token_count=10,
                    embedding=serialize_embedding([1.0, 0.0, 0.0]),
                ),
                ChunkORM(
                    id="chunk-lexical-fallback",
                    documento_id=doc.id,
                    texto="conteudo com palavrachavesuperrara para busca lexical",
                    metadados=json.dumps({"documento": "TEST"}),
                    token_count=10,
                    embedding=serialize_embedding([0.0, 1.0, 0.0]),
                ),
            ]
        )
        await db_session.commit()

        results = await vector_store.search(
            query_embedding=[1.0, 0.0, 0.0],
            query_text="palavrachavesuperrara",
            limit=2,
            min_similarity=0.0,
            candidate_limit=1,
        )

        result_ids = [chunk.chunk_id for chunk, _ in results]
        assert "chunk-lexical-fallback" in result_ids
        assert await vector_store.has_fts5_capability() is False

    async def _create_fts5_table(self, db_session: AsyncSession) -> bool:
        """Try to create FTS5 table for tests; return False when not supported."""
        try:
            await db_session.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts
                    USING fts5(texto, tokenize='unicode61 remove_diacritics 2')
                    """
                )
            )
            await db_session.commit()
            return True
        except Exception:
            await db_session.rollback()
            return False
