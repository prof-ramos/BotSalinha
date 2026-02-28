"""Unit tests for EmbeddingService."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.rag.services.embedding_service import EMBEDDING_DIM, EmbeddingService


@pytest.mark.unit
def test_embedding_service_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service should fail fast when no API key is available."""
    fake_settings = SimpleNamespace(
        get_openai_api_key=lambda: None,
        rag=SimpleNamespace(embedding_model="text-embedding-3-small"),
    )
    monkeypatch.setattr("src.rag.services.embedding_service.get_settings", lambda: fake_settings)

    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        EmbeddingService()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_text_empty_returns_zero_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty text should return zero vector and skip OpenAI call."""
    service = EmbeddingService(api_key="test-key")
    create_embedding_mock = AsyncMock(return_value=[0.5] * EMBEDDING_DIM)
    monkeypatch.setattr(service, "_create_embedding", create_embedding_mock)

    result = await service.embed_text("   ")

    assert result == [0.0] * EMBEDDING_DIM
    create_embedding_mock.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_batch_preserves_positions_for_empty_texts() -> None:
    """Batch embedding should keep original order and fill empty entries with zeros."""
    service = EmbeddingService(api_key="test-key")

    async def fake_create(input: list[str], model: str) -> SimpleNamespace:  # noqa: A002
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(len(text))]) for text in input]
        )

    create_mock = AsyncMock(side_effect=fake_create)
    service._client = SimpleNamespace(embeddings=SimpleNamespace(create=create_mock))

    texts = ["alpha", "", "beta", "   "]
    embeddings = await service.embed_batch(texts)

    assert embeddings[0] == [5.0]
    assert embeddings[2] == [4.0]
    assert len(embeddings[1]) == EMBEDDING_DIM
    assert len(embeddings[3]) == EMBEDDING_DIM
    assert all(value == 0.0 for value in embeddings[1])
    assert all(value == 0.0 for value in embeddings[3])
    create_mock.assert_awaited_once_with(input=["alpha", "beta"], model=service._model)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_batch_splits_requests_when_token_estimate_is_high() -> None:
    """Batch embedding should split requests when token estimate exceeds limit."""
    service = EmbeddingService(api_key="test-key")

    async def fake_create(input: list[str], model: str) -> SimpleNamespace:  # noqa: A002
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(len(text))]) for text in input]
        )

    create_mock = AsyncMock(side_effect=fake_create)
    service._client = SimpleNamespace(embeddings=SimpleNamespace(create=create_mock))
    service._estimate_tokens = lambda _text: 150_000

    texts = ["a", "bb", "ccc"]
    embeddings = await service.embed_batch(texts)

    assert embeddings == [[1.0], [2.0], [3.0]]
    assert create_mock.await_count == 3
