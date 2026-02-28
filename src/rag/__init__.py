"""RAG (Retrieval-Augmented Generation) module for BotSalinha."""

from .models import Chunk, ChunkMetadata, ConfiancaLevel, Document, RAGContext
from .parser import DOCXParser
from .services import EMBEDDING_DIM, EmbeddingService, QueryService
from .storage import VectorStore, cosine_similarity
from .utils import MetadataExtractor, ConfiancaCalculator

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
    "QueryService",
    "EMBEDDING_DIM",
    # Storage
    "VectorStore",
    "cosine_similarity",
]
