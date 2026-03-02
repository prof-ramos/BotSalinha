"""RAG (Retrieval-Augmented Generation) module for BotSalinha."""

from .models import Chunk, ChunkMetadata, ConfiancaLevel, Document, RAGContext
from .parser import DOCXParser
from .services import (
    EMBEDDING_DIM,
    CachedEmbeddingService,
    CacheStats,
    CodeIngestionResult,
    CodeIngestionService,
    DocumentResult,
    EmbeddingService,
    IngestionError,
    IngestionService,
    LRUCache,
    QueryService,
    SemanticCache,
)
from .storage import VectorStore, cosine_similarity
from .utils import ConfiancaCalculator, MetadataExtractor

__all__ = [
    # Models
    "ChunkMetadata",
    "Chunk",
    "Document",
    "ConfiancaLevel",
    "RAGContext",
    # Parsers
    "DOCXParser",
    # Utils
    "MetadataExtractor",
    "ConfiancaCalculator",
    # Services
    "EmbeddingService",
    "CachedEmbeddingService",
    "LRUCache",
    "QueryService",
    "SemanticCache",
    "CacheStats",
    "CodeIngestionService",
    "CodeIngestionResult",
    "DocumentResult",
    "IngestionService",
    "IngestionError",
    "EMBEDDING_DIM",
    # Storage
    "VectorStore",
    "cosine_similarity",
]
