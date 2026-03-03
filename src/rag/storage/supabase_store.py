"""Supabase pgvector store for dual-write and optional retrieval."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import get_settings
from ...utils.errors import APIError
from ..models import Chunk, ChunkMetadata

log = structlog.get_logger(__name__)


class SupabaseStore:
    """Supabase-backed vector store using RPC for pgvector search."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._client: Any | None = None

    def _is_enabled(self) -> bool:
        cfg = self._settings.rag.supabase
        return bool(cfg.enabled and cfg.url and cfg.service_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._is_enabled():
            raise APIError("Supabase backend is not configured.")

        try:
            from supabase import create_client  # type: ignore[import-untyped]
        except Exception as e:  # pragma: no cover - only when dependency missing
            raise APIError(f"Supabase dependency unavailable: {e}") from e

        self._client = create_client(
            self._settings.rag.supabase.url,
            self._settings.rag.supabase.service_key,
        )
        return self._client

    async def add_embeddings(self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> None:
        """Upsert chunks and embeddings to Supabase."""
        if not self._is_enabled() or not chunks_with_embeddings:
            return

        payload: list[dict[str, Any]] = []
        for chunk, embedding in chunks_with_embeddings:
            payload.append(
                {
                    "id": chunk.chunk_id,
                    "documento_id": chunk.documento_id,
                    "texto": chunk.texto,
                    "metadados": chunk.metadados.model_dump(),
                    "token_count": chunk.token_count,
                    "embedding": embedding,
                }
            )

        client = self._get_client()
        table_name = self._settings.rag.supabase.table_name
        try:
            await asyncio.to_thread(client.table(table_name).upsert(payload).execute)
            log.debug("supabase_dual_write_ok", count=len(payload), table_name=table_name)
        except Exception as e:
            raise APIError(f"Supabase upsert failed: {e}") from e

    async def search(
        self,
        query_embedding: list[float],
        query_text: str | None = None,  # kept for interface compatibility
        limit: int = 5,
        min_similarity: float = 0.6,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
        candidate_limit: int | None = None,  # kept for interface compatibility
    ) -> list[tuple[Chunk, float]]:
        """Search Supabase via RPC function backed by pgvector."""
        if not self._is_enabled():
            return []

        del query_text, candidate_limit  # interface parity

        client = self._get_client()
        fn_name = self._settings.rag.supabase.rpc_search_function
        rpc_payload: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_count": limit,
            "min_similarity": min_similarity,
            "metadata_filter": filters or {},
        }
        if documento_id is not None:
            rpc_payload["documento_id_filter"] = documento_id

        try:
            response = await asyncio.to_thread(client.rpc(fn_name, rpc_payload).execute)
            rows = getattr(response, "data", None) or []
        except Exception as e:
            raise APIError(f"Supabase RPC search failed: {e}") from e

        results: list[tuple[Chunk, float]] = []
        for row in rows:
            metadata_raw = row.get("metadados", {})
            if isinstance(metadata_raw, str):
                try:
                    metadata_raw = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    metadata_raw = {}
            metadata = ChunkMetadata.model_validate(metadata_raw or {})
            chunk = Chunk(
                chunk_id=str(row.get("id", "")),
                documento_id=int(row.get("documento_id", 0)),
                texto=str(row.get("texto", "")),
                metadados=metadata,
                token_count=int(row.get("token_count", 0)),
                posicao_documento=float(row.get("posicao_documento", 0.0)),
            )
            similarity = float(row.get("similarity", row.get("score", 0.0)))
            results.append((chunk, similarity))

        return results


__all__ = ["SupabaseStore"]
