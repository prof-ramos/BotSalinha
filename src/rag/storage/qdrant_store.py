"""Dedicated vector store backend using Qdrant via HTTP API."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
import structlog

from ...config.settings import get_settings
from ...utils.errors import APIError
from ...utils.log_events import LogEvents
from ..models import Chunk, ChunkMetadata

log = structlog.get_logger(__name__)


class QdrantVectorStore:
    """Vector store implementation backed by Qdrant."""

    def __init__(self) -> None:
        self._settings = get_settings().rag
        self._base_url = self._settings.qdrant_url.rstrip("/")
        self._collection = self._settings.qdrant_collection
        self._timeout = self._settings.qdrant_timeout_seconds
        self._api_key = self._settings.qdrant_api_key

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["api-key"] = self._api_key
        return headers

    @staticmethod
    def _point_id(chunk_id: str) -> int:
        """Convert arbitrary chunk_id string into deterministic uint64 id."""
        digest = hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()
        return int(digest[:16], 16)

    async def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._headers(),
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") not in (None, "ok"):
                raise APIError(f"Qdrant error on {path}: {data}")
            return data

    async def ensure_collection(self, vector_size: int) -> None:
        """Create collection if needed."""
        path = f"/collections/{self._collection}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            get_resp = await client.get(url=f"{self._base_url}{path}", headers=self._headers())
            if get_resp.status_code == 200:
                return
            if get_resp.status_code != 404:
                get_resp.raise_for_status()

        payload = {
            "vectors": {
                "size": vector_size,
                "distance": "Cosine",
            }
        }
        await self._request("PUT", path, payload)

    async def add_embeddings(
        self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]
    ) -> None:
        """Upsert embeddings and payload into Qdrant."""
        if not chunks_with_embeddings:
            return

        vector_size = len(chunks_with_embeddings[0][1])
        await self.ensure_collection(vector_size)

        points = []
        for chunk, embedding in chunks_with_embeddings:
            points.append(
                {
                    "id": self._point_id(chunk.chunk_id),
                    "vector": embedding,
                    "payload": {
                        "chunk_id": chunk.chunk_id,
                        "documento_id": chunk.documento_id,
                        "texto": chunk.texto,
                        "token_count": chunk.token_count,
                        "posicao_documento": chunk.posicao_documento,
                        "metadados": chunk.metadados.model_dump(),
                    },
                }
            )

        await self._request(
            "PUT",
            f"/collections/{self._collection}/points",
            {"points": points},
        )

        log.info(
            "rag_qdrant_upsert_success",
            count=len(points),
            collection=self._collection,
            event_name="rag_qdrant_upsert_success",
        )

    @staticmethod
    def _matches_filters(payload: dict[str, Any], filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True

        metadata = payload.get("metadados") or {}
        for key, expected in filters.items():
            value = metadata.get(key)
            if expected == "not_null":
                if value in (None, ""):
                    return False
            elif value != expected:
                return False
        return True

    @staticmethod
    def _to_chunk(payload: dict[str, Any]) -> Chunk:
        return Chunk(
            chunk_id=payload["chunk_id"],
            documento_id=int(payload["documento_id"]),
            texto=payload["texto"],
            metadados=ChunkMetadata(**(payload.get("metadados") or {})),
            token_count=int(payload.get("token_count", 0)),
            posicao_documento=float(payload.get("posicao_documento", 0.0)),
        )

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        min_similarity: float = 0.6,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Search chunks by vector similarity in Qdrant."""
        await self.ensure_collection(len(query_embedding))

        payload: dict[str, Any] = {
            "vector": query_embedding,
            "limit": max(limit * 5, 50),
            "with_payload": True,
        }

        response = await self._request(
            "POST",
            f"/collections/{self._collection}/points/search",
            payload,
        )

        results: list[tuple[Chunk, float]] = []
        for item in response.get("result", []):
            score = float(item.get("score", 0.0))
            if score < min_similarity:
                continue

            point_payload = item.get("payload") or {}
            if documento_id is not None and int(point_payload.get("documento_id", -1)) != documento_id:
                continue

            if not self._matches_filters(point_payload, filters):
                continue

            try:
                results.append((self._to_chunk(point_payload), score))
            except Exception as exc:
                log.warning(
                    "rag_qdrant_payload_invalid",
                    error=str(exc),
                    payload_keys=list(point_payload.keys()),
                )

            if len(results) >= limit:
                break

        log.info(
            LogEvents.RAG_BUSCA_CONCLUIDA,
            results_count=len(results),
            top_score=results[0][1] if results else 0,
            backend="qdrant",
            event_name="rag_qdrant_search_success",
        )

        return results

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        """Get chunk by logical chunk_id from Qdrant payload."""
        payload = {
            "filter": {
                "must": [{"key": "chunk_id", "match": {"value": chunk_id}}],
            },
            "limit": 1,
            "with_payload": True,
        }
        response = await self._request(
            "POST",
            f"/collections/{self._collection}/points/scroll",
            payload,
        )
        points = response.get("result", {}).get("points", [])
        if not points:
            return None

        point_payload = points[0].get("payload") or {}
        return self._to_chunk(point_payload)

    async def count_chunks(self, documento_id: int | None = None) -> int:
        """Count points in collection (optionally by document)."""
        payload: dict[str, Any] = {"exact": True}
        if documento_id is not None:
            payload["filter"] = {
                "must": [{"key": "documento_id", "match": {"value": documento_id}}]
            }

        response = await self._request(
            "POST",
            f"/collections/{self._collection}/points/count",
            payload,
        )
        result = response.get("result", {})
        return int(result.get("count", 0))
