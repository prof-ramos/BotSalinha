"""
Unit tests for metricas.config module.
"""

import pytest

from metricas.config import (
    METRICS_DIR,
    PROJECT_ROOT,
    SCRIPT_TIMEOUT_SECONDS,
    DEFAULT_RAG_MIN_SIMILARITY,
    DEFAULT_RAG_SEARCH_LIMIT,
    DEFAULT_NUM_INSERTS,
    DEFAULT_NUM_READS,
    TABLE_MAX_ROWS,
    CHART_MAX_ENTRIES,
    DEFAULT_OUTPUT_PATHS,
    METRICS_METADATA,
    MetricsConfig,
    get_metrics_config,
)


class TestConfigConstants:
    """Test configuration constants."""

    def test_metrics_dir_exists(self):
        """Test that METRICS_DIR points to a valid directory."""
        assert METRICS_DIR.exists()
        assert METRICS_DIR.is_dir()
        assert METRICS_DIR.name == "metricas"

    def test_project_root_exists(self):
        """Test that PROJECT_ROOT points to a valid directory."""
        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()

    def test_timeout_value(self):
        """Test that SCRIPT_TIMEOUT_SECONDS has a reasonable value."""
        assert SCRIPT_TIMEOUT_SECONDS == 300
        assert 60 <= SCRIPT_TIMEOUT_SECONDS <= 3600

    def test_rag_defaults(self):
        """Test RAG configuration defaults."""
        assert 0.0 <= DEFAULT_RAG_MIN_SIMILARITY <= 1.0
        assert DEFAULT_RAG_SEARCH_LIMIT == 5
        assert 1 <= DEFAULT_RAG_SEARCH_LIMIT <= 100

    def test_benchmark_defaults(self):
        """Test database benchmark defaults."""
        assert DEFAULT_NUM_INSERTS == 50
        assert DEFAULT_NUM_READS == 100
        assert 1 <= DEFAULT_NUM_INSERTS <= 10000
        assert 1 <= DEFAULT_NUM_READS <= 10000

    def test_display_limits(self):
        """Test display limit constants."""
        assert TABLE_MAX_ROWS == 10
        assert CHART_MAX_ENTRIES == 5
        assert 1 <= TABLE_MAX_ROWS <= 1000
        assert 1 <= CHART_MAX_ENTRIES <= 100


class TestOutputPaths:
    """Test default output paths configuration."""

    def test_output_paths_structure(self):
        """Test that DEFAULT_OUTPUT_PATHS has correct keys."""
        expected_keys = {"access", "rag", "quality", "performance"}
        assert set(DEFAULT_OUTPUT_PATHS.keys()) == expected_keys

    def test_output_paths_values(self):
        """Test that output paths have correct filenames."""
        assert DEFAULT_OUTPUT_PATHS["access"].name == "performance_acesso.csv"
        assert DEFAULT_OUTPUT_PATHS["rag"].name == "performance_rag_componentes.csv"
        assert DEFAULT_OUTPUT_PATHS["quality"].name == "qualidade_rag.csv"
        assert DEFAULT_OUTPUT_PATHS["performance"].name == "performance_geral.csv"


class TestMetadata:
    """Test metrics metadata configuration."""

    def test_metadata_keys(self):
        """Test that METRICS_METADATA has correct keys."""
        expected_keys = {"access", "rag", "quality", "performance"}
        assert set(METRICS_METADATA.keys()) == expected_keys

    def test_metadata_structure(self):
        """Test that each metric has required metadata fields."""
        required_fields = {"name", "script", "output", "description"}
        for metric_type, metadata in METRICS_METADATA.items():
            assert required_fields.issubset(metadata.keys()), f"{metric_type} missing fields"

    def test_access_metadata(self):
        """Test database access metadata."""
        metadata = METRICS_METADATA["access"]
        assert "Database Access Performance" in metadata["name"]
        assert "gerar_performance_acesso.py" in metadata["script"]

    def test_quality_metadata(self):
        """Test RAG quality metadata."""
        metadata = METRICS_METADATA["quality"]
        assert "RAG Quality" in metadata["name"]
        assert "gerar_qualidade.py" in metadata["script"]


class TestMetricsConfig:
    """Test MetricsConfig class."""

    def test_config_instantiation(self):
        """Test that MetricsConfig can be instantiated."""
        config = MetricsConfig()
        assert config is not None

    def test_config_defaults(self):
        """Test that MetricsConfig has correct default values."""
        config = MetricsConfig()
        assert config.script_timeout_seconds == SCRIPT_TIMEOUT_SECONDS
        assert config.rag_min_similarity == DEFAULT_RAG_MIN_SIMILARITY
        assert config.rag_search_limit == DEFAULT_RAG_SEARCH_LIMIT
        assert config.benchmark_num_inserts == DEFAULT_NUM_INSERTS
        assert config.benchmark_num_reads == DEFAULT_NUM_READS
        assert config.table_max_rows == TABLE_MAX_ROWS
        assert config.chart_max_entries == CHART_MAX_ENTRIES

    def test_config_validation(self):
        """Test that Pydantic validation works."""
        # Valid config
        config = MetricsConfig(
            script_timeout_seconds=600,
            rag_min_similarity=0.5,
            rag_search_limit=10,
        )
        assert config.script_timeout_seconds == 600
        assert config.rag_min_similarity == 0.5
        assert config.rag_search_limit == 10

        # Invalid config (out of range)
        with pytest.raises(ValueError):
            MetricsConfig(rag_min_similarity=2.0)  # Must be <= 1.0

        with pytest.raises(ValueError):
            MetricsConfig(rag_min_similarity=-0.1)  # Must be >= 0.0

    def test_get_output_path(self, tmp_path):
        """Test get_output_path method."""
        config = MetricsConfig(metrics_output_dir=tmp_path)

        access_path = config.get_output_path("access")
        assert access_path.parent == tmp_path
        assert access_path.name == "performance_acesso.csv"

        # Test invalid metric type
        with pytest.raises(ValueError, match="Unknown metric type"):
            config.get_output_path("invalid_type")

    def test_get_metadata(self):
        """Test get_metadata method."""
        config = MetricsConfig()

        metadata = config.get_metadata("quality")
        assert metadata["name"] == METRICS_METADATA["quality"]["name"]
        assert metadata["description"] == METRICS_METADATA["quality"]["description"]

        # Test invalid metric type
        with pytest.raises(ValueError, match="Unknown metric type"):
            config.get_metadata("invalid_type")


class TestSingleton:
    """Test get_metrics_config singleton pattern."""

    def test_singleton_returns_instance(self):
        """Test that get_metrics_config returns a MetricsConfig instance."""
        config = get_metrics_config()
        assert isinstance(config, MetricsConfig)

    def test_singleton_same_instance(self):
        """Test that get_metrics_config returns the same instance."""
        config1 = get_metrics_config()
        config2 = get_metrics_config()
        assert config1 is config2
