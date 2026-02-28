"""Embedding service for text vectorization using OpenAI."""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from ...config.settings import get_settings
from ...utils.errors import APIError
from ...utils.log_events import LogEvents
from ...utils.retry import async_retry_decorator

log = structlog.get_logger(__name__)

# OpenAI text-embedding-3-small dimension
EMBEDDING_DIM = 1536


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI API.

    Uses the text-embedding-3-small model by default, which provides
    a good balance of performance and cost for Brazilian legal text.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """
        Initialize the embedding service.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Embedding model name (defaults to settings.rag.embedding_model)
        """
        settings = get_settings()

        self._api_key = api_key or settings.get_openai_api_key()
        if not self._api_key:
            msg = "OpenAI API key not configured"
            log.error(LogEvents.API_ERRO_GERAR_RESPOSTA, error=msg)
            raise ValueError(msg)

        self._model = model or settings.rag.embedding_model
        self._client = AsyncOpenAI(api_key=self._api_key)

        log.debug(
            "rag_embedding_service_initialized",
            model=self._model,
            event_name="rag_embedding_service_initialized",
        )

    @async_retry_decorator(max_attempts=3, operation_name="embed_text")
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of float values representing the embedding vector

        Raises:
            APIError: If the embedding API call fails
        """
        if not text or not text.strip():
            log.warning(
                LogEvents.API_ERRO_GERAR_RESPOSTA, error="Empty text provided for embedding"
            )
            return [0.0] * EMBEDDING_DIM

        token_estimate = self._estimate_tokens(text)

        try:
            embedding = await self._create_embedding(text)

            log.info(
                "rag_embedding_created",
                model=self._model,
                token_estimate=token_estimate,
                embedding_dim=len(embedding),
                event_name="rag_embedding_created",
            )

            return embedding

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                model=self._model,
                text_length=len(text),
            )
            raise APIError(f"Failed to generate embedding: {e}") from e

    @async_retry_decorator(max_attempts=3, operation_name="embed_batch")
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input texts)

        Raises:
            APIError: If the embedding API call fails
        """
        if not texts:
            log.warning(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error="Empty text list provided for batch embedding",
            )
            return []

        # Filter out empty texts but preserve indices
        valid_texts = [(i, t) for i, t in enumerate(texts) if t and t.strip()]

        if not valid_texts:
            return [[0.0] * EMBEDDING_DIM for _ in texts]

        # Estimate total tokens
        total_tokens = sum(self._estimate_tokens(t) for _, t in valid_texts)

        # OpenAI limit: 300000 tokens per request for text-embedding-3-small
        # Use 200000 as safe limit to account for estimation errors
        max_tokens_per_request = 200000  # noqa: N806

        try:
            # Create embeddings for all valid texts (with batching if needed)
            indices, texts_to_embed = zip(*valid_texts, strict=True)
            embeddings: list[list[float]] = [[0.0] * EMBEDDING_DIM for _ in texts]

            if total_tokens <= max_tokens_per_request:
                # Single request
                response = await self._client.embeddings.create(
                    input=list(texts_to_embed),
                    model=self._model,
                )

                for idx, embedding_obj in zip(indices, response.data, strict=True):
                    embeddings[idx] = embedding_obj.embedding
            else:
                # Split into multiple batches
                log.info(
                    "rag_embedding_batch_split",
                    total_tokens=total_tokens,
                    total_texts=len(texts_to_embed),
                    batch_size_limit=max_tokens_per_request,
                    event_name="rag_embedding_batch_split",
                )

                # Process in chunks of tokens
                current_batch_indices: list[int] = []
                current_batch_texts: list[str] = []
                current_batch_tokens = 0

                for idx, text in zip(indices, texts_to_embed, strict=True):
                    text_tokens = self._estimate_tokens(text)

                    # Check if adding this text would exceed limit
                    if (
                        current_batch_texts
                        and current_batch_tokens + text_tokens > max_tokens_per_request
                    ):
                        # Process current batch
                        response = await self._client.embeddings.create(
                            input=current_batch_texts,
                            model=self._model,
                        )
                        for batch_idx, embedding_obj in zip(
                            current_batch_indices, response.data, strict=True
                        ):
                            embeddings[batch_idx] = embedding_obj.embedding

                        # Start new batch
                        current_batch_indices = [idx]
                        current_batch_texts = [text]
                        current_batch_tokens = text_tokens
                    else:
                        # Add to current batch
                        current_batch_indices.append(idx)
                        current_batch_texts.append(text)
                        current_batch_tokens += text_tokens

                # Process final batch
                if current_batch_texts:
                    response = await self._client.embeddings.create(
                        input=current_batch_texts,
                        model=self._model,
                    )
                    for batch_idx, embedding_obj in zip(
                        current_batch_indices, response.data, strict=True
                    ):
                        embeddings[batch_idx] = embedding_obj.embedding

            log.info(
                "rag_embedding_batch",
                model=self._model,
                total_texts=len(texts),
                valid_texts=len(valid_texts),
                token_estimate=total_tokens,
                event_name="rag_embedding_batch",
            )

            return embeddings

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                model=self._model,
                texts_count=len(texts),
            )
            raise APIError(f"Failed to generate batch embeddings: {e}") from e

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (approximately 4 characters per token).

        This is a rough estimate suitable for Brazilian Portuguese text.
        For accurate counting, use tiktoken library.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token for Portuguese
        return max(1, len(text) // 4)

    async def _create_embedding(self, text: str) -> list[float]:
        """
        Call OpenAI API to create embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: If the API call fails
        """
        response = await self._client.embeddings.create(
            input=text,
            model=self._model,
        )

        return response.data[0].embedding


__all__ = ["EmbeddingService", "EMBEDDING_DIM"]
