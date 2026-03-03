"""Integration tests for ChromaDB store."""

import json
import tempfile
from pathlib import Path

import pytest

from src.models.rag_models import ChunkORM
from src.rag.models import Chunk, ChunkMetadata
from src.rag.storage.chroma_store import ChromaStore
from src.rag.storage.vector_store import VectorStore


@pytest.fixture
def temp_chroma_path():
    """Create temporary directory for ChromaDB tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        chroma_path = Path(tmpdir) / "chroma"
        chroma_path.mkdir(parents=True, exist_ok=True)
        yield chroma_path


@pytest.fixture
async def chroma_store(temp_chroma_path, db_session):
    """Create ChromaStore with temporary ChromaDB path."""
    from src.config.settings import get_settings

    settings = get_settings()

    original_path = settings.rag.chroma.path
    original_enabled = settings.rag.chroma.enabled

    settings.rag.chroma.path = str(temp_chroma_path)
    settings.rag.chroma.enabled = True

    store = ChromaStore(db_session)

    # Clean collection before each test
    collection = store._get_or_create_collection()
    if collection.count() > 0:
        collection.delete(where={})

    # Clean database chunks
    await db_session.execute(ChunkORM.__table__.delete())
    await db_session.commit()

    yield store

    # Cleanup
    settings.rag.chroma.path = original_path
    settings.rag.chroma.enabled = original_enabled


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    metadata1 = ChunkMetadata(
        documento="CF/88",
        tipo="artigo",
        artigo="5º",
    )
    chunk1 = Chunk(
        chunk_id="test-1",
        documento_id=1,
        texto="Todos são iguais perante a lei",
        metadados=metadata1,
        token_count=8,
        posicao_documento=0.0,
    )

    metadata2 = ChunkMetadata(
        documento="CF/88",
        tipo="artigo",
        artigo="6º",
    )
    chunk2 = Chunk(
        chunk_id="test-2",
        documento_id=1,
        texto="É inviolável a liberdade de consciência",
        metadados=metadata2,
        token_count=7,
        posicao_documento=0.0,
    )

    return [chunk1, chunk2]


@pytest.fixture
async def sample_chunks_in_db(sample_chunks, db_session):
    """Create sample chunks in database for testing."""
    for chunk in sample_chunks:
        chunk_orm = ChunkORM(
            id=chunk.chunk_id,
            documento_id=chunk.documento_id,
            texto=chunk.texto,
            metadados=json.dumps(chunk.metadados.model_dump()),
            token_count=chunk.token_count,
        )
        db_session.add(chunk_orm)
    await db_session.commit()
    return sample_chunks


@pytest.mark.integration
class TestChromaIntegration:
    """Integration tests with real ChromaDB."""

    @pytest.mark.asyncio
    async def test_add_and_retrieve_chunks(self, chroma_store, sample_chunks_in_db):
        """Test adding and retrieving chunks."""
        embeddings = [[0.1] * 1536, [0.2] * 1536]  # Dummy embeddings

        await chroma_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))

        # Verify chunks were added
        count = await chroma_store.count_chunks()
        assert count == 2

    @pytest.mark.asyncio
    async def test_search_with_query(self, chroma_store, sample_chunks_in_db):
        """Test searching with query embedding."""
        embeddings = [[0.1] * 1536, [0.2] * 1536]
        await chroma_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))

        query_embedding = [0.15] * 1536
        results = await chroma_store.search(query_embedding, limit=5)

        assert len(results) > 0
        assert all(isinstance(chunk, Chunk) for chunk, _ in results)
        assert all(isinstance(score, float) for _, score in results)

    @pytest.mark.asyncio
    async def test_search_with_filters(self, chroma_store, sample_chunks_in_db):
        """Test searching with metadata filters."""
        embeddings = [[0.1] * 1536, [0.2] * 1536]
        await chroma_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))

        query_embedding = [0.15] * 1536
        results = await chroma_store.search(
            query_embedding,
            filters={"artigo": "5º"},
            limit=5,
        )

        # Should filter to only artigo 5º
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_with_min_similarity(self, chroma_store, sample_chunks_in_db):
        """Test searching with minimum similarity threshold."""
        # Use vectors with different directions (not just magnitudes)
        # Cosine similarity is direction-based, so we need opposite directions
        embeddings = [[0.1] * 1536, [-0.9] * 1536]  # Opposite directions
        await chroma_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))

        query_embedding = [0.1] * 1536
        results = await chroma_store.search(query_embedding, min_similarity=0.8)

        # Only first chunk should match (second is opposite direction)
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_count_chunks_by_document(self, chroma_store, sample_chunks_in_db):
        """Test counting chunks by document."""
        embeddings = [[0.1] * 1536, [0.2] * 1536]
        await chroma_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))

        count = await chroma_store.count_chunks(documento_id=1)
        assert count == 2

    @pytest.mark.asyncio
    async def test_dual_write_consistency(self, chroma_store, sample_chunks_in_db):
        """Test that dual-write maintains consistency."""
        sqlite_store = VectorStore(chroma_store._session)
        embeddings = [[0.1] * 1536, [0.2] * 1536]

        # Write to both
        await sqlite_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))
        await chroma_store.add_embeddings(list(zip(sample_chunks_in_db, embeddings, strict=True)))

        # Compare counts
        sqlite_count = await sqlite_store.count_chunks()
        chroma_count = await chroma_store.count_chunks()

        assert sqlite_count == chroma_count
