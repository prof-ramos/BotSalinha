"""Code chunking strategies for RAG."""

from __future__ import annotations

from typing import Any

import structlog

from src.rag.models import Chunk
from src.rag.parser.chunker import ChunkExtractor
from src.rag.utils.code_metadata_extractor import CodeMetadataExtractor

log = structlog.get_logger(__name__)


class CodeChunkExtractor(ChunkExtractor):
    """
    Chunk extractor for code files.

    Uses smaller chunks (default 300 tokens) and respects code boundaries
    like functions and classes. Tracks line numbers for source reference.
    """

    # Override defaults for code chunking
    DEFAULT_MAX_TOKENS = 300
    DEFAULT_MIN_CHUNK_SIZE = 50

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the code chunk extractor.

        Args:
            config: Optional configuration dict with keys:
                - max_tokens: Maximum tokens per chunk (default: 300)
                - overlap_tokens: Tokens to overlap between chunks (default: 50)
                - respect_boundaries: Respect natural boundaries (default: True)
                - min_chunk_size: Minimum chunk size in tokens (default: 50)
        """
        # Apply code-specific defaults
        if config is None:
            config = {}
        else:
            config = config.copy()  # Shallow copy to avoid mutating caller's dict

        # Ensure max_tokens and min_chunk_size use code defaults if not specified
        if "max_tokens" not in config:
            config["max_tokens"] = self.DEFAULT_MAX_TOKENS
        if "min_chunk_size" not in config:
            config["min_chunk_size"] = self.DEFAULT_MIN_CHUNK_SIZE

        super().__init__(config)

        log.debug(
            "rag_code_chunker_initialized",
            max_tokens=self._max_tokens,
            min_chunk_size=self._min_chunk_size,
            overlap_tokens=self._overlap_tokens,
        )

    async def extract_code_chunks(
        self,
        parsed_files: list[dict[str, Any]],
        metadata_extractor: CodeMetadataExtractor,
        document_name: str = "codebase",
        documento_id: int = 0,
    ) -> list[Chunk]:
        """
        Extract chunks from parsed code files.

        Processes each file separately, creating one chunk per file or splitting
        large files at function/class boundaries when possible.

        Args:
            parsed_files: List of file dicts from RepomixXMLParser with keys:
                - file_path: str (path to the file)
                - language: str (programming language)
                - text: str (code content)
                - line_start: int (starting line number)
                - line_end: int (ending line number)
            metadata_extractor: CodeMetadataExtractor instance for enrichment
            document_name: Document identifier (e.g., 'codebase')
            documento_id: Document ID for database reference

        Returns:
            List of Chunk objects with enriched metadata
        """
        if not parsed_files:
            log.warning("rag_code_chunker_empty_files", document=document_name)
            return []

        chunks: list[Chunk] = []
        chunk_sequence = 0
        total_files = len(parsed_files)

        log.info(
            "rag_code_chunk_progress",
            document=document_name,
            total_files=total_files,
            stage="started",
        )

        for file_idx, file_data in enumerate(parsed_files):
            file_path = file_data.get("file_path", "")
            text = file_data.get("text", "")
            line_start = file_data.get("line_start", 1)
            line_end = file_data.get("line_end", 1)

            if not text:
                log.debug("rag_code_chunker_empty_file", file_path=file_path)
                continue

            # Estimate tokens for the entire file
            file_tokens = self._estimate_tokens(text)

            # If file fits in one chunk, create single chunk
            if file_tokens <= self._max_tokens:
                chunk = self._create_code_chunk(
                    file_data=file_data,
                    text=text,
                    line_start=line_start,
                    line_end=line_end,
                    metadata_extractor=metadata_extractor,
                    document_name=document_name,
                    documento_id=documento_id,
                    sequence=chunk_sequence,
                )
                chunks.append(chunk)
                chunk_sequence += 1
            else:
                # Split large file into multiple chunks
                file_chunks = self._split_large_file(
                    file_data=file_data,
                    metadata_extractor=metadata_extractor,
                    document_name=document_name,
                    documento_id=documento_id,
                    start_sequence=chunk_sequence,
                )
                chunks.extend(file_chunks)
                chunk_sequence += len(file_chunks)

            # Log progress periodically
            if (file_idx + 1) % 50 == 0 or (file_idx + 1) == total_files:
                log.info(
                    "rag_code_chunk_progress",
                    document=document_name,
                    processed_files=file_idx + 1,
                    total_files=total_files,
                    chunks_created=len(chunks),
                    progress_percent=round((file_idx + 1) / total_files * 100, 1),
                )

        log.info(
            "rag_code_chunk_progress",
            document=document_name,
            stage="completed",
            total_chunks=len(chunks),
            total_tokens=sum(c.token_count for c in chunks),
        )

        return chunks

    def _create_code_chunk(
        self,
        file_data: dict[str, Any],
        text: str,
        line_start: int,
        line_end: int,
        metadata_extractor: CodeMetadataExtractor,
        document_name: str,
        documento_id: int,
        sequence: int,
    ) -> Chunk:
        """
        Create a Chunk from code text.

        Args:
            file_data: Original file data dict from parser
            text: Code text for this chunk
            line_start: Starting line number
            line_end: Ending line number
            metadata_extractor: CodeMetadataExtractor instance
            document_name: Document identifier
            documento_id: Document ID for database reference
            sequence: Chunk sequence number

        Returns:
            Chunk object with enriched metadata
        """
        file_path = file_data.get("file_path", "")
        language = file_data.get("language", "unknown")

        # Estimate token count
        token_count = self._estimate_tokens(text)

        # Build context for metadata extraction
        context = {
            "file_path": file_path,
            "language": language,
            "line_start": line_start,
            "line_end": line_end,
        }

        # Extract code metadata
        code_metadata = metadata_extractor.extract_code_metadata(text, context)

        # Build base metadata with document info
        metadata = {
            "documento": document_name,
            "file_path": file_path,
            "language": language,
            "line_start": line_start,
            "line_end": line_end,
            "functions": code_metadata.get("functions", []),
            "classes": code_metadata.get("classes", []),
            "layer": code_metadata.get("layer", "unknown"),
            "module": code_metadata.get("module", "unknown"),
            "is_test": code_metadata.get("is_test", False),
        }

        # Calculate position (simplified: use sequence-based estimation)
        posicao_documento = min(sequence * 0.01, 1.0)

        # Generate unique chunk_id
        chunk_id = self._generate_chunk_id(
            f"{document_name}-{file_path.replace('/', '-').replace('\\', '-')}", sequence
        )

        chunk = Chunk(
            chunk_id=chunk_id,
            documento_id=documento_id,
            texto=text,
            metadados=metadata,
            token_count=token_count,
            posicao_documento=round(posicao_documento, 4),
        )

        log.debug(
            "rag_code_chunk_created",
            chunk_id=chunk_id,
            file_path=file_path,
            language=language,
            sequence=sequence,
            token_count=token_count,
            line_start=line_start,
            line_end=line_end,
        )

        return chunk

    def _split_large_file(
        self,
        file_data: dict[str, Any],
        metadata_extractor: CodeMetadataExtractor,
        document_name: str,
        documento_id: int,
        start_sequence: int,
    ) -> list[Chunk]:
        """
        Split a large file into multiple chunks.

        Tries to split at function/class boundaries when possible.
        Falls back to line-based splitting if no clear boundaries exist.

        Args:
            file_data: Original file data dict from parser
            metadata_extractor: CodeMetadataExtractor instance
            document_name: Document identifier
            documento_id: Document ID for database reference
            start_sequence: Starting chunk sequence number

        Returns:
            List of Chunk objects
        """
        text = file_data.get("text", "")
        file_path = file_data.get("file_path", "")
        language = file_data.get("language", "unknown")

        chunks: list[Chunk] = []
        lines = text.split("\n")
        sequence = start_sequence

        # Try to split at code boundaries
        # For simplicity, we'll use line-based splitting with overlap
        # In a more sophisticated implementation, we could parse the AST
        # to find function/class boundaries

        current_chunk_lines: list[str] = []
        current_tokens = 0
        current_line_start = file_data.get("line_start", 1)

        for _line_idx, line in enumerate(lines):
            line_tokens = self._estimate_tokens(line)

            # Check if we should break
            if current_tokens + line_tokens > self._max_tokens and current_chunk_lines:
                # Create chunk from accumulated lines
                chunk_text = "\n".join(current_chunk_lines)
                line_end = current_line_start + len(current_chunk_lines) - 1

                chunk = self._create_code_chunk(
                    file_data=file_data,
                    text=chunk_text,
                    line_start=current_line_start,
                    line_end=line_end,
                    metadata_extractor=metadata_extractor,
                    document_name=document_name,
                    documento_id=documento_id,
                    sequence=sequence,
                )
                chunks.append(chunk)
                sequence += 1

                # Create overlap for next chunk
                overlap_lines = self._create_overlap_lines(current_chunk_lines)
                current_chunk_lines = overlap_lines
                current_tokens = sum(self._estimate_tokens(line) for line in overlap_lines)
                if overlap_lines:
                    current_line_start = line_end - len(overlap_lines) + 1
                else:
                    current_line_start = line_end + 1

            # Add line to current chunk
            current_chunk_lines.append(line)
            current_tokens += line_tokens

        # Don't forget the last chunk
        if current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            line_end = current_line_start + len(current_chunk_lines) - 1

            chunk = self._create_code_chunk(
                file_data=file_data,
                text=chunk_text,
                line_start=current_line_start,
                line_end=line_end,
                metadata_extractor=metadata_extractor,
                document_name=document_name,
                documento_id=documento_id,
                sequence=sequence,
            )
            chunks.append(chunk)

        log.debug(
            "rag_code_chunker_split_file",
            file_path=file_path,
            language=language,
            original_tokens=self._estimate_tokens(text),
            num_chunks=len(chunks),
        )

        return chunks

    def _create_overlap_lines(self, previous_lines: list[str]) -> list[str]:
        """
        Create overlap lines from previous chunk.

        Args:
            previous_lines: List of lines from previous chunk

        Returns:
            List of lines to include in overlap
        """
        if self._overlap_tokens <= 0:
            return []

        overlap_lines: list[str] = []
        overlap_tokens = 0

        # Add lines from end of previous chunk until we reach overlap_tokens
        for line in reversed(previous_lines):
            line_tokens = self._estimate_tokens(line)

            if overlap_tokens + line_tokens > self._overlap_tokens:
                break

            overlap_lines.insert(0, line)
            overlap_tokens += line_tokens

        return overlap_lines


__all__ = ["CodeChunkExtractor"]
