"""Document ingestion service for RAG pipeline."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import get_settings
from ...models.rag_models import ChunkORM, DocumentORM
from ...utils.errors import BotSalinhaError
from ...utils.log_events import LogEvents
from ..models import Chunk, Document
from ..parser.chunker import ChunkExtractor
from ..parser.docx_parser import DOCXParser
from ..parser.pdf_parser import PDFParser
from ..storage import get_vector_store
from ..storage.vector_store import serialize_embedding
from ..utils.metadata_extractor import MetadataExtractor
from .embedding_service import EMBEDDING_DIM, EmbeddingService

log = structlog.get_logger(__name__)


class IngestionError(BotSalinhaError):
    """Error during document ingestion."""

    pass


class DuplicateDocumentError(IngestionError):
    """Raised when a file with the same SHA-256 hash already exists in the DB.

    Attributes:
        existing_id:   ID of the already-indexed document.
        existing_nome: Name of the already-indexed document.
        file_hash:     SHA-256 hex digest of the duplicate file.
    """

    def __init__(self, existing_id: int, existing_nome: str, file_hash: str) -> None:
        super().__init__(
            f"Arquivo já indexado como '{existing_nome}' (id={existing_id}). "
            "Use !reindexar para recriar o índice ou envie um arquivo diferente.",
            details={
                "existing_id": existing_id,
                "existing_nome": existing_nome,
                "file_hash": file_hash,
            },
        )
        self.existing_id = existing_id
        self.existing_nome = existing_nome
        self.file_hash = file_hash


class IngestionService:
    """
    Service for ingesting documents into the RAG system.

    Implements the complete pipeline:
    Parser (DOCX/PDF) -> MetadataExtractor -> ChunkExtractor -> EmbeddingService -> Database
    """

    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService) -> None:
        """
        Initialize the ingestion service.

        Args:
            session: SQLAlchemy async session for database operations
            embedding_service: EmbeddingService for generating embeddings
        """
        self._session = session
        self._embedding_service = embedding_service
        self._metadata_extractor = MetadataExtractor()
        self._chunker = ChunkExtractor()

        log.debug(
            "rag_ingestion_service_initialized",
            event_name="rag_ingestion_service_initialized",
        )

    async def ingest_document(self, file_path: str, document_name: str) -> Document:
        """
        Ingest a document through the complete RAG pipeline.

        Pipeline steps:
        0. Compute SHA-256 hash and check for duplicates
        1. Parse document file with parser based on extension (.docx/.pdf)
        2. Extract metadata with MetadataExtractor
        3. Extract chunks with ChunkExtractor
        4. Generate embeddings with EmbeddingService
        5. Store DocumentORM and ChunkORM in database

        Args:
            file_path: Path to the input document (.docx or .pdf)
            document_name: Document identifier (e.g., 'CF/88')

        Returns:
            Document Pydantic model with statistics

        Raises:
            DuplicateDocumentError: If the file was already indexed (same SHA-256).
            IngestionError: If any other step in the pipeline fails.
        """
        log.info(
            LogEvents.AGENTE_INICIALIZADO,
            document=document_name,
            file_path=file_path,
            stage="rag_ingestion_started",
            event_name="rag_ingestion_started",
        )

        try:
            # Step 0: Deduplicate by file hash
            file_hash = self._compute_file_hash(file_path)
            existing = await self._find_by_hash(file_hash)
            if existing is not None:
                log.warning(
                    "rag_ingestion_duplicate",
                    file_hash=file_hash,
                    existing_id=existing.id,
                    existing_nome=existing.nome,
                    event_name="rag_ingestion_duplicate",
                )
                raise DuplicateDocumentError(
                    existing_id=existing.id,
                    existing_nome=existing.nome,
                    file_hash=file_hash,
                )

            # Step 1: Parse the document
            parser = self._get_parser(file_path)
            parsed_doc = parser.parse()

            if not parsed_doc:
                msg = f"Empty document: {file_path}"
                log.error(
                    "rag_ingestion_error",
                    error=msg,
                    document=document_name,
                    event_name="rag_ingestion_error",
                )
                raise IngestionError(msg)

            log.info(
                "rag_ingestion_progress",
                document=document_name,
                stage="parsed",
                paragraphs_count=len(parsed_doc),
                event_name="rag_ingestion_progress",
            )

            # Step 2: Create DocumentORM (first to get documento_id)
            document_orm = self._create_document_orm(document_name, file_path, file_hash)
            self._session.add(document_orm)

            # Flush to get the ID before creating chunks
            await self._session.flush()

            log.info(
                "rag_ingestion_progress",
                document=document_name,
                document_id=document_orm.id,
                stage="document_created",
                event_name="rag_ingestion_progress",
            )

            # Step 3: Extract chunks
            chunks = self._chunker.extract_chunks(
                parsed_doc=parsed_doc,
                metadata_extractor=self._metadata_extractor,
                document_name=document_name,
                documento_id=document_orm.id,
            )

            if not chunks:
                msg = f"No chunks extracted from document: {document_name}"
                log.error(
                    "rag_ingestion_error",
                    error=msg,
                    document=document_name,
                    event_name="rag_ingestion_error",
                )
                raise IngestionError(msg)

            log.info(
                "rag_ingestion_progress",
                document=document_name,
                stage="chunks_extracted",
                chunks_count=len(chunks),
                event_name="rag_ingestion_progress",
            )

            # Step 4: Generate embeddings and create ChunkORMs
            chunk_texts = [chunk.texto for chunk in chunks]
            embeddings = await self._embedding_service.embed_batch(chunk_texts)

            for chunk, embedding in zip(chunks, embeddings, strict=True):
                chunk_orm = self._create_chunk_orm(chunk, embedding)
                self._session.add(chunk_orm)

            log.info(
                "rag_ingestion_progress",
                document=document_name,
                stage="embeddings_generated",
                embeddings_count=len(embeddings),
                event_name="rag_ingestion_progress",
            )

            # Optional Step 4.1: Sync embeddings to dedicated vector DB
            if get_settings().rag.vector_backend == "qdrant":
                vector_store = get_vector_store(self._session)
                await vector_store.add_embeddings(
                    list(zip(chunks, embeddings, strict=True))
                )

            # Step 5: Update document statistics
            self._update_document_stats(document_orm, chunks)

            # Commit transaction
            await self._session.commit()
            await self._session.refresh(document_orm)

            log.info(
                LogEvents.AGENTE_RESPOSTA_GERADA,
                document=document_name,
                document_id=document_orm.id,
                chunk_count=document_orm.chunk_count,
                token_count=document_orm.token_count,
                stage="rag_ingestion_completed",
                event_name="rag_ingestion_completed",
            )

            # Return Pydantic model
            return Document(
                id=document_orm.id,
                nome=document_orm.nome,
                arquivo_origem=document_orm.arquivo_origem,
                chunk_count=document_orm.chunk_count,
                token_count=document_orm.token_count,
                file_hash=document_orm.file_hash,
            )

        except IngestionError:
            # Re-raise IngestionError as-is
            await self._session.rollback()
            raise

        except Exception as e:
            # Wrap other exceptions
            await self._session.rollback()
            msg = f"Failed to ingest document {document_name}: {e}"
            log.error(
                "rag_ingestion_error",
                error=msg,
                document=document_name,
                exception_type=type(e).__name__,
                event_name="rag_ingestion_error",
            )
            raise IngestionError(
                msg, details={"file_path": file_path, "document_name": document_name}
            ) from e


    @staticmethod
    def _get_parser(file_path: str) -> DOCXParser | PDFParser:
        """Return parser instance based on file extension."""
        suffix = Path(file_path).suffix.lower()
        if suffix == ".docx":
            return DOCXParser(file_path)
        if suffix == ".pdf":
            return PDFParser(file_path)

        raise IngestionError(
            f"Formato de arquivo não suportado: '{suffix}'. Use .docx ou .pdf.",
            details={"file_path": file_path, "suffix": suffix},
        )

    def _create_document_orm(
        self, document_name: str, file_path: str, file_hash: str | None = None
    ) -> DocumentORM:
        """
        Create a DocumentORM instance.

        Args:
            document_name: Document identifier
            file_path: Path to source file
            file_hash: SHA-256 hex digest (optional)

        Returns:
            DocumentORM instance
        """
        return DocumentORM(
            nome=document_name,
            arquivo_origem=file_path,
            chunk_count=0,
            token_count=0,
            file_hash=file_hash,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Return the SHA-256 hex digest of the file at *file_path*.

        Reads the file in 64 KiB chunks so large files don't exhaust memory.
        """
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
        except FileNotFoundError as exc:
            raise IngestionError(
                f"Arquivo não encontrado: {file_path}",
                details={"file_path": file_path},
            ) from exc
        return h.hexdigest()

    async def _find_by_hash(self, file_hash: str) -> DocumentORM | None:
        """Return the existing DocumentORM with *file_hash*, or None."""
        result = await self._session.execute(
            select(DocumentORM).where(DocumentORM.file_hash == file_hash).limit(1)
        )
        return result.scalar_one_or_none()

    def _create_chunk_orm(self, chunk: Chunk, embedding: list[float]) -> ChunkORM:
        """
        Create a ChunkORM instance.

        Args:
            chunk: Chunk Pydantic model
            embedding: Embedding vector

        Returns:
            ChunkORM instance

        Raises:
            ValueError: If embedding dimension is invalid
        """
        if len(embedding) != EMBEDDING_DIM:
            msg = f"Invalid embedding dimension: expected {EMBEDDING_DIM}, got {len(embedding)}"
            log.error(
                "rag_ingestion_error",
                error=msg,
                chunk_id=chunk.chunk_id,
                expected_dim=EMBEDDING_DIM,
                actual_dim=len(embedding),
                event_name="rag_ingestion_error",
            )
            raise ValueError(msg)

        # Serialize metadata to JSON
        metadados_json = chunk.metadados.model_dump_json()

        # Serialize embedding to bytes for storage
        embedding_blob = serialize_embedding(embedding)

        return ChunkORM(
            id=chunk.chunk_id,
            documento_id=chunk.documento_id,
            texto=chunk.texto,
            metadados=metadados_json,
            token_count=chunk.token_count,
            embedding=embedding_blob,
            created_at=datetime.now(UTC),
        )

    def _update_document_stats(self, document: DocumentORM, chunks: list[Chunk]) -> None:
        """
        Update document statistics after chunk processing.

        Args:
            document: DocumentORM instance to update
            chunks: List of processed chunks
        """
        document.chunk_count = len(chunks)
        document.token_count = sum(chunk.token_count for chunk in chunks)

        log.debug(
            "rag_ingestion_stats_updated",
            document_id=document.id,
            chunk_count=document.chunk_count,
            token_count=document.token_count,
            event_name="rag_ingestion_stats_updated",
        )

    async def reindex(
        self,
        documents_dir: str | None = None,
        pattern: str = "*.docx",
    ) -> dict[str, int | float]:
        """
        Rebuild the RAG index from scratch.

        Deletes all existing chunks and documents, then re-ingests all
        DOCX files from the specified directory.

        Args:
            documents_dir: Path to directory containing DOCX files.
                          Defaults to docs/plans/RAG/
            pattern: Glob pattern for matching files (default: "*.docx")

        Returns:
            Dictionary with statistics:
            - chunks_count: Total number of chunks created
            - documents_count: Total number of documents processed
            - duration_seconds: Time taken to complete reindexing
            - success: True if successful, False otherwise

        Raises:
            IngestionError: If reindexing fails
        """
        start_time = time.time()

        # Default to data/documents/ (project root / data / documents)
        if documents_dir is None:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent
            documents_dir = str(project_root / "data" / "documents")

        documents_path = Path(documents_dir)
        if not documents_path.exists():
            msg = f"Documents directory not found: {documents_dir}"
            log.error(
                "rag_reindex_error",
                error=msg,
                documents_dir=documents_dir,
                event_name="rag_reindex_error",
            )
            raise IngestionError(msg, details={"documents_dir": documents_dir})

        log.info(
            "rag_reindex_started",
            documents_dir=documents_dir,
            pattern=pattern,
            event_name="rag_reindex_started",
        )

        try:
            # Step 1: Delete all existing chunks and documents
            log.info(
                "rag_reindex_progress",
                stage="deleting_existing_data",
                event_name="rag_reindex_progress",
            )

            # Delete all chunks (cascades from documents)
            delete_chunks_stmt = delete(ChunkORM)
            await self._session.execute(delete_chunks_stmt)

            # Delete all documents
            delete_docs_stmt = delete(DocumentORM)
            await self._session.execute(delete_docs_stmt)

            await self._session.commit()

            log.info(
                "rag_reindex_progress",
                stage="existing_data_deleted",
                event_name="rag_reindex_progress",
            )

            # Step 2: Find all DOCX files
            docx_files = list(documents_path.glob(pattern))
            if not docx_files:
                msg = f"No DOCX files found in {documents_dir} with pattern {pattern}"
                log.warning(
                    "rag_reindex_warning",
                    warning=msg,
                    documents_dir=documents_dir,
                    pattern=pattern,
                    event_name="rag_reindex_warning",
                )
                return {
                    "chunks_count": 0,
                    "documents_count": 0,
                    "duration_seconds": 0.0,
                    "success": True,
                }

            log.info(
                "rag_reindex_progress",
                stage="files_found",
                files_count=len(docx_files),
                event_name="rag_reindex_progress",
            )

            # Step 3: Re-ingest each document
            total_chunks = 0
            successful_docs = 0

            for docx_file in docx_files:
                try:
                    # Use filename without extension as document name
                    doc_name = docx_file.stem

                    log.info(
                        "rag_reindex_progress",
                        stage="ingesting_document",
                        document=doc_name,
                        file_path=str(docx_file),
                        event_name="rag_reindex_progress",
                    )

                    document = await self.ingest_document(
                        file_path=str(docx_file),
                        document_name=doc_name,
                    )

                    total_chunks += document.chunk_count
                    successful_docs += 1

                    log.info(
                        "rag_reindex_progress",
                        stage="document_ingested",
                        document=doc_name,
                        chunk_count=document.chunk_count,
                        event_name="rag_reindex_progress",
                    )

                except Exception as e:
                    # Log error but continue with other documents
                    log.error(
                        "rag_reindex_error",
                        error=str(e),
                        document=str(docx_file),
                        exception_type=type(e).__name__,
                        event_name="rag_reindex_error",
                    )
                    continue

            duration = time.time() - start_time

            log.info(
                "rag_reindex_completed",
                documents_count=successful_docs,
                chunks_count=total_chunks,
                duration_seconds=duration,
                event_name="rag_reindex_completed",
            )

            return {
                "chunks_count": total_chunks,
                "documents_count": successful_docs,
                "duration_seconds": round(duration, 2),
                "success": True,
            }

        except Exception as e:
            await self._session.rollback()
            duration = time.time() - start_time
            msg = f"Reindexing failed: {e}"
            log.error(
                "rag_reindex_error",
                error=msg,
                exception_type=type(e).__name__,
                duration_seconds=duration,
                event_name="rag_reindex_error",
            )
            raise IngestionError(
                msg,
                details={
                    "documents_dir": documents_dir,
                    "pattern": pattern,
                    "duration_seconds": duration,
                },
            ) from e


__all__ = ["IngestionService", "IngestionError"]
