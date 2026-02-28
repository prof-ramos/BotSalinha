"""Unit tests for Qdrant vector store backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.config.settings import get_settings
from src.rag.storage import get_vector_store
from src.rag.storage.qdrant_store import QdrantVectorStore
from src.rag.storage.vector_store import VectorStore


@pytest.mark.unit
def test_get_vector_store_defaults_to_sqlite() -> None:
    store = get_vector_store(AsyncMock())
    assert isinstance(store, VectorStore)


@pytest.mark.unit
def test_get_vector_store_qdrant(monkeypatch) -> None:
    monkeypatch.setenv("RAG__VECTOR_BACKEND", "qdrant")
    get_settings.cache_clear()

    store = get_vector_store(AsyncMock())
    assert isinstance(store, QdrantVectorStore)

    monkeypatch.delenv("RAG__VECTOR_BACKEND", raising=False)
    get_settings.cache_clear()


@pytest.mark.unit
def test_point_id_is_deterministic() -> None:
    point_1 = QdrantVectorStore._point_id("chunk-abc")
    point_2 = QdrantVectorStore._point_id("chunk-abc")
    point_3 = QdrantVectorStore._point_id("chunk-def")

    assert point_1 == point_2
    assert point_1 != point_3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_qdrant_search_applies_filters(monkeypatch) -> None:
    monkeypatch.setenv("RAG__VECTOR_BACKEND", "qdrant")
    get_settings.cache_clear()

    store = QdrantVectorStore()

    fake_response = {
        "status": "ok",
        "result": [
            {
                "score": 0.91,
                "payload": {
                    "chunk_id": "id-1",
                    "documento_id": 7,
                    "texto": "habeas corpus",
                    "token_count": 12,
                    "posicao_documento": 0.4,
                    "metadados": {"documento": "CF/88", "artigo": "5"},
                },
            },
            {
                "score": 0.88,
                "payload": {
                    "chunk_id": "id-2",
                    "documento_id": 8,
                    "texto": "outro",
                    "token_count": 8,
                    "posicao_documento": 0.2,
                    "metadados": {"documento": "Lei", "artigo": None},
                },
            },
        ],
    }

    with patch.object(store, "ensure_collection", new=AsyncMock()), patch.object(
        store, "_request", new=AsyncMock(return_value=fake_response)
    ):
        results = await store.search(
            query_embedding=[0.1, 0.2],
            limit=5,
            min_similarity=0.6,
            documento_id=7,
            filters={"artigo": "not_null"},
        )

    assert len(results) == 1
    assert results[0][0].chunk_id == "id-1"

    monkeypatch.delenv("RAG__VECTOR_BACKEND", raising=False)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_collection_creates_when_missing(monkeypatch) -> None:
    monkeypatch.setenv("RAG__VECTOR_BACKEND", "qdrant")
    get_settings.cache_clear()

    store = QdrantVectorStore()
    get_resp = Mock(status_code=404)

    async_client = AsyncMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = None
    async_client.get = AsyncMock(return_value=get_resp)

    with patch("src.rag.storage.qdrant_store.httpx.AsyncClient", return_value=async_client), patch.object(
        store, "_request", new=AsyncMock(return_value={"status": "ok"})
    ) as request_mock:
        await store.ensure_collection(vector_size=1536)

    request_mock.assert_awaited_once()

    monkeypatch.delenv("RAG__VECTOR_BACKEND", raising=False)
    get_settings.cache_clear()
