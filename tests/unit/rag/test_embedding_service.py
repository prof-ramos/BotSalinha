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
@pytest.mark.parametrize(
    ("provider", "model_id"),
    [
        ("openai", "gpt-4o-mini"),
        ("google", "gemini-2.5-flash-lite"),
    ],
)
async def test_count_tokens_for_provider_model(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    model_id: str,
) -> None:
    """Token counting should be available for both OpenAI and Gemini strategies."""
    monkeypatch.setattr(
        "src.rag.services.embedding_service.EmbeddingService.get_generation_model_strategy",
        classmethod(lambda _cls: (provider, model_id)),
    )

    token_count = EmbeddingService.count_tokens_for_generation(
        "Art. 5º Todos são iguais perante a lei."
    )

    assert token_count > 0


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
async def test_embed_batch_splits_requests_when_token_estimate_is_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch embedding should split requests when token estimate exceeds limit."""
    service = EmbeddingService(api_key="test-key")

    async def fake_create(input: list[str], model: str) -> SimpleNamespace:  # noqa: A002
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(len(text))]) for text in input]
        )

    create_mock = AsyncMock(side_effect=fake_create)
    service._client = SimpleNamespace(embeddings=SimpleNamespace(create=create_mock))
    monkeypatch.setattr(
        "src.rag.services.embedding_service.EmbeddingService.count_tokens",
        classmethod(lambda _cls, text, provider, model=None: 150_000),
    )

    texts = ["a", "bb", "ccc"]
    embeddings = await service.embed_batch(texts)

    assert embeddings == [[1.0], [2.0], [3.0]]
    assert create_mock.await_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_text_splits_oversized_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Oversized single text should be split and recomposed."""
    service = EmbeddingService(api_key="test-key")

    async def fake_create_embedding(text: str) -> list[float]:
        return [1.0, 0.0] if text == "part-a" else [0.0, 1.0]

    def fake_count_tokens(_cls, text: str, provider: str, model: str | None = None) -> int:
        if text == "oversized":
            return 9_000
        if text == "part-a":
            return 100
        if text == "part-b":
            return 100
        return 0

    monkeypatch.setattr(service, "_create_embedding", AsyncMock(side_effect=fake_create_embedding))
    monkeypatch.setattr(
        service,
        "_split_text_by_token_limit",
        lambda text, max_tokens, overlap_tokens: ["part-a", "part-b"],
    )
    monkeypatch.setattr(
        "src.rag.services.embedding_service.EmbeddingService.count_tokens",
        classmethod(fake_count_tokens),
    )

    result = await service.embed_text("oversized")

    assert len(result) == 2
    assert pytest.approx(result[0], abs=1e-6) == 0.707106
    assert pytest.approx(result[1], abs=1e-6) == 0.707106


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_batch_handles_oversized_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch embedding should route oversized items through split embedding path."""
    service = EmbeddingService(api_key="test-key")

    async def fake_create(input: list[str], model: str) -> SimpleNamespace:  # noqa: A002
        return SimpleNamespace(data=[SimpleNamespace(embedding=[42.0]) for _ in input])

    create_mock = AsyncMock(side_effect=fake_create)
    service._client = SimpleNamespace(embeddings=SimpleNamespace(create=create_mock))

    monkeypatch.setattr(
        "src.rag.services.embedding_service.EmbeddingService.count_tokens",
        classmethod(
            lambda _cls, text, provider, model=None: (
                9_000 if text == "too-big" else (20 if text == "small" else 10)
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_embed_text_with_auto_split",
        AsyncMock(return_value=[7.0]),
    )

    result = await service.embed_batch(["small", "too-big"])

    assert result[0] == [42.0]
    assert result[1] == [7.0]
    create_mock.assert_awaited_once_with(input=["small"], model=service._model)
