"""RAG storage layer."""

from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import get_settings
from .qdrant_store import QdrantVectorStore
from .vector_store import VectorStore, cosine_similarity, deserialize_embedding, serialize_embedding


def get_vector_store(session: AsyncSession) -> VectorStore | QdrantVectorStore:
    """Build vector store backend based on settings."""
    backend = get_settings().rag.vector_backend
    if backend == "qdrant":
        return QdrantVectorStore()
    return VectorStore(session)


__all__ = [
    "VectorStore",
    "QdrantVectorStore",
    "get_vector_store",
    "cosine_similarity",
    "serialize_embedding",
    "deserialize_embedding",
]
