"""
RAG data models for BotSalinha.

Defines Pydantic schemas for RAG (Retrieval-Augmented Generation) functionality,
including chunks, documents, and RAG context structures.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ExamReference(BaseModel):
    """Reference to an exam source where a legal excerpt was charged."""

    source: str = Field(..., description="Exam or institution source (e.g., TRF3, PCPR)")
    year: int | None = Field(default=None, description="Exam year")


class ExamMark(BaseModel):
    """Structured exam marker extracted from annotation blocks."""

    concurso: str = Field(..., description="Exam institution or concurso identifier")
    ano: int | None = Field(default=None, description="Exam year if available")
    banca: str | None = Field(default=None, description="Exam board name if available")
    orgao: str | None = Field(default=None, description="Optional organization/body tag")


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    model_config = {"extra": "allow"}

    documento: str = Field(..., description="Document identifier (e.g., 'CF/88')")
    titulo: str | None = Field(None, description="Section title")
    capitulo: str | None = Field(None, description="Chapter reference")
    secao: str | None = Field(None, description="Section reference")
    hierarquia_normativa: list[str] = Field(
        default_factory=list,
        description="Normative hierarchy path for legal chunks",
    )
    law_name: str | None = Field(None, description="Law name (e.g., Código Civil)")
    law_number: str | None = Field(None, description="Law number (e.g., 10.406/2002)")
    artigo: str | None = Field(None, description="Article number")
    article: str | None = Field(None, description="Alias for article number")
    paragrafo: str | None = Field(None, description="Paragraph number")
    inciso: str | None = Field(None, description="Inciso/Item number")
    tipo: str | None = Field(None, description="Type of text (e.g., 'caput', 'inciso')")
    content_type: str | None = Field(
        None,
        description="One of: legal_text, jurisprudence, exam_question, doctrine",
    )
    source_type: str | None = Field(
        None,
        description=(
            "One of: lei_cf, emenda_constitucional, jurisprudence, "
            "commentary, exam_question"
        ),
    )
    exam_source: str | None = Field(None, description="Single detected exam source")
    exam_year: int | None = Field(None, description="Single detected exam year")
    exam_references: list[ExamReference] = Field(
        default_factory=list,
        description="Detected exam references list [{source, year}]",
    )
    exam_marks: list[ExamMark] = Field(
        default_factory=list,
        description="Structured exam tags [{concurso, ano, banca, orgao}]",
    )
    is_exam_focus: bool = Field(False, description="Whether this chunk is exam-oriented/high-yield")
    valid_from: str | None = Field(None, description="ISO date for validity start")
    valid_to: str | None = Field(None, description="ISO date for validity end")
    updated_by_law: str | None = Field(None, description="Law reference that updated this text")
    is_revoked: bool = Field(False, description="Whether the legal text is revoked")
    is_vetoed: bool = Field(False, description="Whether the legal text is vetoed")
    revocation_scope: str | None = Field(None, description="Revocation scope: total, partial, none")
    veto_scope: str | None = Field(None, description="Veto scope: total, partial, none")
    temporal_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for temporal extraction",
    )
    effective_text_version: str | None = Field(
        None,
        description="Human-readable legal version marker (e.g., pos_lei_14230_2021)",
    )
    jurisprudence_linked: list[str] = Field(
        default_factory=list,
        description="Linked jurisprudence references (info/sumula/etc.)",
    )
    linked_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Linked chunk IDs populated at retrieval time when available",
    )
    link_types: list[str] = Field(
        default_factory=list,
        description="Link types associated with linked_chunk_ids",
    )
    is_parent_chunk: bool = Field(False, description="Marks chunk as parent in parent-child hierarchy")
    parent_chunk_id: str | None = Field(None, description="Parent chunk ID when this is a child chunk")
    child_chunk_ids: list[str] = Field(default_factory=list, description="Child chunk IDs when this is a parent")
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
    # Code-specific fields (for code ingestion)
    file_path: str | None = Field(None, description="Source file path for code chunks")
    language: str | None = Field(None, description="Programming language (python, typescript, etc.)")
    layer: str | None = Field(None, description="Architectural layer (core, storage, rag, etc.)")
    module: str | None = Field(None, description="Module name")
    functions: list[str] = Field(default_factory=list, description="Function names found in code")
    classes: list[str] = Field(default_factory=list, description="Class names found in code")
    imports: list[str] = Field(default_factory=list, description="Imported modules")
    is_test: bool = Field(False, description="Whether this is a test file")

    @model_validator(mode="after")
    def sync_legacy_aliases(self) -> "ChunkMetadata":
        """Keep legacy and canonical aliases synchronized."""
        if self.article and not self.artigo:
            self.artigo = self.article
        if self.artigo and not self.article:
            self.article = self.artigo

        if self.content_type and not self.tipo:
            self.tipo = self.content_type
        if self.tipo and not self.content_type:
            self.content_type = self.tipo

        if self.content_type:
            normalized_content = self.content_type.strip().lower()
            content_aliases = {
                "jurisprudencia": "jurisprudence",
                "questao_prova": "exam_question",
                "questao": "exam_question",
                "comentario": "doctrine",
                "doutrina": "doctrine",
            }
            self.content_type = content_aliases.get(normalized_content, normalized_content)

        if self.source_type:
            normalized_source = self.source_type.strip().lower()
            source_aliases = {
                "lei": "lei_cf",
                "lei_cf88": "lei_cf",
                "emenda_constitucional": "emenda_constitucional",
                "jurisprudencia": "jurisprudence",
                "comentario": "commentary",
                "questao_prova": "exam_question",
            }
            self.source_type = source_aliases.get(normalized_source, normalized_source)
        return self


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
    content_hash: str | None = Field(
        default=None,
        description="SHA-256 hash used for deduplication",
    )
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
    retrieval_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Retrieval telemetry and ranking metadata",
    )
    query_normalized: str | None = Field(
        default=None,
        description="Normalized user query used during retrieval",
    )

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
    "ExamReference",
    "ExamMark",
    "ChunkMetadata",
    "Chunk",
    "Document",
    "ConfiancaLevel",
    "RAGContext",
]
