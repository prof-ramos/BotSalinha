"""Métricas coletadas durante testes de carga RAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.rag.models import ConfiancaLevel


@dataclass
class QueryMetrics:
    """Métricas individuais de uma query."""

    query_id: str
    timestamp: float
    latency_ms: float
    success: bool
    error_message: str | None = None
    chunks_retrieved: int = 0
    min_similarity: float = 0.0
    max_similarity: float = 0.0
    avg_similarity: float = 0.0
    confidence: ConfiancaLevel = ConfiancaLevel.SEM_RAG
    user_id: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Exportar métricas para dict."""
        return {
            "query_id": self.query_id,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error_message": self.error_message,
            "chunks_retrieved": self.chunks_retrieved,
            "min_similarity": self.min_similarity,
            "max_similarity": self.max_similarity,
            "avg_similarity": self.avg_similarity,
            "confidence": self.confidence.value,
            "user_id": self.user_id,
        }


@dataclass
class LoadTestMetrics:
    """Métricas agregadas de um teste de carga."""

    test_name: str
    start_time: float
    end_time: float
    total_queries: int
    successful_queries: int
    failed_queries: int

    # Latência metrics (ms)
    avg_latency: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    min_latency: float = 0.0
    max_latency: float = 0.0

    # Throughput metrics
    queries_per_second: float = 0.0
    duration_seconds: float = 0.0

    # RAG-specific metrics
    min_similarity: float = 0.0
    avg_similarity: float = 0.0
    max_similarity: float = 0.0

    # Confidence distribution
    confidence_alta: int = 0
    confidence_media: int = 0
    confidence_baixa: int = 0
    confidence_sem_rag: int = 0

    # Chunk statistics
    avg_chunks_per_query: float = 0.0

    # Raw query metrics for detailed analysis
    query_metrics: list[QueryMetrics] = field(default_factory=list)

    # Error summary
    errors: dict[str, int] = field(default_factory=dict)

    @property
    def error_rate(self) -> float:
        """Taxa de erros como porcentagem."""
        if self.total_queries == 0:
            return 0.0
        return (self.failed_queries / self.total_queries) * 100

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso como porcentagem."""
        return 100.0 - self.error_rate

    @property
    def alta_confidence_rate(self) -> float:
        """Taxa de confiança ALTA como porcentagem."""
        if self.successful_queries == 0:
            return 0.0
        return (self.confidence_alta / self.successful_queries) * 100

    def to_dict(self) -> dict[str, Any]:
        """Exportar métricas agregadas para dict."""
        return {
            "test_name": self.test_name,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "failed_queries": self.failed_queries,
            "error_rate": round(self.error_rate, 2),
            "success_rate": round(self.success_rate, 2),
            # Latência
            "avg_latency_ms": round(self.avg_latency, 2),
            "p50_latency_ms": round(self.p50_latency, 2),
            "p95_latency_ms": round(self.p95_latency, 2),
            "p99_latency_ms": round(self.p99_latency, 2),
            "min_latency_ms": round(self.min_latency, 2),
            "max_latency_ms": round(self.max_latency, 2),
            # Throughput
            "queries_per_second": round(self.queries_per_second, 2),
            # Similaridade
            "min_similarity": round(self.min_similarity, 4),
            "avg_similarity": round(self.avg_similarity, 4),
            "max_similarity": round(self.max_similarity, 4),
            # Confiança
            "confidence_alta_count": self.confidence_alta,
            "confidence_media_count": self.confidence_media,
            "confidence_baixa_count": self.confidence_baixa,
            "confidence_sem_rag_count": self.confidence_sem_rag,
            "confidence_alta_rate": round(self.alta_confidence_rate, 2),
            # Chunks
            "avg_chunks_per_query": round(self.avg_chunks_per_query, 2),
            # Errors
            "errors": self.errors,
        }

    def to_csv_row(self) -> dict[str, Any]:
        """Exportar como linha CSV para relatórios agregados."""
        return {
            "test_name": self.test_name,
            "timestamp": datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "duration_s": round(self.duration_seconds, 2),
            "total_queries": self.total_queries,
            "success": self.successful_queries,
            "failed": self.failed_queries,
            "error_rate_pct": round(self.error_rate, 2),
            "qps": round(self.queries_per_second, 2),
            "avg_latency_ms": round(self.avg_latency, 2),
            "p95_latency_ms": round(self.p95_latency, 2),
            "p99_latency_ms": round(self.p99_latency, 2),
            "avg_similarity": round(self.avg_similarity, 4),
            "alta_confidence_pct": round(self.alta_confidence_rate, 2),
        }


@dataclass
class SystemMetrics:
    """Métricas do sistema durante teste de carga."""

    test_name: str
    timestamp: float
    memory_mb: float
    cpu_percent: float
    active_db_connections: int = 0
    rate_limit_hits: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Exportar para dict."""
        return {
            "test_name": self.test_name,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "memory_mb": round(self.memory_mb, 2),
            "cpu_percent": round(self.cpu_percent, 2),
            "active_db_connections": self.active_db_connections,
            "rate_limit_hits": self.rate_limit_hits,
        }


def calculate_percentiles(values: list[float], percentiles: list[float]) -> list[float]:
    """
    Calcular percentis de uma lista de valores.

    Args:
        values: Lista de valores
        percentiles: Lista de percentis para calcular (0-100)

    Returns:
        Lista de valores correspondentes aos percentis
    """
    if not values:
        return [0.0] * len(percentiles)

    sorted_values = sorted(values)
    n = len(sorted_values)

    result = []
    for p in percentiles:
        index = int((p / 100) * n)
        index = min(index, n - 1)
        result.append(sorted_values[index])

    return result


__all__ = [
    "QueryMetrics",
    "LoadTestMetrics",
    "SystemMetrics",
    "calculate_percentiles",
]
