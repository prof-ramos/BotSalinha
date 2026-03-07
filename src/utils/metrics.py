"""
Comprehensive metrics collection for BotSalinha observability.

Tracks:
- Provider performance (requests, latency, errors, token usage)
- RAG pipeline metrics (query latency, cache hit rates, vector store performance)
- Legal domain metrics (query types, confidence scores, metadata extraction)
- Discord bot metrics (commands, rate limits, health)

Uses prometheus_client for metrics exposition.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

import structlog

log = structlog.get_logger(__name__)

try:
    from prometheus_client import (
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    log.warning(
        "prometheus_client_not_installed",
        message="Install prometheus_client for metrics: uv add prometheus-client",
    )


# =============================================================================
# Provider Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # Request counters per provider
    provider_requests_total = Counter(
        "botsalinha_provider_requests_total",
        "Total AI provider requests",
        ["provider", "model", "status"],  # status: success, error, timeout
    )

    # Request latency histogram
    provider_request_duration_seconds = Histogram(
        "botsalinha_provider_request_duration_seconds",
        "AI provider request duration in seconds",
        ["provider", "model"],
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    )

    # Token usage
    provider_tokens_total = Counter(
        "botsalinha_provider_tokens_total",
        "Total tokens used",
        ["provider", "model", "token_type"],  # token_type: prompt, completion
    )

    # Estimated cost (USD)
    provider_cost_usd_total = Counter(
        "botsalinha_provider_cost_usd_total",
        "Total estimated cost in USD",
        ["provider", "model"],
    )

    # Active requests gauge
    provider_requests_active = Gauge(
        "botsalinha_provider_requests_active",
        "Currently active provider requests",
        ["provider", "model"],
    )


# =============================================================================
# RAG Pipeline Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # RAG query latency components
    rag_query_duration_seconds = Histogram(
        "botsalinha_rag_query_duration_seconds",
        "RAG query duration components",
        ["component"],  # component: embedding, vector_search, rerank, total
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    )

    # Cache hit rates
    rag_cache_hits_total = Counter(
        "botsalinha_rag_cache_hits_total",
        "RAG cache hits",
        ["cache_type"],  # cache_type: semantic, embedding
    )

    rag_cache_misses_total = Counter(
        "botsalinha_rag_cache_misses_total",
        "RAG cache misses",
        ["cache_type"],
    )

    # Vector store performance
    rag_vector_search_duration_seconds = Histogram(
        "botsalinha_rag_vector_search_duration_seconds",
        "Vector search duration",
        ["vector_store"],  # vector_store: sqlite, chroma, supabase
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    )

    # Document ingestion
    rag_documents_ingested_total = Counter(
        "botsalinha_rag_documents_ingested_total",
        "Total documents ingested into RAG",
        ["source_type", "status"],  # source_type: docx, xml, code; status: success, error
    )

    rag_chunks_created_total = Counter(
        "botsalinha_rag_chunks_created_total",
        "Total chunks created during ingestion",
        ["source_type"],
    )

    # RAG quality metrics
    rag_confidence_distribution = Counter(
        "botsalinha_rag_confidence_total",
        "RAG confidence level distribution",
        ["confidence"],  # confidence: alta, media, baixa, sem_rag
    )

    rag_similarity_score = Histogram(
        "botsalinha_rag_similarity_score",
        "RAG similarity scores",
        buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    )


# =============================================================================
# Legal Domain Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # Query type distribution
    legal_query_type_total = Counter(
        "botsalinha_legal_query_type_total",
        "Legal query type distribution",
        ["query_type"],  # query_type: artigo, jurisprudencia, concurso, geral, codigo
    )

    # Metadata extraction success
    legal_metadata_extraction_success_total = Counter(
        "botsalinha_legal_metadata_extraction_success_total",
        "Metadata extraction success rate",
        ["metadata_field", "status"],  # metadata_field: artigo, lei, banca; status: success, failed
    )

    # Normalization effectiveness
    legal_query_rewrite_total = Counter(
        "botsalinha_legal_query_rewrite_total",
        "Query rewrite operations",
        ["rewrite_type", "applied"],  # rewrite_type: legal_term, normalization; applied: true, false
    )


# =============================================================================
# Discord Bot Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # Command usage
    discord_commands_total = Counter(
        "botsalinha_discord_commands_total",
        "Discord command usage",
        ["command", "status"],  # command: ask, ping, ajuda; status: success, error
    )

    # Rate limiting
    discord_rate_limit_hits_total = Counter(
        "botsalinha_discord_rate_limit_hits_total",
        "Rate limit hits",
        ["scope"],  # scope: user, guild
    )

    # Bot health
    discord_bot_connected = Gauge(
        "botsalinha_discord_bot_connected",
        "Discord bot connection status (1=connected, 0=disconnected)",
    )

    discord_guild_count = Gauge(
        "botsalinha_discord_guild_count",
        "Number of guilds the bot is connected to",
    )

    discord_user_count = Gauge(
        "botsalinha_discord_user_count",
        "Total unique users seen",
    )


# =============================================================================
# System Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # E2E request latency
    system_request_duration_seconds = Histogram(
        "botsalinha_system_request_duration_seconds",
        "End-to-end request duration",
        ["request_type"],  # request_type: discord_command, rag_query, llm_generation
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    )

    # Error tracking
    system_errors_total = Counter(
        "botsalinha_system_errors_total",
        "System errors by type",
        ["error_type", "component"],  # error_type: APIError, ValidationError; component: agent, rag, discord
    )


# =============================================================================
# Metrics Decorators and Context Managers
# =============================================================================

@contextmanager
def track_provider_request(provider: str, model: str) -> Iterator[None]:
    """
    Context manager to track AI provider requests.

    Usage:
        with track_provider_request("openai", "gpt-4o-mini"):
            response = await openai_client.chat(...)
    """
    if not PROMETHEUS_AVAILABLE:
        yield
        return

    start_time = time.perf_counter()
    provider_requests_active.labels(provider=provider, model=model).inc()
    status = "success"

    try:
        yield
    except TimeoutError:
        status = "timeout"
        provider_requests_total.labels(provider=provider, model=model, status=status).inc()
        raise
    except Exception:
        status = "error"
        provider_requests_total.labels(provider=provider, model=model, status=status).inc()
        raise
    finally:
        duration = time.perf_counter() - start_time
        provider_requests_active.labels(provider=provider, model=model).dec()
        provider_request_duration_seconds.labels(provider=provider, model=model).observe(duration)
        if status == "success":
            provider_requests_total.labels(provider=provider, model=model, status=status).inc()


@contextmanager
def track_rag_query(component: str = "total") -> Iterator[None]:
    """
    Context manager to track RAG query components.

    Usage:
        with track_rag_query("embedding"):
            embedding = await embed_service.embed_text(...)
    """
    if not PROMETHEUS_AVAILABLE:
        yield
        return

    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        rag_query_duration_seconds.labels(component=component).observe(duration)


def track_cache_hit(cache_type: str) -> None:
    """
    Record a cache hit.

    Args:
        cache_type: Type of cache (semantic, embedding)
    """
    if PROMETHEUS_AVAILABLE:
        rag_cache_hits_total.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str) -> None:
    """
    Record a cache miss.

    Args:
        cache_type: Type of cache (semantic, embedding)
    """
    if PROMETHEUS_AVAILABLE:
        rag_cache_misses_total.labels(cache_type=cache_type).inc()


def track_confidence(confidence: str) -> None:
    """
    Record RAG confidence level.

    Args:
        confidence: Confidence level (alta, media, baixa, sem_rag)
    """
    if PROMETHEUS_AVAILABLE:
        rag_confidence_distribution.labels(confidence=confidence).inc()


def track_similarity(score: float) -> None:
    """
    Record RAG similarity score.

    Args:
        score: Similarity score (0.0 to 1.0)
    """
    if PROMETHEUS_AVAILABLE:
        rag_similarity_score.observe(score)


def track_legal_query_type(query_type: str) -> None:
    """
    Record legal query type.

    Args:
        query_type: Type of legal query (artigo, jurisprudencia, concurso, geral)
    """
    if PROMETHEUS_AVAILABLE:
        legal_query_type_total.labels(query_type=query_type).inc()


def track_discord_command(command: str, status: str = "success") -> None:
    """
    Record Discord command execution.

    Args:
        command: Command name (ask, ping, ajuda)
        status: Execution status (success, error)
    """
    if PROMETHEUS_AVAILABLE:
        discord_commands_total.labels(command=command, status=status).inc()


def track_error(error_type: str, component: str) -> None:
    """
    Record system error.

    Args:
        error_type: Type of error (APIError, ValidationError, etc.)
        component: Component where error occurred (agent, rag, discord)
    """
    if PROMETHEUS_AVAILABLE:
        system_errors_total.labels(error_type=error_type, component=component).inc()


def track_tokens(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """
    Record token usage.

    Args:
        provider: AI provider (openai, google)
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
    """
    if PROMETHEUS_AVAILABLE:
        provider_tokens_total.labels(provider=provider, model=model, token_type="prompt").inc(prompt_tokens)
        provider_tokens_total.labels(provider=provider, model=model, token_type="completion").inc(completion_tokens)

        # Rough cost estimation (update these prices periodically)
        cost_per_million = {
            "openai": {"gpt-4o-mini": {"prompt": 0.15, "completion": 0.60}},
            "google": {"gemini-2.5-flash-lite": {"prompt": 0.075, "completion": 0.30}},
        }

        if provider in cost_per_million and model in cost_per_million[provider]:
            prompt_cost = (prompt_tokens / 1_000_000) * cost_per_million[provider][model]["prompt"]
            completion_cost = (completion_tokens / 1_000_000) * cost_per_million[provider][model]["completion"]
            total_cost = prompt_cost + completion_cost
            provider_cost_usd_total.labels(provider=provider, model=model).inc(total_cost)


# =============================================================================
# Metrics Export
# =============================================================================

def get_metrics_text() -> str:
    """
    Get metrics in Prometheus text format.

    Returns:
        Metrics in Prometheus exposition format
    """
    if not PROMETHEUS_AVAILABLE:
        return "# Metrics unavailable: prometheus_client not installed\n"

    return generate_latest(REGISTRY).decode("utf-8")


def is_prometheus_available() -> bool:
    """Check if Prometheus metrics are available."""
    return PROMETHEUS_AVAILABLE


__all__ = [
    # Prometheus availability
    "is_prometheus_available",
    "get_metrics_text",
    # Provider metrics
    "track_provider_request",
    "track_tokens",
    # RAG metrics
    "track_rag_query",
    "track_cache_hit",
    "track_cache_miss",
    "track_confidence",
    "track_similarity",
    # Legal metrics
    "track_legal_query_type",
    # Discord metrics
    "track_discord_command",
    # Error tracking
    "track_error",
]
