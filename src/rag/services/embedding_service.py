"""Embedding service for text vectorization using OpenAI."""

from __future__ import annotations

import math
import re

import structlog
import tiktoken
from openai import AsyncOpenAI

from ...config.settings import get_settings
from ...config.yaml_config import yaml_config
from ...utils.errors import APIError
from ...utils.log_events import LogEvents
from ...utils.retry import async_retry_decorator

log = structlog.get_logger(__name__)

# OpenAI text-embedding-3-small dimension
EMBEDDING_DIM = 1536
MAX_EMBED_INPUT_TOKENS = 6000
EMBED_CHUNK_OVERLAP_TOKENS = 100


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

        provider, generation_model = self.get_generation_model_strategy()
        log.debug(
            "rag_embedding_service_initialized",
            model=self._model,
            generation_provider=provider,
            generation_model=generation_model,
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

        try:
            embedding = await self._embed_text_with_auto_split(text)
            token_count = self.count_tokens(text, provider="openai", model=self._model)

            log.info(
                "rag_embedding_created",
                model=self._model,
                token_count=token_count,
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
        token_counts_by_index = {
            i: self.count_tokens(text=t, provider="openai", model=self._model)
            for i, t in valid_texts
        }
        total_tokens = sum(token_counts_by_index.values())
        oversized_texts = [
            (idx, text)
            for idx, text in valid_texts
            if token_counts_by_index.get(idx, 0) > MAX_EMBED_INPUT_TOKENS
        ]
        regular_texts = [
            (idx, text)
            for idx, text in valid_texts
            if token_counts_by_index.get(idx, 0) <= MAX_EMBED_INPUT_TOKENS
        ]

        # OpenAI limit: 300000 tokens per request for text-embedding-3-small
        # Use 200000 as safe limit to account for estimation errors
        max_tokens_per_request = 200000  # noqa: N806

        try:
            embeddings: list[list[float]] = [[0.0] * EMBEDDING_DIM for _ in texts]
            if regular_texts:
                regular_total_tokens = sum(token_counts_by_index[idx] for idx, _ in regular_texts)
                indices, texts_to_embed = zip(*regular_texts, strict=True)

                if regular_total_tokens <= max_tokens_per_request:
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
                        total_tokens=regular_total_tokens,
                        total_texts=len(texts_to_embed),
                        batch_size_limit=max_tokens_per_request,
                        event_name="rag_embedding_batch_split",
                    )

                    # Process in chunks of tokens
                    current_batch_indices: list[int] = []
                    current_batch_texts: list[str] = []
                    current_batch_tokens = 0

                    for idx, text in zip(indices, texts_to_embed, strict=True):
                        text_tokens = token_counts_by_index[idx]

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

            for idx, text in oversized_texts:
                embeddings[idx] = await self._embed_text_with_auto_split(text)

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

    @classmethod
    def get_generation_model_strategy(cls) -> tuple[str, str]:
        """
        Resolve provider/model from runtime YAML config for prompt generation.
        """
        try:
            provider = (yaml_config.model.provider or "openai").strip().lower()
            model = (yaml_config.model.model_id or "gpt-4o-mini").strip()
            return provider, model
        except Exception:
            return "openai", "gpt-4o-mini"

    @classmethod
    def count_tokens(cls, text: str, provider: str, model: str | None = None) -> int:
        """
        Count tokens using strategy based on provider/model.

        OpenAI: uses tiktoken model encoding.
        Gemini/others: uses token-like lexical units (words + punctuation).
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return 0

        normalized_provider = (provider or "openai").strip().lower()
        model_name = (model or "").strip()

        if normalized_provider == "openai":
            return cls._count_tokens_openai(clean_text, model_name)

        return cls._count_tokens_lexical(clean_text)

    @classmethod
    def count_tokens_for_generation(cls, text: str) -> int:
        """
        Count tokens using configured generation provider/model.
        """
        provider, model = cls.get_generation_model_strategy()
        return cls.count_tokens(text=text, provider=provider, model=model)

    @staticmethod
    def _count_tokens_openai(text: str, model: str) -> int:
        """
        Count tokens with tiktoken using model-specific encoding.
        """
        try:
            if model:
                encoding = tiktoken.encoding_for_model(model)
            else:
                encoding = tiktoken.get_encoding("o200k_base")
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text))

    @staticmethod
    def _count_tokens_lexical(text: str) -> int:
        """
        Provider-agnostic fallback token count (words + punctuation units).
        """
        units = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        return len(units)

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

    async def _embed_text_with_auto_split(self, text: str) -> list[float]:
        """Embed a text, splitting oversized inputs and averaging child embeddings."""
        token_count = self.count_tokens(text, provider="openai", model=self._model)
        if token_count <= MAX_EMBED_INPUT_TOKENS:
            return await self._create_embedding(text)

        split_texts = self._split_text_by_token_limit(
            text=text,
            max_tokens=MAX_EMBED_INPUT_TOKENS,
            overlap_tokens=EMBED_CHUNK_OVERLAP_TOKENS,
        )

        log.info(
            "rag_embedding_text_split",
            original_tokens=token_count,
            split_parts=len(split_texts),
            max_input_tokens=MAX_EMBED_INPUT_TOKENS,
            event_name="rag_embedding_text_split",
        )

        weighted_embeddings: list[list[float]] = []
        weights: list[float] = []
        for split_text in split_texts:
            split_embedding = await self._create_embedding(split_text)
            weighted_embeddings.append(split_embedding)
            split_tokens = max(
                1,
                self.count_tokens(split_text, provider="openai", model=self._model),
            )
            weights.append(float(split_tokens))

        return self._weighted_average_embedding(weighted_embeddings, weights)

    def _split_text_by_token_limit(self, text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
        """Split text using token windows with overlap."""
        try:
            encoding = tiktoken.encoding_for_model(self._model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        token_ids = encoding.encode(text)
        if len(token_ids) <= max_tokens:
            return [text]

        stride = max(1, max_tokens - max(0, overlap_tokens))
        windows: list[str] = []
        start = 0
        while start < len(token_ids):
            end = min(start + max_tokens, len(token_ids))
            window_ids = token_ids[start:end]
            decoded = encoding.decode(window_ids).strip()
            if decoded:
                windows.append(decoded)
            if end >= len(token_ids):
                break
            start += stride

        return windows or [text]

    @staticmethod
    def _weighted_average_embedding(
        embeddings: list[list[float]],
        weights: list[float],
    ) -> list[float]:
        """Create a weighted and L2-normalized embedding centroid."""
        if not embeddings:
            return [0.0] * EMBEDDING_DIM

        if len(embeddings) != len(weights):
            msg = "embeddings and weights length mismatch"
            raise ValueError(msg)

        total_weight = sum(weights) or float(len(weights))
        aggregated = [0.0] * len(embeddings[0])

        for emb, weight in zip(embeddings, weights, strict=True):
            for i, value in enumerate(emb):
                aggregated[i] += value * (weight / total_weight)

        norm = math.sqrt(sum(value * value for value in aggregated))
        if norm > 0:
            aggregated = [value / norm for value in aggregated]

        return aggregated


__all__ = ["EmbeddingService", "EMBEDDING_DIM"]
