"""
RAG data models for BotSalinha.

Defines Pydantic schemas for RAG (Retrieval-Augmented Generation) functionality,
including chunks, documents, and RAG context structures.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    documento: str = Field(..., description="Document identifier (e.g., 'CF/88')")
    titulo: str | None = Field(None, description="Section title")
    capitulo: str | None = Field(None, description="Chapter reference")
    secao: str | None = Field(None, description="Section reference")
    artigo: str | None = Field(None, description="Article number")
    paragrafo: str | None = Field(None, description="Paragraph number")
    inciso: str | None = Field(None, description="Inciso/Item number")
    tipo: str | None = Field(None, description="Type of text (e.g., 'caput', 'inciso')")
    marca_atencao: bool = Field(False, description="Marked as important attention point")
    marca_stf: bool = Field(False, description="Marked as STF (Supreme Federal Court) relevant")
    marca_stj: bool = Field(False, description="Marked as STJ (Superior Court of Justice) relevant")
    marca_concurso: bool = Field(False, description="Marked as Exame/Concurso relevant")
    # Penal law specific markers
    marca_crime: bool = Field(False, description="Marked as containing criminal law content")
    marca_pena: bool = Field(False, description="Marked as containing penalty information")
    marca_hediondo: bool = Field(False, description="Marked as heinous crime reference")
    marca_acao_penal: bool = Field(False, description="Marked as containing criminal procedure info")
    marca_militar: bool = Field(False, description="Marked as military law/criminal content")
    banca: str | None = Field(None, description="Exam board/banca name")
    ano: str | None = Field(None, description="Exam year")


class Chunk(BaseModel):
    """A document chunk with text and metadata."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    documento_id: int = Field(..., description="Reference to document ID")
    texto: str = Field(..., description="Chunk text content")
    metadados: ChunkMetadata = Field(..., description="Chunk metadata")
    token_count: int = Field(..., description="Estimated token count", ge=0)
    posicao_documento: float = Field(
        ..., description="Position within document (0.0 to 1.0)", ge=0.0, le=1.0
    )


class Document(BaseModel):
    """A document that has been chunked for RAG."""

    id: int = Field(..., description="Document ID")
    nome: str = Field(..., description="Document name (e.g., 'CF/88')")
    arquivo_origem: str = Field(..., description="Source file path")
    chunk_count: int = Field(..., description="Number of chunks", ge=0)
    token_count: int = Field(..., description="Total token count", ge=0)


class ConfiancaLevel(StrEnum):
    """Confidence level for RAG retrieval."""

    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"
    SEM_RAG = "sem_rag"


class RAGContext(BaseModel):
    """Context retrieved from RAG for query augmentation."""

    chunks_usados: list[Chunk] = Field(default_factory=list, description="Chunks used for context")
    similaridades: list[float] = Field(
        default_factory=list, description="Similarity scores for each chunk"
    )
    confianca: ConfiancaLevel = Field(..., description="Overall confidence level")
    fontes: list[str] = Field(default_factory=list, description="Formatted source citations")

    @model_validator(mode="after")
    def validate_lengths(self) -> "RAGContext":
        if (
            self.chunks_usados is not None
            and self.similaridades is not None
            and len(self.chunks_usados) != len(self.similaridades)
        ):
            raise ValueError("O tamanho de chunks_usados e similaridades deve ser o mesmo.")
        return self


__all__ = [
    "ChunkMetadata",
    "Chunk",
    "Document",
    "ConfiancaLevel",
    "RAGContext",
]
