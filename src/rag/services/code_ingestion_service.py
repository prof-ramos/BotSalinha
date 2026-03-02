"""Code ingestion service for RAG pipeline."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import DatabaseError as SQLAlchemyDatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.rag_models import ChunkORM, DocumentORM
from ...utils.log_events import LogEvents
from ..models import Chunk, ChunkMetadata
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

        # CodeChunkExtractor will be initialized when available
        # For now, we'll handle chunking inline
        self._code_chunker = None  # type: ignore

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
            # Step 1: Parse the XML file
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

            # Step 2: Get or create DocumentORM (dedupe by content_hash)
            content_hash = self._compute_document_content_hash(document_name, xml_file_path)
            stmt = select(DocumentORM).where(DocumentORM.content_hash == content_hash)
            result = await self._session.execute(stmt)
            document_orm = result.scalar_one_or_none()

            if document_orm is None:
                document_orm = self._create_document_orm(document_name, xml_file_path)
                self._session.add(document_orm)
                # Flush to get the ID before creating chunks
                await self._session.flush()
                document_stage = "document_created"
            else:
                # Deletar chunks antigos antes de reutilizar
                delete_stmt = delete(ChunkORM).where(ChunkORM.documento_id == document_orm.id)
                await self._session.execute(delete_stmt)
                await self._session.flush()
                document_stage = "document_reused"

            log.info(
                "rag_code_ingestion_progress",
                document=document_name,
                document_id=document_orm.id,
                stage=document_stage,
                content_hash=content_hash,
                event_name="rag_code_ingestion_progress",
            )

            # Step 3: Extract chunks from all files
            chunks = self._extract_chunks_from_files(
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

            # Step 4: Generate embeddings and create ChunkORMs
            chunk_texts = [chunk.texto for chunk in chunks]
            embeddings = await self._embedding_service.embed_batch(chunk_texts)

            for chunk, embedding in zip(chunks, embeddings, strict=True):
                chunk_orm = self._create_chunk_orm(chunk, embedding)
                self._session.add(chunk_orm)

            log.info(
                "rag_code_ingestion_progress",
                document=document_name,
                stage="embeddings_generated",
                embeddings_count=len(embeddings),
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

    def _extract_chunks_from_files(
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
        chunks: list[Chunk] = []
        chunk_sequence = 0

        for file_data in parsed_files:
            try:
                file_path = file_data.get("file_path", "")
                text = file_data.get("text", "")
                language = file_data.get("language", "unknown")

                if not text or not text.strip():
                    log.warning(
                        "rag_code_ingestion_empty_file",
                        file_path=file_path,
                        event_name="rag_code_ingestion_empty_file",
                    )
                    continue

                # Extract metadata using CodeMetadataExtractor
                context = {"file_path": file_path}
                code_metadata = self._code_metadata_extractor.extract_code_metadata(
                    text=text,
                    context=context,
                )

                # Create chunk metadata
                chunk_metadata = ChunkMetadata(
                    documento=document_name,
                    titulo=file_path,
                    tipo="code",
                    # Add code-specific fields to metadata
                    **code_metadata,
                )

                # Estimate token count
                token_count = self._estimate_tokens(text)

                # Generate unique chunk_id
                chunk_id = self._generate_code_chunk_id(document_name, file_path, chunk_sequence)

                # Create chunk
                chunk = Chunk(
                    chunk_id=chunk_id,
                    documento_id=documento_id,
                    texto=text,
                    metadados=chunk_metadata,
                    token_count=token_count,
                    posicao_documento=0.0,
                )

                chunks.append(chunk)
                chunk_sequence += 1

                log.debug(
                    "rag_code_chunk_created",
                    chunk_id=chunk_id,
                    file_path=file_path,
                    language=language,
                    token_count=token_count,
                )

            except Exception as e:
                # Continue processing other files on error
                log.error(
                    "rag_code_ingestion_file_error",
                    error=str(e),
                    file_path=file_data.get("file_path", "unknown"),
                    exception_type=type(e).__name__,
                    event_name="rag_code_ingestion_file_error",
                )
                continue

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
