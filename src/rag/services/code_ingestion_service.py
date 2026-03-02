"""Code ingestion service for RAG pipeline."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field
from sqlalchemy.exc import DatabaseError as SQLAlchemyDatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.log_events import LogEvents
from ..models import Chunk
from ..parser.code_chunker import CodeChunkExtractor
from ..parser.xml_parser import RepomixXMLParser
from ..utils.code_metadata_extractor import CodeMetadataExtractor
from .embedding_service import EmbeddingService
from .ingestion_service import IngestionError, IngestionService

log = structlog.get_logger(__name__)


# Cost calculation constants
OPENAI_EMBEDDING_COST_PER_1M_TOKENS = 0.02  # text-embedding-3-small


class DocumentResult(BaseModel):
    """Serializable document payload for ingestion responses."""

    id: int = Field(..., description="Document ID")
    nome: str = Field(..., description="Document name")
    arquivo_origem: str = Field(..., description="Source file path")
    content_hash: str | None = Field(default=None, description="SHA-256 document hash")
    chunk_count: int = Field(..., description="Number of chunks")
    token_count: int = Field(..., description="Total token count")


class CodeIngestionResult(BaseModel):
    """Result of codebase ingestion."""

    document: DocumentResult = Field(..., description="Document metadata")
    files_processed: int = Field(..., description="Number of files processed")
    chunks_created: int = Field(..., description="Number of chunks created")
    total_tokens: int = Field(..., description="Total token count")
    estimated_cost_usd: float = Field(..., description="Estimated embedding cost in USD")


class CodeIngestionService(IngestionService):
    """
    Ingestion service for code repositories.

    Implements the complete pipeline:
    RepomixXMLParser -> CodeMetadataExtractor -> CodeChunkExtractor
        -> EmbeddingService -> RagRepository -> Database
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
    ) -> None:
        """
        Initialize the code ingestion service.

        Args:
            session: SQLAlchemy async session for database operations
            embedding_service: EmbeddingService for generating embeddings
        """
        # Initialize parent class (reuses embedding_service)
        super().__init__(session, embedding_service)

        # Initialize code-specific extractors
        self._code_metadata_extractor = CodeMetadataExtractor()
        self._code_chunker = CodeChunkExtractor()

        log.debug(
            "rag_code_ingestion_service_initialized",
            event_name="rag_code_ingestion_service_initialized",
        )

    async def ingest_codebase(
        self,
        xml_file_path: str,
        document_name: str = "botsalinha-codebase",
    ) -> CodeIngestionResult:
        """
        Ingest a codebase through the complete RAG pipeline.

        Pipeline steps:
        1. Parse Repomix XML file with RepomixXMLParser
        2. Extract metadata with CodeMetadataExtractor
        3. Extract chunks with CodeChunkExtractor
        4. Generate embeddings with EmbeddingService
        5. Store DocumentORM and ChunkORM in database

        Args:
            xml_file_path: Path to the Repomix XML file
            document_name: Document identifier (e.g., 'botsalinha-codebase')

        Returns:
            CodeIngestionResult with document, statistics, and cost estimate

        Raises:
            IngestionError: If any step in the pipeline fails
        """
        log.info(
            LogEvents.AGENTE_INICIALIZADO,
            document=document_name,
            file_path=xml_file_path,
            stage="rag_code_ingestion_started",
            event_name="rag_code_ingestion_started",
        )

        try:
            # Step 1: Resolve target document by real XML content hash
            content_hash = self._compute_document_content_hash(xml_file_path)
            document_orm, is_unchanged = await self._resolve_document_for_ingestion(
                document_name=document_name,
                file_path=xml_file_path,
                content_hash=content_hash,
            )

            if is_unchanged:
                backfilled_chunks = await self._backfill_chunk_hashes(document_orm.id)
                await self._session.commit()
                await self._session.refresh(document_orm)
                log.info(
                    "rag_code_ingestion_progress",
                    document=document_name,
                    document_id=document_orm.id,
                    stage="skipped_unchanged",
                    backfilled_chunks=backfilled_chunks,
                    event_name="rag_code_ingestion_progress",
                )
                document = DocumentResult(
                    id=document_orm.id,
                    nome=document_orm.nome,
                    arquivo_origem=document_orm.arquivo_origem,
                    content_hash=document_orm.content_hash,
                    chunk_count=document_orm.chunk_count,
                    token_count=document_orm.token_count,
                )
                return CodeIngestionResult(
                    document=document,
                    files_processed=0,
                    chunks_created=document_orm.chunk_count,
                    total_tokens=document_orm.token_count,
                    estimated_cost_usd=0.0,
                )

            # Step 2: Parse the XML file
            parser = RepomixXMLParser(xml_file_path)
            parsed_files = await parser.parse()

            if not parsed_files:
                msg = f"Empty XML file: {xml_file_path}"
                log.error(
                    "rag_code_ingestion_error",
                    error=msg,
                    document=document_name,
                    event_name="rag_code_ingestion_error",
                )
                raise IngestionError(msg)

            log.info(
                "rag_code_ingestion_progress",
                document=document_name,
                stage="parsed",
                files_count=len(parsed_files),
                event_name="rag_code_ingestion_progress",
            )

            log.info(
                "rag_code_ingestion_progress",
                document=document_name,
                document_id=document_orm.id,
                stage="document_resolved",
                content_hash=content_hash,
                event_name="rag_code_ingestion_progress",
            )

            # Step 3: Extract chunks from all files
            chunks = await self._extract_chunks_from_files(
                parsed_files=parsed_files,
                document_name=document_name,
                documento_id=document_orm.id,
            )

            if not chunks:
                msg = f"No chunks extracted from codebase: {document_name}"
                log.error(
                    "rag_code_ingestion_error",
                    error=msg,
                    document=document_name,
                    event_name="rag_code_ingestion_error",
                )
                raise IngestionError(msg)

            log.info(
                "rag_code_ingestion_progress",
                document=document_name,
                stage="chunks_extracted",
                chunks_count=len(chunks),
                event_name="rag_code_ingestion_progress",
            )

            # Step 4: Incremental refresh with content hashes
            refresh_stats = await self._sync_document_chunks_incrementally(
                document_id=document_orm.id,
                chunks=chunks,
            )

            log.info(
                "rag_code_ingestion_progress",
                document=document_name,
                stage="embeddings_generated",
                chunks_embedded=refresh_stats["embedded_chunks"],
                chunks_reused=refresh_stats["reused_chunks"],
                chunks_backfilled=refresh_stats["backfilled_hashes"],
                event_name="rag_code_ingestion_progress",
            )

            # Step 5: Update document statistics
            self._update_document_stats(document_orm, chunks)

            # Commit transaction
            await self._session.commit()
            await self._session.refresh(document_orm)

            # Calculate cost estimate
            total_tokens = sum(chunk.token_count for chunk in chunks)
            estimated_cost = (total_tokens / 1_000_000) * OPENAI_EMBEDDING_COST_PER_1M_TOKENS

            log.info(
                LogEvents.AGENTE_RESPOSTA_GERADA,
                document=document_name,
                document_id=document_orm.id,
                files_processed=len(parsed_files),
                chunk_count=document_orm.chunk_count,
                token_count=document_orm.token_count,
                estimated_cost_usd=round(estimated_cost, 4),
                chunks_deleted=refresh_stats["deleted_chunks"],
                chunks_embedded=refresh_stats["embedded_chunks"],
                chunks_reused=refresh_stats["reused_chunks"],
                stage="rag_code_ingestion_completed",
                event_name="rag_code_ingestion_completed",
            )

            # Build result
            document = DocumentResult(
                id=document_orm.id,
                nome=document_orm.nome,
                arquivo_origem=document_orm.arquivo_origem,
                content_hash=document_orm.content_hash,
                chunk_count=document_orm.chunk_count,
                token_count=document_orm.token_count,
            )

            return CodeIngestionResult(
                document=document,
                files_processed=len(parsed_files),
                chunks_created=len(chunks),
                total_tokens=total_tokens,
                estimated_cost_usd=round(estimated_cost, 4),
            )

        except IngestionError:
            # Re-raise IngestionError as-is
            await self._session.rollback()
            raise

        except (ValueError, OSError, KeyError, SQLAlchemyDatabaseError) as e:
            # Wrap specific exceptions
            await self._session.rollback()
            msg = f"Failed to ingest codebase {document_name}: {e}"
            log.error(
                "rag_code_ingestion_error",
                error=msg,
                document=document_name,
                exception_type=type(e).__name__,
                event_name="rag_code_ingestion_error",
            )
            raise IngestionError(
                msg, details={"xml_file_path": xml_file_path, "document_name": document_name}
            ) from e

    async def _extract_chunks_from_files(
        self,
        parsed_files: list[dict[str, Any]],
        document_name: str,
        documento_id: int,
    ) -> list[Chunk]:
        """
        Extract chunks from parsed code files.

        For each file:
        1. Extract metadata using CodeMetadataExtractor
        2. Create chunks (one per file for now, can be enhanced)
        3. Generate unique chunk_id

        Args:
            parsed_files: List of file dicts from RepomixXMLParser
            document_name: Document identifier
            documento_id: Document ID for database reference

        Returns:
            List of Chunk objects
        """
        try:
            chunks = await self._code_chunker.extract_code_chunks(
                parsed_files=parsed_files,
                metadata_extractor=self._code_metadata_extractor,
                document_name=document_name,
                documento_id=documento_id,
            )
        except Exception as e:  # pragma: no cover - defensive guard
            msg = f"Failed to extract code chunks for {document_name}: {e}"
            log.error(
                "rag_code_ingestion_error",
                error=msg,
                document=document_name,
                exception_type=type(e).__name__,
                event_name="rag_code_ingestion_error",
            )
            raise IngestionError(msg) from e

        self._recompute_chunk_positions(chunks)
        return chunks

    @staticmethod
    def _recompute_chunk_positions(chunks: list[Chunk]) -> None:
        """Recompute chunk positions based on actual created chunks."""
        if not chunks:
            return
        denominator = max(len(chunks) - 1, 1)
        for index, chunk in enumerate(chunks):
            chunk.posicao_documento = index / denominator

    def _generate_code_chunk_id(self, document_name: str, file_path: str, seq: int) -> str:
        """
        Generate unique chunk identifier for code chunks.

        Format: {document_name}-{file_hash}-{short_uuid}-{sequence}

        Args:
            document_name: Document identifier
            file_path: Path to the file
            seq: Chunk sequence number

        Returns:
            Unique chunk ID string
        """
        # Sanitize document name
        safe_name = document_name.replace("/", "-").replace("\\", "-")
        safe_name = safe_name.replace(" ", "_").strip()
        file_hash = hashlib.sha256(file_path.encode("utf-8")).hexdigest()[:10]

        # Generate short UUID for uniqueness
        short_uuid = str(uuid4())[:8]

        return f"{safe_name}-{file_hash}-{short_uuid}-{seq:04d}"

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses parent class tokenizer if available, otherwise simple heuristic.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if hasattr(self, "_chunker") and self._chunker is not None:
            return self._chunker._estimate_tokens(text)
        # Rough estimate: ~4 characters per token
        return max(1, len(text) // 4)


__all__ = ["CodeIngestionService", "CodeIngestionResult", "DocumentResult"]
