"""Unit tests for ChromaStore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.rag.models import Chunk, ChunkMetadata
from src.rag.storage.chroma_store import ChromaStore, bm25_score
from src.utils.errors import BotSalinhaError


@pytest.mark.unit
class TestBM25Score:
    """Test BM25 scoring function."""

    def test_bm25_score_exact_match(self) -> None:
        """Test BM25 score with exact term match."""
        query = "constituição federal"
        document = "A constituição federal do brasil"
        score = bm25_score(query, document)
        assert score > 0

    def test_bm25_score_no_match(self) -> None:
        """Test BM25 score with no matching terms."""
        query = "xyz abc"
        document = "documento completamente diferente"
        score = bm25_score(query, document)
        assert score == 0.0

    def test_bm25_score_partial_match(self) -> None:
        """Test BM25 score with partial term match."""
        query = "direito penal"
        document = "O direito penal é importante"
        score = bm25_score(query, document)
        assert score > 0


@pytest.mark.unit
class TestChromaStore:
    """Unit tests for ChromaStore."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock AsyncSession."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock ChromaDB client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_collection(self) -> MagicMock:
        """Create mock ChromaDB collection."""
        collection = MagicMock()
        collection.count.return_value = 100
        collection.get.return_value = {"ids": ["1", "2", "3"]}
        return collection

    @pytest.fixture
    def chroma_store(
        self, mock_session: AsyncMock, mock_client: MagicMock, mock_collection: MagicMock
    ) -> ChromaStore:
        """Create ChromaStore with mocked dependencies."""
        store = ChromaStore(mock_session)
        store._client = mock_client
        store._collection = mock_collection
        return store

    @pytest.fixture
    def sample_chunk(self) -> Chunk:
        """Create sample chunk for testing."""
        metadata = ChunkMetadata(
            documento="CF/88",
            tipo="artigo",
            artigo="5º",
        )
        return Chunk(
            chunk_id="test-chunk-1",
            documento_id=1,
            texto="Texto do chunk de teste",
            metadados=metadata,
            token_count=10,
            posicao_documento=0.0,
        )

    def test_init_client(self, mock_session: AsyncMock, mock_client: MagicMock) -> None:
        """Test ChromaDB client initialization."""
        with patch("chromadb.PersistentClient", return_value=mock_client):
            store = ChromaStore(mock_session)
            assert store._client is None  # Lazy initialization

            client = store._init_client()
            assert client == mock_client
            assert store._client == mock_client

    def test_get_or_create_collection(
        self, chroma_store: ChromaStore, mock_collection: MagicMock
    ) -> None:
        """Test collection retrieval/creation."""
        collection = chroma_store._get_or_create_collection()
        assert collection == mock_collection

    @pytest.mark.asyncio
    async def test_add_embeddings(
        self, chroma_store: ChromaStore, mock_collection: MagicMock, sample_chunk: Chunk
    ) -> None:
        """Test adding embeddings to ChromaDB."""
        embeddings = [0.1, 0.2, 0.3]

        await chroma_store.add_embeddings([(sample_chunk, embeddings)])

        # Verify collection.add was called
        mock_collection.add.assert_called_once()
        call_args = mock_collection.add.call_args

        assert "ids" in call_args.kwargs
        assert "embeddings" in call_args.kwargs
        assert "metadatas" in call_args.kwargs
        assert "documents" in call_args.kwargs

        assert call_args.kwargs["ids"] == ["test-chunk-1"]
        assert call_args.kwargs["embeddings"] == [embeddings]
        assert call_args.kwargs["documents"] == ["Texto do chunk de teste"]

    def test_convert_filters_for_chroma_simple(self, chroma_store: ChromaStore) -> None:
        """Test filter conversion for simple equality."""
        filters = {"artigo": "5º", "tipo": "artigo"}
        result = chroma_store._convert_filters_for_chroma(filters)

        assert result["artigo"] == "5º"
        assert result["tipo"] == "artigo"

    def test_convert_filters_for_chroma_not_null(self, chroma_store: ChromaStore) -> None:
        """Test filter conversion for not_null."""
        filters = {"artigo": "not_null"}
        result = chroma_store._convert_filters_for_chroma(filters)

        assert result["artigo"] == {"$ne": None}

    def test_convert_filters_for_chroma_or(self, chroma_store: ChromaStore) -> None:
        """Test filter conversion for OR logic."""
        filters = {
            "__or__": [
                {"marca_stf": True},
                {"marca_stj": True},
            ]
        }
        result = chroma_store._convert_filters_for_chroma(filters)

        assert "$or" in result
        assert len(result["$or"]) == 2

    def test_convert_filters_for_chroma_invalid_key(self, chroma_store: ChromaStore) -> None:
        """Test filter conversion with invalid key."""
        filters = {"invalid_key": "value"}

        with pytest.raises(BotSalinhaError):  # Key validation error
            chroma_store._convert_filters_for_chroma(filters)

    @pytest.mark.asyncio
    async def test_bm25_rerank(self, chroma_store: ChromaStore, sample_chunk: Chunk) -> None:
        """Test BM25 reranking."""
        chunks = [
            (sample_chunk, 0.8, "direito constitucional"),
            (sample_chunk, 0.6, "texto completamente diferente"),
        ]

        reranked = chroma_store._bm25_rerank("direito", chunks)

        # First chunk should have higher score after reranking
        assert reranked[0][1] >= reranked[1][1]

    @pytest.mark.asyncio
    async def test_count_chunks(
        self, chroma_store: ChromaStore, mock_collection: MagicMock
    ) -> None:
        """Test counting chunks."""
        mock_collection.count.return_value = 100

        count = await chroma_store.count_chunks()

        assert count == 100
        mock_collection.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_chunks_with_document_filter(
        self, chroma_store: ChromaStore, mock_collection: MagicMock
    ) -> None:
        """Test counting chunks with document filter."""
        mock_collection.get.return_value = {"ids": ["1", "2", "3"]}

        count = await chroma_store.count_chunks(documento_id=1)

        assert count == 3
        mock_collection.get.assert_called_once_with(where={"documento_id": "1"})


__all__ = []
