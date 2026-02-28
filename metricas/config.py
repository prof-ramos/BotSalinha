"""
Centralized configuration for BotSalinha metrics scripts.

This module provides a single source of truth for all metrics-related configuration,
reducing hardcoded values dispersed across multiple scripts.
"""

from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# PATHS
# ============================================================================

METRICS_DIR: Final[Path] = Path(__file__).parent
PROJECT_ROOT: Final[Path] = METRICS_DIR.parent

# Default output paths for each metric type
DEFAULT_OUTPUT_PATHS = {
    "access": METRICS_DIR / "performance_acesso.csv",
    "rag": METRICS_DIR / "performance_rag_componentes.csv",
    "quality": METRICS_DIR / "qualidade_rag.csv",
    "performance": METRICS_DIR / "performance_geral.csv",
}


# ============================================================================
# TIMEOUTS AND THRESHOLDS
# ============================================================================

SCRIPT_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes max per script
DEFAULT_RAG_MIN_SIMILARITY: Final[float] = 0.3
DEFAULT_RAG_SEARCH_LIMIT: Final[int] = 5


# ============================================================================
# DATABASE BENCHMARK DEFAULTS
# ============================================================================

DEFAULT_NUM_INSERTS: Final[int] = 50
DEFAULT_NUM_READS: Final[int] = 100


# ============================================================================
# DISPLAY LIMITS
# ============================================================================

TABLE_MAX_ROWS: Final[int] = 10
CHART_MAX_ENTRIES: Final[int] = 5


# ============================================================================
# METADATA
# ============================================================================

METRICS_METADATA = {
    "access": {
        "name": "Database Access Performance",
        "script": "gerar_performance_acesso.py",
        "output": "performance_acesso.csv",
        "description": "Database write/read operation latency",
    },
    "rag": {
        "name": "RAG Component Performance",
        "script": "gerar_performance_rag.py",
        "output": "performance_rag_componentes.csv",
        "description": "Embedding generation and vector search latency",
    },
    "quality": {
        "name": "RAG Quality Metrics",
        "script": "gerar_qualidade.py",
        "output": "qualidade_rag.csv",
        "description": "Semantic similarity and confidence distribution",
    },
    "performance": {
        "name": "End-to-End Performance",
        "script": "gerar_performance.py",
        "output": "performance_geral.csv",
        "description": "Full bot response generation latency including RAG",
    },
}


# ============================================================================
# PYDANTIC CONFIG CLASSES
# ============================================================================


class MetricsConfig(BaseModel):
    """
    Centralized configuration for metrics scripts.

    This class provides all configuration values used across metrics scripts,
    with validation via Pydantic.
    """

    # Output directory for all metrics files
    metrics_output_dir: Path = Field(
        default=METRICS_DIR,
        description="Directory where metrics CSV and HTML reports are saved",
    )

    # Timeout settings
    script_timeout_seconds: int = Field(
        default=SCRIPT_TIMEOUT_SECONDS,
        ge=1,
        le=3600,
        description="Maximum seconds to wait for a metric script to complete",
    )

    # RAG settings
    rag_min_similarity: float = Field(
        default=DEFAULT_RAG_MIN_SIMILARITY,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for RAG vector search",
    )
    rag_search_limit: int = Field(
        default=DEFAULT_RAG_SEARCH_LIMIT,
        ge=1,
        le=100,
        description="Maximum number of chunks to retrieve from RAG search",
    )

    # Database benchmark settings
    benchmark_num_inserts: int = Field(
        default=DEFAULT_NUM_INSERTS,
        ge=1,
        le=10000,
        description="Default number of insert operations for DB benchmarks",
    )
    benchmark_num_reads: int = Field(
        default=DEFAULT_NUM_READS,
        ge=1,
        le=10000,
        description="Default number of read operations for DB benchmarks",
    )

    # Display settings
    table_max_rows: int = Field(
        default=TABLE_MAX_ROWS,
        ge=1,
        le=1000,
        description="Maximum number of rows to display in HTML tables",
    )
    chart_max_entries: int = Field(
        default=CHART_MAX_ENTRIES,
        ge=1,
        le=100,
        description="Maximum number of entries to display in charts",
    )

    @field_validator("metrics_output_dir")
    @classmethod
    def ensure_directory_exists(cls, v: Path) -> Path:
        """Ensure the metrics output directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    def get_output_path(self, metric_type: str) -> Path:
        """
        Get the default output CSV path for a metric type.

        Args:
            metric_type: One of 'access', 'rag', 'quality', 'performance'

        Returns:
            Path to the default output CSV file

        Raises:
            ValueError: If metric_type is not recognized
        """
        if metric_type not in DEFAULT_OUTPUT_PATHS:
            raise ValueError(
                f"Unknown metric type: {metric_type}. "
                f"Valid types: {list(DEFAULT_OUTPUT_PATHS.keys())}"
            )
        return self.metrics_output_dir / DEFAULT_OUTPUT_PATHS[metric_type].name

    def get_metadata(self, metric_type: str) -> dict:
        """
        Get metadata for a metric type.

        Args:
            metric_type: One of 'access', 'rag', 'quality', 'performance'

        Returns:
            Dictionary with metric metadata (name, description, etc.)

        Raises:
            ValueError: If metric_type is not recognized
        """
        if metric_type not in METRICS_METADATA:
            raise ValueError(
                f"Unknown metric type: {metric_type}. "
                f"Valid types: {list(METRICS_METADATA.keys())}"
            )
        return METRICS_METADATA[metric_type].copy()


# Singleton instance
_config_instance: MetricsConfig | None = None


def get_metrics_config() -> MetricsConfig:
    """
    Get a cached MetricsConfig instance.

    This function ensures a singleton instance is reused across calls.

    Returns:
        MetricsConfig instance with all metrics configuration
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = MetricsConfig()
    return _config_instance
