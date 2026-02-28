"""Text chunking strategies for RAG."""

from __future__ import annotations

from typing import Any

import structlog

from src.rag.models import Chunk
from src.rag.utils.metadata_extractor import MetadataExtractor

log = structlog.get_logger(__name__)


class ChunkExtractor:
    """
    Extract chunks from parsed document with hierarchical context preservation.

    Groups paragraphs respecting max_tokens while preserving context
    (title, chapter, section), adds overlap at natural boundaries,
    and enriches metadata using MetadataExtractor.
    """

    # Default configuration
    DEFAULT_MAX_TOKENS = 500
    DEFAULT_OVERLAP_TOKENS = 50
    DEFAULT_RESPECT_BOUNDARIES = True
    DEFAULT_MIN_CHUNK_SIZE = 100
    DEFAULT_METADATA_MAX_DEPTH = 3

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the chunk extractor.

        Args:
            config: Optional configuration dict with keys:
                - max_tokens: Maximum tokens per chunk (default: 500)
                - overlap_tokens: Tokens to overlap between chunks (default: 50)
                - respect_boundaries: Respect natural boundaries (default: True)
                - min_chunk_size: Minimum chunk size in tokens (default: 100)
                - metadata_max_depth: Max hierarchy depth for metadata (default: 3)
        """
        self.config = config or {}

        self._max_tokens = self.config.get("max_tokens", self.DEFAULT_MAX_TOKENS)
        self._overlap_tokens = self.config.get("overlap_tokens", self.DEFAULT_OVERLAP_TOKENS)
        self._respect_boundaries = self.config.get(
            "respect_boundaries", self.DEFAULT_RESPECT_BOUNDARIES
        )
        self._min_chunk_size = self.config.get("min_chunk_size", self.DEFAULT_MIN_CHUNK_SIZE)
        self._metadata_max_depth = self.config.get(
            "metadata_max_depth", self.DEFAULT_METADATA_MAX_DEPTH
        )

        log.debug(
            "rag_chunker_initialized",
            max_tokens=self._max_tokens,
            overlap_tokens=self._overlap_tokens,
            respect_boundaries=self._respect_boundaries,
            min_chunk_size=self._min_chunk_size,
            metadata_max_depth=self._metadata_max_depth,
        )

    def extract_chunks(
        self,
        parsed_doc: list[dict[str, Any]],
        metadata_extractor: MetadataExtractor,
        document_name: str = "unknown",
        documento_id: int = 0,
    ) -> list[Chunk]:
        """
        Extract chunks from parsed document.

        Groups paragraphs respecting max_tokens, preserves hierarchical
        context, adds overlap at natural boundaries, calculates position,
        generates unique chunk_id, and enriches metadata.

        Args:
            parsed_doc: List of paragraph dicts from DOCXParser
            metadata_extractor: MetadataExtractor instance for enrichment
            document_name: Document identifier (e.g., 'CF/88')
            documento_id: Document ID for database reference

        Returns:
            List of Chunk objects with enriched metadata
        """
        if not parsed_doc:
            log.warning("rag_chunker_empty_document", document=document_name)
            return []

        chunks: list[Chunk] = []
        current_chunk: list[dict[str, Any]] = []
        current_tokens = 0
        chunk_sequence = 0
        total_paragraphs = len(parsed_doc)

        log.info(
            "rag_chunk_progress",
            document=document_name,
            total_paragraphs=total_paragraphs,
            stage="started",
        )

        for idx, paragraph in enumerate(parsed_doc):
            paragraph_text = paragraph.get("text", "")
            paragraph_tokens = self._estimate_tokens(paragraph_text)

            # Check if we should break before adding this paragraph
            should_break = self._should_break_chunk(paragraph, current_tokens, paragraph_tokens)

            if should_break and current_chunk:
                # Create chunk from accumulated paragraphs
                chunk = self._create_chunk(
                    parsed_doc=parsed_doc,
                    current_chunk=current_chunk,
                    metadata_extractor=metadata_extractor,
                    document_name=document_name,
                    documento_id=documento_id,
                    sequence=chunk_sequence,
                    total_paragraphs=total_paragraphs,
                    start_idx=idx - len(current_chunk),
                )
                chunks.append(chunk)
                chunk_sequence += 1

                # Start new chunk with overlap if configured
                current_chunk, current_tokens = self._create_overlap_chunk(current_chunk)

            # Add paragraph to current chunk
            current_chunk.append(paragraph)
            current_tokens += paragraph_tokens

            # Log progress periodically
            if (idx + 1) % 100 == 0 or (idx + 1) == total_paragraphs:
                log.info(
                    "rag_chunk_progress",
                    document=document_name,
                    processed=idx + 1,
                    total=total_paragraphs,
                    chunks_created=len(chunks),
                    progress_percent=round((idx + 1) / total_paragraphs * 100, 1),
                )

        # Don't forget the last chunk
        if current_chunk:
            chunk = self._create_chunk(
                parsed_doc=parsed_doc,
                current_chunk=current_chunk,
                metadata_extractor=metadata_extractor,
                document_name=document_name,
                documento_id=documento_id,
                sequence=chunk_sequence,
                total_paragraphs=total_paragraphs,
                start_idx=total_paragraphs - len(current_chunk),
            )
            chunks.append(chunk)

        log.info(
            "rag_chunk_progress",
            document=document_name,
            stage="completed",
            total_chunks=len(chunks),
            total_tokens=sum(c.token_count for c in chunks),
        )

        return chunks

    def _create_chunk(
        self,
        parsed_doc: list[dict[str, Any]],
        current_chunk: list[dict[str, Any]],
        metadata_extractor: MetadataExtractor,
        document_name: str,
        documento_id: int,
        sequence: int,
        total_paragraphs: int,
        start_idx: int,
    ) -> Chunk:
        """Create a Chunk from accumulated paragraphs."""
        # Combine paragraph texts
        chunk_text = "\n\n".join(p.get("text", "") for p in current_chunk)
        token_count = self._estimate_tokens(chunk_text)

        # Get hierarchical context using the full document history
        context = self._get_hierarchical_context(parsed_doc, start_idx)
        context["documento"] = document_name

        # Extract metadata using MetadataExtractor
        metadata = metadata_extractor.extract(chunk_text, context)

        # Calculate position in document (0.0 to 1.0)
        end_idx = start_idx + len(current_chunk) - 1
        posicao_documento = (
            (start_idx + end_idx) / 2 / total_paragraphs if total_paragraphs > 0 else 0.0
        )

        # Generate unique chunk_id
        chunk_id = self._generate_chunk_id(document_name, sequence)

        chunk = Chunk(
            chunk_id=chunk_id,
            documento_id=documento_id,
            texto=chunk_text,
            metadados=metadata,
            token_count=token_count,
            posicao_documento=round(posicao_documento, 4),
        )

        log.info(
            "rag_chunk_created",
            chunk_id=chunk_id,
            document=document_name,
            sequence=sequence,
            token_count=token_count,
            position=posicao_documento,
            paragraphs=len(current_chunk),
        )

        return chunk

    def _create_overlap_chunk(
        self, previous_chunk: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Create new chunk with overlap from previous chunk.

        Returns:
            Tuple of (new_chunk_list, new_token_count)
        """
        if self._overlap_tokens <= 0:
            return [], 0

        overlap_chunk: list[dict[str, Any]] = []
        overlap_tokens = 0

        # Add paragraphs from end of previous chunk until we reach overlap_tokens
        for paragraph in reversed(previous_chunk):
            para_text = paragraph.get("text", "")
            para_tokens = self._estimate_tokens(para_text)

            if overlap_tokens + para_tokens > self._overlap_tokens:
                break

            overlap_chunk.insert(0, paragraph)
            overlap_tokens += para_tokens

        return overlap_chunk, overlap_tokens

    def _get_hierarchical_context(
        self, paragraphs: list[dict[str, Any]], current_idx: int
    ) -> dict[str, Any]:
        """
        Get hierarchical context (title, chapter, section) for current position.

        Scans backwards from current_idx to find the most recent headings
        at each level (1=title, 2=chapter, 3=section, etc.).

        Args:
            paragraphs: List of all paragraphs in document
            current_idx: Current paragraph index

        Returns:
            Dict with titulo, capitulo, secao, tipo based on headings
        """
        context: dict[str, Any] = {}

        # Track most recent heading at each level
        headings: dict[int, str] = {}

        # Scan backwards from current position
        for i in range(current_idx - 1, -1, -1):
            if i >= len(paragraphs):
                continue
            para = paragraphs[i]
            if para.get("is_heading") and para.get("heading_level"):
                level = para["heading_level"]
                if level > self._metadata_max_depth:
                    continue
                text = para.get("text", "")
                if level not in headings and text:
                    headings[level] = text

        # Map heading levels to context keys
        if 1 in headings:
            context["titulo"] = headings[1]
        if 2 in headings:
            context["capitulo"] = headings[2]
        if 3 in headings:
            context["secao"] = headings[3]

        # Determine type based on first paragraph in chunk
        if paragraphs and paragraphs[0].get("is_heading"):
            context["tipo"] = "heading"
        else:
            context["tipo"] = "content"

        return context

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses a simple heuristic: ~4 characters per token for Portuguese text.
        This is approximate but works well for chunk sizing.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        # Approximate: 4 characters per token for Portuguese/English
        return max(1, len(text) // 4)

    def _should_break_chunk(
        self, paragraph: dict[str, Any], current_tokens: int, paragraph_tokens: int
    ) -> bool:
        """
        Determine if we should break the chunk before adding this paragraph.

        Respects natural boundaries when respect_boundaries=True:
        - Major headings (level 1-2)
        - Would exceed max_tokens significantly

        Args:
            paragraph: Paragraph to potentially add
            current_tokens: Current chunk token count
            paragraph_tokens: Token count of paragraph to add

        Returns:
            True if chunk should break before this paragraph
        """
        # Check natural boundaries first (major headings)
        is_major_heading = (
            self._respect_boundaries
            and bool(paragraph.get("is_heading"))
            and (paragraph.get("heading_level", 99) or 99) <= 2
        )

        # Break if: (exceeds max AND has min content) OR (major heading AND has content)
        would_exceed_max = current_tokens + paragraph_tokens > self._max_tokens
        has_min_content = current_tokens >= self._min_chunk_size

        return (would_exceed_max and has_min_content) or (is_major_heading and has_min_content)

    def _generate_chunk_id(self, document_name: str, seq: int) -> str:
        """
        Generate unique chunk identifier.

        Format: {document_name}-{sequence}

        Sanitizes document_name to be filename-safe.

        Args:
            document_name: Document identifier
            seq: Chunk sequence number

        Returns:
            Unique chunk ID string
        """
        # Sanitize document name for use in ID
        safe_name = document_name.replace("/", "-").replace("\\", "-")
        safe_name = safe_name.replace(" ", "_").strip()
        return f"{safe_name}-{seq:04d}"


__all__ = ["ChunkExtractor"]
