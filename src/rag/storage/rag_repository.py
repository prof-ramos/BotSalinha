"""
RAG repository for document metadata.

Implementação do repositório responsável pelo RAG.
"""

import json
from hashlib import sha256
from heapq import heappush, heapreplace
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...models.rag_models import ChunkORM, DocumentORM
from ...utils.errors import BotSalinhaError
from ..models import Chunk, Document

logger = structlog.get_logger(__name__)


class RagRepositoryError(BotSalinhaError):
    """Exception class for RagRepository errors."""

    pass


class RagRepository:
    """
    Repositório concreto para operações do RAG.

    Gerencia a persistência e recuparação de chunks e documentos de RAG,
    delegando chamadas de I/O para implementações correspondentes.
    """

    _SEARCH_BATCH_SIZE = 250

    def __init__(self, async_session_maker: async_sessionmaker[AsyncSession]) -> None:
        """
        Inicializa o RagRepository.

        Args:
            async_session_maker: SQLAlchemy async session factory.
        """
        self._async_session_maker = async_session_maker

    async def get_by_id(self, chunk_id: str) -> Chunk | None:
        """
        Busca um chunk pelo ID.

        Args:
            chunk_id: O identificador único do chunk.

        Returns:
            Chunk se encontrado, None caso contrário.
        """
        try:
            logger.debug("rag_repo_get_by_id", chunk_id=chunk_id)

            async with self._async_session_maker() as session:
                stmt = select(ChunkORM).where(ChunkORM.id == chunk_id)
                result = await session.execute(stmt)
                orm = result.scalar_one_or_none()

                if orm is None:
                    return None

                return self._orm_to_chunk(orm)

        except Exception as e:
            logger.error("rag_repo_get_by_id_error", chunk_id=chunk_id, error=str(e))
            raise RagRepositoryError(f"Erro ao buscar chunk pelo ID: {e}") from e

    async def save_chunk(self, chunk: Chunk, embedding: list[float]) -> Chunk:
        """
        Salva ou atualiza um chunk de RAG.

        Args:
            chunk: Dados do chunk.
            embedding: Vetor de embedding do chunk.

        Returns:
            O chunk salvo.
        """
        try:
            logger.debug("rag_repo_save_chunk", chunk_id=chunk.chunk_id)

            # Convert embedding to bytes (float32)
            embedding_bytes = self._serialize_embedding(embedding)

            # Convert metadata to JSON string
            metadata_json = chunk.metadados.model_dump_json()

            async with self._async_session_maker() as session:
                # Check if chunk exists
                stmt = select(ChunkORM).where(ChunkORM.id == chunk.chunk_id)
                result = await session.execute(stmt)
                existing_orm = result.scalar_one_or_none()

                if existing_orm:
                    # Update existing
                    existing_orm.documento_id = chunk.documento_id
                    existing_orm.texto = chunk.texto
                    existing_orm.metadados = metadata_json
                    existing_orm.token_count = chunk.token_count
                    existing_orm.embedding = embedding_bytes
                    orm = existing_orm
                else:
                    # Create new
                    orm = ChunkORM(
                        id=chunk.chunk_id,
                        documento_id=chunk.documento_id,
                        texto=chunk.texto,
                        metadados=metadata_json,
                        token_count=chunk.token_count,
                        embedding=embedding_bytes,
                    )
                    session.add(orm)

                await session.commit()
                await session.refresh(orm)

                return self._orm_to_chunk(orm)

        except Exception as e:
            logger.error("rag_repo_save_chunk_error", chunk_id=chunk.chunk_id, error=str(e))
            raise RagRepositoryError(f"Erro ao salvar chunk: {e}") from e

    async def save_document(self, document: Document) -> Document:
        """
        Salva ou atualiza um documento de RAG.

        Args:
            document: Dados do documento.

        Returns:
            O documento salvo.
        """
        try:
            content_hash = self._compute_document_content_hash(document)
            logger.debug(
                "rag_repo_save_document",
                document_id=document.id,
                content_hash=content_hash,
            )

            async with self._async_session_maker() as session:
                # Prefer hash-based deduplication first
                stmt = select(DocumentORM).where(DocumentORM.content_hash == content_hash)
                result = await session.execute(stmt)
                existing_hash_orm = result.scalar_one_or_none()

                if existing_hash_orm:
                    existing_hash_orm.nome = document.nome
                    existing_hash_orm.arquivo_origem = document.arquivo_origem
                    existing_hash_orm.chunk_count = document.chunk_count
                    existing_hash_orm.token_count = document.token_count
                    existing_hash_orm.content_hash = content_hash
                    orm = existing_hash_orm
                else:
                    # Backward compatibility: update by ID when hash did not match
                    stmt = select(DocumentORM).where(DocumentORM.id == document.id)
                    result = await session.execute(stmt)
                    existing_id_orm = result.scalar_one_or_none()

                    if existing_id_orm:
                        existing_id_orm.nome = document.nome
                        existing_id_orm.arquivo_origem = document.arquivo_origem
                        existing_id_orm.chunk_count = document.chunk_count
                        existing_id_orm.token_count = document.token_count
                        existing_id_orm.content_hash = content_hash
                        orm = existing_id_orm
                    else:
                        orm = DocumentORM(
                            id=document.id,
                            nome=document.nome,
                            arquivo_origem=document.arquivo_origem,
                            content_hash=content_hash,
                            chunk_count=document.chunk_count,
                            token_count=document.token_count,
                        )
                        session.add(orm)

                await session.commit()
                await session.refresh(orm)

                return self._orm_to_document(orm)

        except Exception as e:
            logger.error(
                "rag_repo_save_document_error",
                document_id=document.id,
                content_hash=self._compute_document_content_hash(document),
                error=str(e),
            )
            raise RagRepositoryError(f"Erro ao salvar documento: {e}") from e

    async def delete(self, chunk_id: str) -> bool:
        """
        Remove um chunk pelo ID.

        Args:
            chunk_id: ID do chunk.

        Returns:
            Verdadeiro se deletado com sucesso, falso se não encontrado.
        """
        try:
            logger.debug("rag_repo_delete", chunk_id=chunk_id)

            async with self._async_session_maker() as session:
                stmt = select(ChunkORM).where(ChunkORM.id == chunk_id)
                result = await session.execute(stmt)
                orm = result.scalar_one_or_none()

                if orm is None:
                    return False

                await session.delete(orm)
                await session.commit()

                return True

        except Exception as e:
            logger.error("rag_repo_delete_error", chunk_id=chunk_id, error=str(e))
            raise RagRepositoryError(f"Erro ao deletar chunk: {e}") from e

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Pesquisa chunks baseados em similaridade de embedding.

        Args:
            query_embedding: Vetor de embedding da query.
            limit: Limite de resultados.
            filters: Filtros opcionais (ex: {'documento': 'CF/88'}).

        Returns:
            Lista de tuplas (chunk, similaridade) ordenada por similaridade.
        """
        try:
            logger.debug("rag_repo_search", limit=limit, filters=filters)
            if limit <= 0:
                return []

            async with self._async_session_maker() as session:
                top_k_heap: list[tuple[float, int, ChunkORM]] = []
                offset = 0
                counter = 0

                while True:
                    stmt = (
                        select(ChunkORM)
                        .where(ChunkORM.embedding.isnot(None))
                        .order_by(ChunkORM.id)
                        .offset(offset)
                        .limit(self._SEARCH_BATCH_SIZE)
                    )
                    result = await session.execute(stmt)
                    orms = result.scalars().all()
                    if not orms:
                        break

                    for orm in orms:
                        # Apply filters if provided
                        if filters:
                            metadata = json.loads(orm.metadados)
                            if not all(metadata.get(k) == v for k, v in filters.items()):
                                continue

                        if not orm.embedding:
                            continue

                        chunk_embedding = self._deserialize_embedding(orm.embedding)
                        similarity = self._cosine_similarity(query_embedding, chunk_embedding)

                        # Keep only top-k with min-heap
                        heap_item = (similarity, counter, orm)
                        counter += 1
                        if len(top_k_heap) < limit:
                            heappush(top_k_heap, heap_item)
                        elif similarity > top_k_heap[0][0]:
                            heapreplace(top_k_heap, heap_item)

                    offset += self._SEARCH_BATCH_SIZE

                if not top_k_heap:
                    return []

                chunks_with_scores = sorted(top_k_heap, key=lambda item: item[0], reverse=True)
                return [(self._orm_to_chunk(orm), score) for score, _, orm in chunks_with_scores]

        except Exception as e:
            logger.error("rag_repo_search_error", error=str(e))
            raise RagRepositoryError(f"Erro ao pesquisar chunks: {e}") from e

    async def get_document_by_id(self, document_id: int) -> Document | None:
        """
        Busca um documento pelo ID.

        Args:
            document_id: ID do documento.

        Returns:
            Document se encontrado, None caso contrário.
        """
        try:
            logger.debug("rag_repo_get_document_by_id", document_id=document_id)

            async with self._async_session_maker() as session:
                stmt = select(DocumentORM).where(DocumentORM.id == document_id)
                result = await session.execute(stmt)
                orm = result.scalar_one_or_none()

                if orm is None:
                    return None

                return self._orm_to_document(orm)

        except Exception as e:
            logger.error(
                "rag_repo_get_document_by_id_error", document_id=document_id, error=str(e)
            )
            raise RagRepositoryError(f"Erro ao buscar documento pelo ID: {e}") from e

    async def get_document_by_name(self, name: str) -> Document | None:
        """
        Busca um documento pelo nome.

        Args:
            name: Nome do documento.

        Returns:
            Document se encontrado, None caso contrário.
        """
        try:
            logger.debug("rag_repo_get_document_by_name", name=name)

            async with self._async_session_maker() as session:
                stmt = select(DocumentORM).where(DocumentORM.nome == name)
                result = await session.execute(stmt)
                orm = result.scalar_one_or_none()

                if orm is None:
                    return None

                return self._orm_to_document(orm)

        except Exception as e:
            logger.error("rag_repo_get_document_by_name_error", name=name, error=str(e))
            raise RagRepositoryError(f"Erro ao buscar documento pelo nome: {e}") from e

    async def delete_document(self, document_id: int) -> bool:
        """
        Remove um documento pelo ID.

        Chunks associados são deletados em cascata pelo banco de dados.

        Args:
            document_id: ID do documento.

        Returns:
            Verdadeiro se deletado com sucesso, falso se não encontrado.
        """
        try:
            logger.debug("rag_repo_delete_document", document_id=document_id)

            async with self._async_session_maker() as session:
                stmt = select(DocumentORM).where(DocumentORM.id == document_id)
                result = await session.execute(stmt)
                orm = result.scalar_one_or_none()

                if orm is None:
                    return False

                await session.delete(orm)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                "rag_repo_delete_document_error", document_id=document_id, error=str(e)
            )
            raise RagRepositoryError(f"Erro ao deletar documento: {e}") from e

    async def list_documents(self) -> list[Document]:
        """
        Lista todos os documentos.

        Returns:
            Lista de todos os documentos ordenados por nome.
        """
        try:
            logger.debug("rag_repo_list_documents")

            async with self._async_session_maker() as session:
                stmt = select(DocumentORM).order_by(DocumentORM.nome)
                result = await session.execute(stmt)
                orms = result.scalars().all()

                return [self._orm_to_document(orm) for orm in orms]

        except Exception as e:
            logger.error("rag_repo_list_documents_error", error=str(e))
            raise RagRepositoryError(f"Erro ao listar documentos: {e}") from e

    # Helper methods

    @staticmethod
    def _serialize_embedding(embedding: list[float]) -> bytes:
        """Convert embedding list to bytes (float32)."""
        return np.array(embedding, dtype=np.float32).tobytes()

    @staticmethod
    def _deserialize_embedding(data: bytes) -> list[float]:
        """Convert bytes to embedding list (float32)."""
        return np.frombuffer(data, dtype=np.float32).tolist()

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a_arr = np.array(a, dtype=np.float32)
        b_arr = np.array(b, dtype=np.float32)

        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    @staticmethod
    def _orm_to_chunk(orm: ChunkORM) -> Chunk:
        """Convert ChunkORM to Chunk Pydantic model."""
        from ..models import ChunkMetadata

        metadata_dict = json.loads(orm.metadados)

        return Chunk(
            chunk_id=orm.id,
            documento_id=orm.documento_id,
            texto=orm.texto,
            metadados=ChunkMetadata(**metadata_dict),
            token_count=orm.token_count,
            posicao_documento=metadata_dict.get("posicao_documento", 0.0),
        )

    @staticmethod
    def _orm_to_document(orm: DocumentORM) -> Document:
        """Convert DocumentORM to Document Pydantic model."""
        return Document(
            id=orm.id,
            nome=orm.nome,
            arquivo_origem=orm.arquivo_origem,
            content_hash=orm.content_hash,
            chunk_count=orm.chunk_count,
            token_count=orm.token_count,
        )

    @staticmethod
    def _compute_document_content_hash(document: Document) -> str:
        """
        Compute deterministic SHA-256 hash for document deduplication.

        NOTE: We use metadata (name + path) instead of file content for hashing.
        This is semantically correct for RAG where the document name is the
        logical identifier, and maintains backward compatibility with existing
        migrations that compute hash the same way.
        """
        payload = f"{document.nome}|{document.arquivo_origem}".encode()
        return sha256(payload).hexdigest()
