"""Text chunking strategies for RAG."""

from __future__ import annotations

import re
from typing import Any

import structlog
import tiktoken

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
    _ARTIGO_RE = re.compile(r"^\s*Art\.?\s*(\d+[A-Za-z]?)\b", re.IGNORECASE)
    _PARAGRAFO_RE = re.compile(
        r"^\s*(?:§\s*([0-9]+|[úu]nico)\s*[º°]?|par[aá]grafo\s+([úu]nico|\d+)\b)",
        re.IGNORECASE,
    )
    _INCISO_RE = re.compile(r"^\s*([IVXLCDM]+)\s*[-–—\)]", re.IGNORECASE)
    _ALINEA_RE = re.compile(r"^\s*([a-z])\)", re.IGNORECASE)

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

        # Initialize tiktoken encoding
        try:
            # Try to get encoding for a common model, default to o200k_base (GPT-4o)
            self._encoding = tiktoken.get_encoding("o200k_base")
        except Exception:
            # Fallback to cl100k_base (GPT-4/GPT-3.5)
            self._encoding = tiktoken.get_encoding("cl100k_base")

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

        semantic_blocks = self._build_semantic_blocks(parsed_doc)
        chunks: list[Chunk] = []
        chunks_by_id: dict[str, Chunk] = {}
        children_by_parent: dict[str, list[str]] = {}
        current_chunk: list[dict[str, Any]] = []
        current_tokens = 0
        chunk_sequence = 0
        total_paragraphs = len(parsed_doc)
        current_parent_chunk_id: str | None = None
        current_parent_article: str | None = None

        log.info(
            "rag_chunk_progress",
            document=document_name,
            total_paragraphs=total_paragraphs,
            semantic_blocks=len(semantic_blocks),
            stage="started",
        )

        for block_idx, block in enumerate(semantic_blocks):
            block_tokens = int(block["token_count"])
            start_idx = int(block["start_idx"])
            first_paragraph = block["paragraphs"][0]

            should_break = self._should_break_chunk(first_paragraph, current_tokens, block_tokens)

            if should_break and current_chunk:
                chunk = self._create_chunk(
                    parsed_doc=parsed_doc,
                    current_chunk=current_chunk,
                    metadata_extractor=metadata_extractor,
                    document_name=document_name,
                    documento_id=documento_id,
                    sequence=chunk_sequence,
                    total_paragraphs=total_paragraphs,
                    start_idx=self._get_paragraph_index(parsed_doc, current_chunk[0]),
                )
                chunk, current_parent_chunk_id, current_parent_article = self._annotate_parent_child(
                    chunk=chunk,
                    current_parent_chunk_id=current_parent_chunk_id,
                    current_parent_article=current_parent_article,
                    children_by_parent=children_by_parent,
                )
                chunks.append(chunk)
                chunks_by_id[chunk.chunk_id] = chunk
                chunk_sequence += 1

                current_chunk, current_tokens = self._create_overlap_chunk(current_chunk)

            current_chunk.extend(block["paragraphs"])
            current_tokens += block_tokens

            if (block_idx + 1) % 25 == 0 or (block_idx + 1) == len(semantic_blocks):
                log.info(
                    "rag_chunk_progress",
                    document=document_name,
                    processed_blocks=block_idx + 1,
                    total_blocks=len(semantic_blocks),
                    last_start_idx=start_idx,
                    chunks_created=len(chunks),
                    progress_percent=round((block_idx + 1) / len(semantic_blocks) * 100, 1),
                )

        if current_chunk:
            chunk = self._create_chunk(
                parsed_doc=parsed_doc,
                current_chunk=current_chunk,
                metadata_extractor=metadata_extractor,
                document_name=document_name,
                documento_id=documento_id,
                sequence=chunk_sequence,
                total_paragraphs=total_paragraphs,
                start_idx=self._get_paragraph_index(parsed_doc, current_chunk[0]),
            )
            chunk, current_parent_chunk_id, current_parent_article = self._annotate_parent_child(
                chunk=chunk,
                current_parent_chunk_id=current_parent_chunk_id,
                current_parent_article=current_parent_article,
                children_by_parent=children_by_parent,
            )
            chunks.append(chunk)
            chunks_by_id[chunk.chunk_id] = chunk

        for parent_id, child_ids in children_by_parent.items():
            parent_chunk = chunks_by_id.get(parent_id)
            if parent_chunk is None:
                continue
            parent_chunk.metadados = parent_chunk.metadados.model_copy(
                update={"child_chunk_ids": child_ids}
            )

        log.info(
            "rag_chunk_progress",
            document=document_name,
            stage="completed",
            total_chunks=len(chunks),
            total_tokens=sum(c.token_count for c in chunks),
        )

        return chunks

    def _annotate_parent_child(
        self,
        *,
        chunk: Chunk,
        current_parent_chunk_id: str | None,
        current_parent_article: str | None,
        children_by_parent: dict[str, list[str]],
    ) -> tuple[Chunk, str | None, str | None]:
        """Mark parent-child relationships for legal chunking."""
        metadata = chunk.metadados
        content_type = metadata.content_type or metadata.tipo or "legal_text"

        if content_type == "exam_question":
            chunk.metadados = metadata.model_copy(
                update={"parent_chunk_id": None, "is_parent_chunk": False}
            )
            return chunk, current_parent_chunk_id, current_parent_article

        is_parent = bool(metadata.tipo == "artigo" or (metadata.artigo and metadata.inciso is None))
        if is_parent:
            chunk.metadados = metadata.model_copy(
                update={"is_parent_chunk": True, "parent_chunk_id": None}
            )
            return chunk, chunk.chunk_id, metadata.artigo

        if (
            current_parent_chunk_id
            and metadata.artigo
            and (not current_parent_article or metadata.artigo == current_parent_article)
        ):
            children_by_parent.setdefault(current_parent_chunk_id, []).append(chunk.chunk_id)
            chunk.metadados = metadata.model_copy(
                update={"parent_chunk_id": current_parent_chunk_id, "is_parent_chunk": False}
            )
            return chunk, current_parent_chunk_id, current_parent_article

        chunk.metadados = metadata.model_copy(update={"is_parent_chunk": False})
        return chunk, current_parent_chunk_id, current_parent_article

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
        chunk_text = "\n\n".join(p.get("text", "") for p in current_chunk)
        token_count = self._estimate_tokens(chunk_text)

        context = self._get_hierarchical_context(parsed_doc, start_idx, current_chunk[0])
        context["documento"] = document_name

        metadata = metadata_extractor.extract(chunk_text, context)
        effective_artigo = metadata.artigo or context.get("artigo")
        effective_paragrafo = metadata.paragrafo or context.get("paragrafo")
        effective_inciso = metadata.inciso or context.get("inciso")
        hierarchy_context = {
            **context,
            "artigo": effective_artigo,
            "paragrafo": effective_paragrafo,
            "inciso": effective_inciso,
        }
        metadata = metadata.model_copy(
            update={
                "artigo": effective_artigo,
                "paragrafo": effective_paragrafo,
                "inciso": effective_inciso,
                "tipo": context.get("tipo", metadata.tipo),
                "hierarquia_normativa": self._build_normative_hierarchy(hierarchy_context),
            }
        )

        end_idx = start_idx + len(current_chunk) - 1
        posicao_documento = (
            (start_idx + end_idx) / 2 / total_paragraphs if total_paragraphs > 0 else 0.0
        )

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

        for paragraph in reversed(previous_chunk):
            para_text = paragraph.get("text", "")
            para_tokens = self._estimate_tokens(para_text)

            if overlap_tokens + para_tokens > self._overlap_tokens:
                break

            overlap_chunk.insert(0, paragraph)
            overlap_tokens += para_tokens

        if not overlap_chunk and previous_chunk:
            last_paragraph = previous_chunk[-1]
            overlap_chunk = [last_paragraph]
            overlap_tokens = self._estimate_tokens(last_paragraph.get("text", ""))

        return overlap_chunk, overlap_tokens

    def _get_hierarchical_context(
        self,
        paragraphs: list[dict[str, Any]],
        current_idx: int,
        first_paragraph: dict[str, Any] | None = None,
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
        headings: dict[int, str] = {}
        artigo: str | None = None
        paragrafo: str | None = None
        inciso: str | None = None

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
            text = para.get("text", "")
            marker_type, marker_value = self._detect_legal_marker(text)
            if marker_type == "artigo" and not artigo:
                artigo = marker_value
            elif marker_type == "paragrafo" and not paragrafo:
                paragrafo = marker_value
            elif marker_type == "inciso" and not inciso:
                inciso = marker_value

        if 1 in headings:
            context["titulo"] = headings[1]
        if 2 in headings:
            context["capitulo"] = headings[2]
        if 3 in headings:
            context["secao"] = headings[3]

        if first_paragraph:
            first_marker_type, first_marker_value = self._detect_legal_marker(
                first_paragraph.get("text", "")
            )
            if first_marker_type == "artigo":
                artigo = first_marker_value
                paragrafo = None
                inciso = None
            elif first_marker_type == "paragrafo":
                paragrafo = first_marker_value
                inciso = None
            elif first_marker_type == "inciso":
                inciso = first_marker_value
            elif first_paragraph.get("is_heading"):
                first_marker_type = "heading"
            context["tipo"] = first_marker_type or "content"
        else:
            context["tipo"] = "content"

        if artigo:
            context["artigo"] = artigo
        if paragrafo:
            context["paragrafo"] = paragrafo
        if inciso:
            context["inciso"] = inciso

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
        return len(self._encoding.encode(text))

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

    def _build_semantic_blocks(self, paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group paragraphs by legal boundaries to avoid breaking inciso/§ bodies."""
        blocks: list[dict[str, Any]] = []
        current_block: list[dict[str, Any]] = []
        current_tokens = 0
        current_start_idx = 0
        current_kind = "content"

        for idx, paragraph in enumerate(paragraphs):
            text = paragraph.get("text", "")
            if not text:
                continue
            marker_type, _marker_value = self._detect_legal_marker(text)
            is_new_block = bool(current_block) and marker_type in {
                "heading",
                "artigo",
                "paragrafo",
                "inciso",
            }

            if is_new_block:
                blocks.append(
                    {
                        "paragraphs": current_block,
                        "token_count": current_tokens,
                        "start_idx": current_start_idx,
                        "kind": current_kind,
                    }
                )
                current_block = []
                current_tokens = 0
                current_start_idx = idx

            if not current_block:
                current_start_idx = idx
                current_kind = marker_type or "content"

            current_block.append(paragraph)
            current_tokens += self._estimate_tokens(text)

        if current_block:
            blocks.append(
                {
                    "paragraphs": current_block,
                    "token_count": current_tokens,
                    "start_idx": current_start_idx,
                    "kind": current_kind,
                }
            )

        return blocks

    def _detect_legal_marker(self, text: str) -> tuple[str, str | None]:
        """Detect legal structure marker at paragraph start."""
        stripped = text.strip()
        if not stripped:
            return "content", None

        artigo_match = self._ARTIGO_RE.match(stripped)
        if artigo_match:
            return "artigo", artigo_match.group(1)

        paragrafo_match = self._PARAGRAFO_RE.match(stripped)
        if paragrafo_match:
            value = paragrafo_match.group(1) or paragrafo_match.group(2)
            normalized = str(value).lower() if value else None
            return "paragrafo", normalized

        inciso_match = self._INCISO_RE.match(stripped)
        if inciso_match:
            return "inciso", inciso_match.group(1).upper()

        alinea_match = self._ALINEA_RE.match(stripped)
        if alinea_match:
            return "alinea", alinea_match.group(1).lower()

        return "content", None

    def _build_normative_hierarchy(self, context: dict[str, Any]) -> list[str]:
        """Build normalized hierarchy path for chunk metadata."""
        hierarchy: list[str] = []
        if context.get("titulo"):
            hierarchy.append(f"titulo:{context['titulo']}")
        if context.get("capitulo"):
            hierarchy.append(f"capitulo:{context['capitulo']}")
        if context.get("secao"):
            hierarchy.append(f"secao:{context['secao']}")
        if context.get("artigo"):
            hierarchy.append(f"artigo:{context['artigo']}")
        if context.get("paragrafo"):
            hierarchy.append(f"paragrafo:{context['paragrafo']}")
        if context.get("inciso"):
            hierarchy.append(f"inciso:{context['inciso']}")
        return hierarchy

    def _get_paragraph_index(
        self, paragraphs: list[dict[str, Any]], paragraph: dict[str, Any]
    ) -> int:
        """Resolve paragraph index preserving first-match semantics."""
        for idx, candidate in enumerate(paragraphs):
            if candidate is paragraph:
                return idx
        return 0

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
