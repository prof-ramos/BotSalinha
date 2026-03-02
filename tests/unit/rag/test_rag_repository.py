"""Unit tests for RagRepository."""


import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.conversation import Base
from src.rag.models import Chunk, ChunkMetadata, Document
from src.rag.storage.rag_repository import RagRepository

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session_maker():
    """Create test database engine and session maker."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session maker
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    yield async_session_maker

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def rag_repository(async_session_maker):
    """Create RagRepository instance for testing."""
    repo = RagRepository(async_session_maker)
    yield repo


@pytest.mark.unit
class TestRagRepositorySaveChunk:
    """Tests for save_chunk method."""

    @pytest.mark.asyncio
    async def test_save_chunk(self, rag_repository: RagRepository) -> None:
        """Should save chunk with embedding."""
        metadata = ChunkMetadata(documento="test_doc")
        chunk = Chunk(
            chunk_id="test-chunk-1",
            documento_id=1,
            texto="Test chunk content",
            metadados=metadata,
            token_count=10,
            posicao_documento=0.5,
        )
        embedding = [0.1, 0.2, 0.3, 0.4]

        result = await rag_repository.save_chunk(chunk, embedding)

        assert result.chunk_id == "test-chunk-1"
        assert result.texto == "Test chunk content"

    @pytest.mark.asyncio
    async def test_save_chunk_update_existing(self, rag_repository: RagRepository) -> None:
        """Should update existing chunk."""
        metadata = ChunkMetadata(documento="test_doc")
        chunk = Chunk(
            chunk_id="test-chunk-1",
            documento_id=1,
            texto="Original content",
            metadados=metadata,
            token_count=10,
            posicao_documento=0.5,
        )
        embedding = [0.1, 0.2, 0.3, 0.4]

        # Save initial chunk
        await rag_repository.save_chunk(chunk, embedding)

        # Update chunk
        updated_metadata = ChunkMetadata(documento="updated_doc")
        updated_chunk = Chunk(
            chunk_id="test-chunk-1",
            documento_id=2,
            texto="Updated content",
            metadados=updated_metadata,
            token_count=20,
            posicao_documento=0.8,
        )
        updated_embedding = [0.5, 0.6, 0.7, 0.8]

        result = await rag_repository.save_chunk(updated_chunk, updated_embedding)

        assert result.texto == "Updated content"
        assert result.documento_id == 2
        assert result.token_count == 20


@pytest.mark.unit
class TestRagRepositoryGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id(self, rag_repository: RagRepository) -> None:
        """Should retrieve chunk by ID."""
        metadata = ChunkMetadata(documento="test_doc")
        chunk = Chunk(
            chunk_id="test-chunk-1",
            documento_id=1,
            texto="Test chunk content",
            metadados=metadata,
            token_count=10,
            posicao_documento=0.5,
        )
        embedding = [0.1, 0.2, 0.3, 0.4]

        await rag_repository.save_chunk(chunk, embedding)
        result = await rag_repository.get_by_id("test-chunk-1")

        assert result is not None
        assert result.chunk_id == "test-chunk-1"
        assert result.texto == "Test chunk content"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, rag_repository: RagRepository) -> None:
        """Should return None for non-existent chunk."""
        result = await rag_repository.get_by_id("nonexistent")

        assert result is None


@pytest.mark.unit
class TestRagRepositorySaveDocument:
    """Tests for save_document method."""

    @pytest.mark.asyncio
    async def test_save_document(self, rag_repository: RagRepository) -> None:
        """Should save document metadata."""
        document = Document(
            id=1,
            nome="Test Document",
            arquivo_origem="/path/to/file.docx",
            chunk_count=5,
            token_count=1000,
        )

        result = await rag_repository.save_document(document)

        assert result.id == 1
        assert result.nome == "Test Document"
        assert result.arquivo_origem == "/path/to/file.docx"

    @pytest.mark.asyncio
    async def test_save_document_update_existing(self, rag_repository: RagRepository) -> None:
        """Should update existing document."""
        document = Document(
            id=1,
            nome="Original Name",
            arquivo_origem="/original/path",
            chunk_count=5,
            token_count=1000,
        )

        await rag_repository.save_document(document)

        updated_document = Document(
            id=1,
            nome="Updated Name",
            arquivo_origem="/updated/path",
            chunk_count=10,
            token_count=2000,
        )

        result = await rag_repository.save_document(updated_document)

        assert result.nome == "Updated Name"
        assert result.chunk_count == 10
        assert result.token_count == 2000

    @pytest.mark.asyncio
    async def test_save_document_deduplicates_by_content_hash(
        self,
        rag_repository: RagRepository,
    ) -> None:
        """Should deduplicate documents with same logical content hash."""
        first = Document(
            id=1,
            nome="Same Name",
            arquivo_origem="/same/path",
            chunk_count=2,
            token_count=100,
        )
        second = Document(
            id=999,
            nome="Same Name",
            arquivo_origem="/same/path",
            chunk_count=3,
            token_count=150,
        )

        saved_first = await rag_repository.save_document(first)
        saved_second = await rag_repository.save_document(second)

        assert saved_second.id == saved_first.id
        assert saved_second.content_hash == saved_first.content_hash
        assert saved_second.chunk_count == 3
        assert saved_second.token_count == 150


@pytest.mark.unit
class TestRagRepositoryDeleteChunk:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_chunk(self, rag_repository: RagRepository) -> None:
        """Should delete chunk successfully."""
        metadata = ChunkMetadata(documento="test_doc")
        chunk = Chunk(
            chunk_id="test-chunk-1",
            documento_id=1,
            texto="Test chunk content",
            metadados=metadata,
            token_count=10,
            posicao_documento=0.5,
        )
        embedding = [0.1, 0.2, 0.3, 0.4]

        await rag_repository.save_chunk(chunk, embedding)
        result = await rag_repository.delete("test-chunk-1")

        assert result is True

        # Verify deletion
        retrieved = await rag_repository.get_by_id("test-chunk-1")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_chunk_not_found(self, rag_repository: RagRepository) -> None:
        """Should return False for non-existent chunk."""
        result = await rag_repository.delete("nonexistent")

        assert result is False


@pytest.mark.unit
class TestRagRepositorySearch:
    """Tests for search method."""

    @pytest.mark.asyncio
    async def test_search(self, rag_repository: RagRepository) -> None:
        """Should perform vector similarity search."""
        # Create chunks with different embeddings
        metadata1 = ChunkMetadata(documento="doc1")
        chunk1 = Chunk(
            chunk_id="chunk-1",
            documento_id=1,
            texto="Content about legal rights",
            metadados=metadata1,
            token_count=10,
            posicao_documento=0.0,
        )
        embedding1 = [1.0, 0.0, 0.0]

        metadata2 = ChunkMetadata(documento="doc2")
        chunk2 = Chunk(
            chunk_id="chunk-2",
            documento_id=1,
            texto="Content about criminal law",
            metadados=metadata2,
            token_count=10,
            posicao_documento=0.5,
        )
        embedding2 = [0.0, 1.0, 0.0]

        metadata3 = ChunkMetadata(documento="doc1")
        chunk3 = Chunk(
            chunk_id="chunk-3",
            documento_id=1,
            texto="Content about civil procedure",
            metadados=metadata3,
            token_count=10,
            posicao_documento=1.0,
        )
        embedding3 = [0.9, 0.1, 0.0]  # Similar to chunk1

        await rag_repository.save_chunk(chunk1, embedding1)
        await rag_repository.save_chunk(chunk2, embedding2)
        await rag_repository.save_chunk(chunk3, embedding3)

        # Search with query embedding similar to chunk1 and chunk3
        query_embedding = [1.0, 0.0, 0.0]
        results = await rag_repository.search(query_embedding, limit=2)

        assert len(results) == 2
        # First result should be chunk1 (exact match)
        assert results[0][0].chunk_id == "chunk-1"
        assert results[0][1] == 1.0  # Perfect similarity

    @pytest.mark.asyncio
    async def test_search_with_filters(self, rag_repository: RagRepository) -> None:
        """Should apply filters to search results."""
        metadata1 = ChunkMetadata(documento="doc1")
        chunk1 = Chunk(
            chunk_id="chunk-1",
            documento_id=1,
            texto="Content from doc1",
            metadados=metadata1,
            token_count=10,
            posicao_documento=0.0,
        )
        embedding1 = [1.0, 0.0, 0.0]

        metadata2 = ChunkMetadata(documento="doc2")
        chunk2 = Chunk(
            chunk_id="chunk-2",
            documento_id=1,
            texto="Content from doc2",
            metadados=metadata2,
            token_count=10,
            posicao_documento=0.5,
        )
        embedding2 = [1.0, 0.0, 0.0]

        await rag_repository.save_chunk(chunk1, embedding1)
        await rag_repository.save_chunk(chunk2, embedding2)

        # Search with filter for doc1 only
        query_embedding = [1.0, 0.0, 0.0]
        results = await rag_repository.search(
            query_embedding, limit=10, filters={"documento": "doc1"}
        )

        assert len(results) == 1
        assert results[0][0].chunk_id == "chunk-1"

    @pytest.mark.asyncio
    async def test_search_empty_results(self, rag_repository: RagRepository) -> None:
        """Should return empty list when no chunks match."""
        query_embedding = [1.0, 0.0, 0.0]
        results = await rag_repository.search(query_embedding)

        assert results == []


@pytest.mark.unit
class TestRagRepositoryGetDocumentById:
    """Tests for get_document_by_id method."""

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, rag_repository: RagRepository) -> None:
        """Should retrieve document by ID."""
        document = Document(
            id=1,
            nome="Test Document",
            arquivo_origem="/path/to/file.docx",
            chunk_count=5,
            token_count=1000,
        )

        await rag_repository.save_document(document)
        result = await rag_repository.get_document_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.nome == "Test Document"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(
        self, rag_repository: RagRepository
    ) -> None:
        """Should return None for non-existent document."""
        result = await rag_repository.get_document_by_id(999)

        assert result is None


@pytest.mark.unit
class TestRagRepositoryGetDocumentByName:
    """Tests for get_document_by_name method."""

    @pytest.mark.asyncio
    async def test_get_document_by_name(self, rag_repository: RagRepository) -> None:
        """Should retrieve document by name."""
        document = Document(
            id=1,
            nome="CF/88",
            arquivo_origem="/path/to/constituicao.docx",
            chunk_count=100,
            token_count=50000,
        )

        await rag_repository.save_document(document)
        result = await rag_repository.get_document_by_name("CF/88")

        assert result is not None
        assert result.id == 1
        assert result.nome == "CF/88"

    @pytest.mark.asyncio
    async def test_get_document_by_name_not_found(
        self, rag_repository: RagRepository
    ) -> None:
        """Should return None for non-existent document name."""
        result = await rag_repository.get_document_by_name("Nonexistent Document")

        assert result is None


@pytest.mark.unit
class TestRagRepositoryDeleteDocument:
    """Tests for delete_document method."""

    @pytest.mark.asyncio
    async def test_delete_document(self, rag_repository: RagRepository) -> None:
        """Should delete document (cascade deletes chunks)."""
        # Create document
        document = Document(
            id=1,
            nome="Test Document",
            arquivo_origem="/path/to/file.docx",
            chunk_count=2,
            token_count=100,
        )
        await rag_repository.save_document(document)

        # Create chunks for the document
        metadata1 = ChunkMetadata(documento="Test Document")
        chunk1 = Chunk(
            chunk_id="chunk-1",
            documento_id=1,
            texto="First chunk",
            metadados=metadata1,
            token_count=50,
            posicao_documento=0.0,
        )
        await rag_repository.save_chunk(chunk1, [1.0, 0.0])

        metadata2 = ChunkMetadata(documento="Test Document")
        chunk2 = Chunk(
            chunk_id="chunk-2",
            documento_id=1,
            texto="Second chunk",
            metadados=metadata2,
            token_count=50,
            posicao_documento=1.0,
        )
        await rag_repository.save_chunk(chunk2, [0.0, 1.0])

        # Delete document
        result = await rag_repository.delete_document(1)

        assert result is True

        # Verify document is deleted
        doc = await rag_repository.get_document_by_id(1)
        assert doc is None

        # Verify chunks are cascade deleted
        chunk1_retrieved = await rag_repository.get_by_id("chunk-1")
        chunk2_retrieved = await rag_repository.get_by_id("chunk-2")
        assert chunk1_retrieved is None
        assert chunk2_retrieved is None

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, rag_repository: RagRepository) -> None:
        """Should return False for non-existent document."""
        result = await rag_repository.delete_document(999)

        assert result is False


@pytest.mark.unit
class TestRagRepositoryListDocuments:
    """Tests for list_documents method."""

    @pytest.mark.asyncio
    async def test_list_documents(self, rag_repository: RagRepository) -> None:
        """Should list all documents ordered by name."""
        # Create multiple documents
        doc1 = Document(id=1, nome="Zebra", arquivo_origem="/z", chunk_count=1, token_count=10)
        doc2 = Document(id=2, nome="Apple", arquivo_origem="/a", chunk_count=1, token_count=10)
        doc3 = Document(id=3, nome="Mango", arquivo_origem="/m", chunk_count=1, token_count=10)

        await rag_repository.save_document(doc1)
        await rag_repository.save_document(doc2)
        await rag_repository.save_document(doc3)

        results = await rag_repository.list_documents()

        assert len(results) == 3
        # Should be ordered by name alphabetically
        assert results[0].nome == "Apple"
        assert results[1].nome == "Mango"
        assert results[2].nome == "Zebra"

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, rag_repository: RagRepository) -> None:
        """Should return empty list when no documents exist."""
        results = await rag_repository.list_documents()

        assert results == []


@pytest.mark.unit
class TestRagRepositoryHelperMethods:
    """Tests for helper methods."""

    def test_serialize_embedding(self) -> None:
        """Should convert embedding list to bytes."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        result = RagRepository._serialize_embedding(embedding)

        assert isinstance(result, bytes)
        # Verify deserialization
        deserialized = RagRepository._deserialize_embedding(result)
        np.testing.assert_array_almost_equal(deserialized, embedding, decimal=5)

    def test_deserialize_embedding(self) -> None:
        """Should convert bytes to embedding list."""
        embedding = [1.0, 2.0, 3.0]
        serialized = np.array(embedding, dtype=np.float32).tobytes()

        result = RagRepository._deserialize_embedding(serialized)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == 1.0
        assert result[1] == 2.0
        assert result[2] == 3.0

    def test_cosine_similarity(self) -> None:
        """Should calculate cosine similarity correctly."""
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]

        result = RagRepository._cosine_similarity(a, b)

        assert result == 1.0  # Perfect similarity

    def test_cosine_similarity_orthogonal(self) -> None:
        """Should return 0 for orthogonal vectors."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]

        result = RagRepository._cosine_similarity(a, b)

        assert result == 0.0  # Orthogonal

    def test_cosine_similarity_zero_vector(self) -> None:
        """Should return 0 when one vector is zero."""
        a = [1.0, 1.0, 1.0]
        b = [0.0, 0.0, 0.0]

        result = RagRepository._cosine_similarity(a, b)

        assert result == 0.0
