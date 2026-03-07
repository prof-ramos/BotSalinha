"""Document ingestion service for RAG pipeline."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.rag_models import ChunkORM, ContentLinkORM, DocumentORM
from ...utils.errors import BotSalinhaError
from ...utils.log_events import LogEvents
from ..models import Chunk, Document
from ..parser.chunker import ChunkExtractor
from ..parser.docx_parser import DOCXParser
from ..storage.vector_store import serialize_embedding
from ..utils.metadata_extractor import MetadataExtractor
from .embedding_service import EMBEDDING_DIM, EmbeddingService

log = structlog.get_logger(__name__)

RAG_SCHEMA_VERSION = 3
RAG_METADATA_VERSION = 3
RAG_PARSER_VERSION = "docx_parser_v3"


class IngestionError(BotSalinhaError):
    """Error during document ingestion."""

    pass


class IngestionService:
    """
    Service for ingesting documents into the RAG system.

    Implements the complete pipeline:
    DOCXParser -> MetadataExtractor -> ChunkExtractor -> EmbeddingService -> Database
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
        1. Parse DOCX file with DOCXParser
        2. Extract metadata with MetadataExtractor
        3. Extract chunks with ChunkExtractor
        4. Generate embeddings with EmbeddingService
        5. Store DocumentORM and ChunkORM in database

        Args:
            file_path: Path to the DOCX file
            document_name: Document identifier (e.g., 'CF/88')

        Returns:
            Document Pydantic model with statistics

        Raises:
            IngestionError: If any step in the pipeline fails
        """
        log.info(
            LogEvents.AGENTE_INICIALIZADO,
            document=document_name,
            file_path=file_path,
            stage="rag_ingestion_started",
            event_name="rag_ingestion_started",
        )

        try:
            # Step 1: Resolve document by real file content hash
            document_content_hash = self._compute_document_content_hash(file_path)
            document_orm, is_unchanged = await self._resolve_document_for_ingestion(
                document_name=document_name,
                file_path=file_path,
                content_hash=document_content_hash,
            )

            if is_unchanged:
                backfilled_chunks = await self._backfill_chunk_hashes(document_orm.id)
                await self._session.commit()
                await self._session.refresh(document_orm)
                log.info(
                    "rag_ingestion_progress",
                    document=document_name,
                    document_id=document_orm.id,
                    stage="skipped_unchanged",
                    backfilled_chunks=backfilled_chunks,
                    event_name="rag_ingestion_progress",
                )
                return Document(
                    id=document_orm.id,
                    nome=document_orm.nome,
                    arquivo_origem=document_orm.arquivo_origem,
                    content_hash=document_orm.content_hash,
                    chunk_count=document_orm.chunk_count,
                    token_count=document_orm.token_count,
                )

            # Step 2: Parse the document
            parser = DOCXParser(file_path)
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

            log.info(
                "rag_ingestion_progress",
                document=document_name,
                document_id=document_orm.id,
                stage="document_resolved",
                content_hash=document_content_hash,
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

            # Step 4: Incremental refresh with chunk content hashes
            refresh_stats = await self._sync_document_chunks_incrementally(
                document_id=document_orm.id,
                chunks=chunks,
            )

            log.info(
                "rag_ingestion_progress",
                document=document_name,
                stage="embeddings_generated",
                chunks_embedded=refresh_stats["embedded_chunks"],
                chunks_reused=refresh_stats["reused_chunks"],
                event_name="rag_ingestion_progress",
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
                chunks_deleted=refresh_stats["deleted_chunks"],
                chunks_embedded=refresh_stats["embedded_chunks"],
                chunks_reused=refresh_stats["reused_chunks"],
                chunks_backfilled=refresh_stats["backfilled_hashes"],
                stage="rag_ingestion_completed",
                event_name="rag_ingestion_completed",
            )

            # Return Pydantic model
            return Document(
                id=document_orm.id,
                nome=document_orm.nome,
                arquivo_origem=document_orm.arquivo_origem,
                content_hash=document_orm.content_hash,
                chunk_count=document_orm.chunk_count,
                token_count=document_orm.token_count,
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

    async def _resolve_document_for_ingestion(
        self,
        document_name: str,
        file_path: str,
        content_hash: str,
    ) -> tuple[DocumentORM, bool]:
        """Resolve target document row for ingestion with legacy-safe deduplication."""
        by_hash_stmt = select(DocumentORM).where(DocumentORM.content_hash == content_hash)
        by_hash_result = await self._session.execute(by_hash_stmt)
        document_by_hash = by_hash_result.scalar_one_or_none()

        by_path_stmt = select(DocumentORM).where(DocumentORM.arquivo_origem == file_path)
        by_path_result = await self._session.execute(by_path_stmt)
        document_by_path = by_path_result.scalar_one_or_none()

        if document_by_hash is not None:
            if document_by_path is not None and document_by_path.id != document_by_hash.id:
                await self._session.delete(document_by_path)
                await self._session.flush()
            document_by_hash.nome = document_name
            document_by_hash.arquivo_origem = file_path
            document_by_hash.schema_version = RAG_SCHEMA_VERSION
            await self._session.flush()
            is_unchanged = (
                document_by_hash.chunk_count > 0
                and document_by_hash.schema_version == RAG_SCHEMA_VERSION
            )
            return document_by_hash, is_unchanged

        if document_by_path is not None:
            is_unchanged = (
                document_by_path.content_hash == content_hash
                and document_by_path.chunk_count > 0
                and document_by_path.schema_version == RAG_SCHEMA_VERSION
            )
            document_by_path.nome = document_name
            document_by_path.content_hash = content_hash
            document_by_path.schema_version = RAG_SCHEMA_VERSION
            await self._session.flush()
            return document_by_path, is_unchanged

        document_orm = self._create_document_orm(
            document_name=document_name,
            file_path=file_path,
            content_hash=content_hash,
        )
        self._session.add(document_orm)
        await self._session.flush()
        return document_orm, False

    async def _backfill_chunk_hashes(self, document_id: int) -> int:
        """Backfill legacy chunk hashes for unchanged documents."""
        stmt = select(ChunkORM).where(ChunkORM.documento_id == document_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        backfilled = 0
        for row in rows:
            if row.content_hash:
                continue
            row.content_hash = self._compute_chunk_content_hash(row.texto, row.metadados)
            backfilled += 1
        if backfilled > 0:
            await self._session.flush()
        return backfilled

    async def _sync_document_chunks_incrementally(
        self,
        document_id: int,
        chunks: list[Chunk],
    ) -> dict[str, int]:
        """
        Sync chunks idempotently, embedding only content-changed chunks.

        Strategy:
        - Build reusable embedding pool from existing chunk content hashes.
        - Backfill legacy rows with missing chunk hash.
        - Rebuild chunk rows for the document with deterministic hash metadata.
        """
        existing_stmt = select(ChunkORM).where(ChunkORM.documento_id == document_id)
        existing_chunks = (await self._session.execute(existing_stmt)).scalars().all()

        reusable_embeddings: dict[str, list[bytes | None]] = defaultdict(list)
        backfilled_hashes = 0
        for existing_chunk in existing_chunks:
            chunk_hash = existing_chunk.content_hash
            if not chunk_hash:
                chunk_hash = self._compute_chunk_content_hash(
                    existing_chunk.texto,
                    existing_chunk.metadados,
                )
                existing_chunk.content_hash = chunk_hash
                backfilled_hashes += 1
            reusable_embeddings[chunk_hash].append(existing_chunk.embedding)

        new_chunk_hashes: list[str] = []
        new_metadata_payloads: list[str] = []
        embedding_blobs: list[bytes | None] = [None] * len(chunks)
        pending_embed_indexes: list[int] = []
        pending_embed_texts: list[str] = []
        reused_chunks = 0

        for index, chunk in enumerate(chunks):
            metadata_dict = chunk.metadados.model_dump()
            metadata_dict["parser_version"] = RAG_PARSER_VERSION
            metadata_dict["schema_version"] = RAG_SCHEMA_VERSION
            embedding_model = getattr(
                self._embedding_service,
                "model",
                getattr(self._embedding_service, "_model", "unknown"),
            )
            metadata_dict["embedding_model"] = embedding_model
            metadata_payload = json.dumps(metadata_dict, ensure_ascii=False, sort_keys=True)
            chunk_hash = self._compute_chunk_content_hash(chunk.texto, metadata_payload)
            new_chunk_hashes.append(chunk_hash)
            new_metadata_payloads.append(metadata_payload)

            candidate_pool = reusable_embeddings.get(chunk_hash, [])
            reused_embedding = None
            while candidate_pool:
                candidate = candidate_pool.pop()
                if candidate is not None:
                    reused_embedding = candidate
                    break

            if reused_embedding is not None:
                embedding_blobs[index] = reused_embedding
                reused_chunks += 1
            else:
                pending_embed_indexes.append(index)
                pending_embed_texts.append(chunk.texto)

        if pending_embed_texts:
            generated_embeddings = await self._embedding_service.embed_batch(pending_embed_texts)
            for chunk_index, embedding in zip(
                pending_embed_indexes, generated_embeddings, strict=True
            ):
                if len(embedding) != EMBEDDING_DIM:
                    msg = (
                        f"Invalid embedding dimension: expected {EMBEDDING_DIM}, got {len(embedding)}"
                    )
                    raise ValueError(msg)
                embedding_blobs[chunk_index] = serialize_embedding(embedding)

        if existing_chunks:
            await self._session.execute(delete(ChunkORM).where(ChunkORM.documento_id == document_id))

        for chunk, metadata_payload, chunk_hash, embedding_blob in zip(
            chunks,
            new_metadata_payloads,
            new_chunk_hashes,
            embedding_blobs,
            strict=True,
        ):
            chunk_orm = self._create_chunk_orm_with_blob(
                chunk=chunk,
                metadados_json=metadata_payload,
                embedding_blob=embedding_blob,
                content_hash=chunk_hash,
            )
            self._session.add(chunk_orm)

        for link in self._build_content_links(chunks):
            self._session.add(link)

        await self._session.flush()
        return {
            "deleted_chunks": len(existing_chunks),
            "embedded_chunks": len(pending_embed_texts),
            "reused_chunks": reused_chunks,
            "backfilled_hashes": backfilled_hashes,
        }

    def _build_content_links(self, chunks: list[Chunk]) -> list[ContentLinkORM]:
        """Build explicit content links from parent-child metadata relationships."""
        chunk_ids = {chunk.chunk_id for chunk in chunks}
        links: list[ContentLinkORM] = []
        seen: set[tuple[str, str, str]] = set()

        for chunk in chunks:
            metadata = chunk.metadados
            parent_chunk_id = metadata.parent_chunk_id
            if not parent_chunk_id or parent_chunk_id not in chunk_ids:
                continue

            content_type = (metadata.content_type or metadata.tipo or "").lower()
            source_type = (metadata.source_type or "").lower()

            if content_type == "exam_question" or source_type == "exam_question":
                link_type = "charged_in"
            elif source_type == "emenda_constitucional" or bool(metadata.updated_by_law):
                link_type = "updates"
            else:
                link_type = "interprets"

            key = (parent_chunk_id, chunk.chunk_id, link_type)
            if key in seen:
                continue
            seen.add(key)
            links.append(
                ContentLinkORM(
                    article_chunk_id=parent_chunk_id,
                    linked_chunk_id=chunk.chunk_id,
                    link_type=link_type,
                )
            )

        return links

    def _create_document_orm(
        self,
        document_name: str,
        file_path: str,
        content_hash: str,
    ) -> DocumentORM:
        """
        Create a DocumentORM instance.

        Args:
            document_name: Document identifier
            file_path: Path to source file

        Returns:
            DocumentORM instance
        """
        return DocumentORM(
            nome=document_name,
            arquivo_origem=file_path,
            content_hash=content_hash,
            schema_version=RAG_SCHEMA_VERSION,
            chunk_count=0,
            token_count=0,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _compute_document_content_hash(file_path: str) -> str:
        """
        Compute deterministic SHA-256 hash from real file content.
        """
        payload = Path(file_path).read_bytes()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _compute_chunk_content_hash(text: str, metadata_json: str) -> str:
        """Compute deterministic SHA-256 hash from chunk text + metadata payload."""
        normalized = json.dumps(
            {"text": text, "metadata": json.loads(metadata_json)},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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

        metadados_json = chunk.metadados.model_dump_json()
        embedding_blob = serialize_embedding(embedding)
        content_hash = self._compute_chunk_content_hash(chunk.texto, metadados_json)
        return self._create_chunk_orm_with_blob(
            chunk=chunk,
            metadados_json=metadados_json,
            embedding_blob=embedding_blob,
            content_hash=content_hash,
        )

    def _create_chunk_orm_with_blob(
        self,
        chunk: Chunk,
        metadados_json: str,
        embedding_blob: bytes | None,
        content_hash: str,
    ) -> ChunkORM:
        """Create a chunk ORM row from pre-serialized payload."""
        return ChunkORM(
            id=chunk.chunk_id,
            documento_id=chunk.documento_id,
            texto=chunk.texto,
            metadados=metadados_json,
            content_hash=content_hash,
            metadata_version=RAG_METADATA_VERSION,
            token_count=chunk.token_count,
            embedding=embedding_blob,
            source_type=chunk.metadados.source_type,
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
        import time

        start_time = time.time()

        # Default to docs/plans/RAG/ if not specified
        if documents_dir is None:
            # Get project root (3 levels up from this file)
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent
            documents_dir = str(project_root / "docs" / "plans" / "RAG")

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
