"""
Unit tests for metricas.utils module.
"""

import csv
from datetime import datetime
from pathlib import Path

import pytest

from metricas.utils import (
    configure_logging,
    get_logger,
    get_base_parser,
    save_results_csv,
    save_summary_csv,
    load_csv,
    read_csv_dict,
    escape_html,
    generate_html_table,
    format_duration,
    format_timestamp,
    calculate_stats,
    format_percentile,
    print_summary_box,
    print_progress,
    Timer,
)


class TestLogging:
    """Test logging utilities."""

    def test_configure_logging_default(self, caplog):
        """Test default logging configuration."""
        configure_logging(verbose=False, quiet=False)
        # Just verify it doesn't raise an exception

    def test_configure_logging_verbose(self):
        """Test verbose logging configuration."""
        configure_logging(verbose=True, quiet=False)
        # Just verify it doesn't raise an exception

    def test_configure_logging_quiet(self):
        """Test quiet logging configuration."""
        configure_logging(verbose=False, quiet=True)
        # Just verify it doesn't raise an exception

    def test_get_logger(self):
        """Test get_logger returns a logger."""
        logger = get_logger("test_logger")
        assert logger is not None
        assert logger.name == "test_logger"


class TestCli:
    """Test CLI utilities."""

    def test_get_base_parser(self):
        """Test base parser creation."""
        parser = get_base_parser("Test description")
        assert parser.description == "Test description"

        # Test default arguments
        args = parser.parse_args([])
        assert hasattr(args, "output")
        assert hasattr(args, "verbose")
        assert hasattr(args, "quiet")

    def test_parser_with_output(self):
        """Test parser with output argument."""
        parser = get_base_parser("Test")
        args = parser.parse_args(["-o", "test.csv"])
        assert args.output == "test.csv"

    def test_parser_with_verbose(self):
        """Test parser with verbose flag."""
        parser = get_base_parser("Test")
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_parser_with_quiet(self):
        """Test parser with quiet flag."""
        parser = get_base_parser("Test")
        args = parser.parse_args(["-q"])
        assert args.quiet is True


class TestCsvOperations:
    """Test CSV operation utilities."""

    def test_save_results_csv(self, tmp_path):
        """Test saving results to CSV."""
        output_path = tmp_path / "test_results.csv"
        results = [
            {"name": "test1", "value": "100"},
            {"name": "test2", "value": "200"},
        ]
        fieldnames = ["name", "value"]

        save_results_csv(output_path, results, fieldnames)

        assert output_path.exists()

        # Verify content
        with open(output_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["name"] == "test1"
            assert rows[0]["value"] == "100"

    def test_save_summary_csv(self, tmp_path):
        """Test saving summary to CSV."""
        output_path = tmp_path / "test.csv"
        summary_data = [
            {"metric": "total", "value": "100"},
            {"metric": "average", "value": "50.5"},
        ]

        save_summary_csv(output_path, summary_data)

        summary_path = tmp_path / "test_summary.csv"
        assert summary_path.exists()

        # Verify content
        with open(summary_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["metric"] == "total"

    def test_load_csv(self, tmp_path):
        """Test loading CSV as list of lists."""
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["col1", "col2"])
            writer.writerow(["val1", "val2"])

        rows = load_csv(csv_path)
        assert len(rows) == 2
        assert rows[0] == ["col1", "col2"]
        assert rows[1] == ["val1", "val2"]

    def test_load_csv_not_found(self, tmp_path):
        """Test load_csv raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            load_csv(tmp_path / "nonexistent.csv")

    def test_read_csv_dict(self, tmp_path):
        """Test loading CSV as list of dictionaries."""
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "value"])
            writer.writerow(["test1", "100"])
            writer.writerow(["test2", "200"])

        rows = read_csv_dict(csv_path)
        assert len(rows) == 2
        assert rows[0]["name"] == "test1"
        assert rows[0]["value"] == "100"


class TestHtmlOperations:
    """Test HTML operation utilities."""

    def test_escape_html(self):
        """Test HTML special character escaping."""
        assert escape_html("<div>") == "&lt;div&gt;"
        assert escape_html("&nbsp;") == "&amp;nbsp;"
        assert escape_html('"quoted"') == "&quot;quoted&quot;"
        assert escape_html("'apostrophe'") == "&#39;apostrophe&#39;"
        assert escape_html("normal") == "normal"

    def test_generate_html_table(self):
        """Test HTML table generation."""
        headers = ["Name", "Value"]
        rows = [
            {"Name": "Test1", "Value": "100"},
            {"Name": "Test2", "Value": "200"},
        ]

        html = generate_html_table(headers, rows)

        assert "<table>" in html
        assert "<th>Name</th>" in html
        assert "<th>Value</th>" in html
        assert "Test1" in html
        assert "100" in html

    def test_generate_html_table_max_rows(self):
        """Test HTML table generation with max_rows limit."""
        headers = ["Name"]
        rows = [{"Name": f"Test{i}"} for i in range(20)]

        html = generate_html_table(headers, rows, max_rows=10)

        # Should show 10 rows + "more" indicator
        assert "e mais 10 linhas" in html


class TestTimeOperations:
    """Test time and timing utilities."""

    def test_format_duration_ms(self):
        """Test formatting milliseconds."""
        assert format_duration(0.001) == "1.0ms"
        assert format_duration(0.5) == "500.0ms"

    def test_format_duration_seconds(self):
        """Test formatting seconds."""
        assert format_duration(1.0) == "1.0s"
        assert format_duration(45.5) == "45.5s"

    def test_format_duration_minutes(self):
        """Test formatting minutes."""
        assert "1m" in format_duration(60)
        assert "30s" in format_duration(90)

    def test_format_duration_hours(self):
        """Test formatting hours."""
        result = format_duration(3665)
        assert "1h" in result
        assert "1m" in result

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        result = format_timestamp()
        assert len(result) == 17  # YYYYMMDD_HHMMSS
        assert "_" in result

    def test_format_timestamp_custom(self):
        """Test timestamp formatting with custom datetime."""
        dt = datetime(2026, 2, 28, 12, 34, 56)
        result = format_timestamp(dt)
        assert result == "20260228_123456"


class TestStatistics:
    """Test statistics utilities."""

    def test_calculate_stats_basic(self):
        """Test basic statistics calculation."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = calculate_stats(values)

        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0

    def test_calculate_stats_empty(self):
        """Test statistics with empty list."""
        stats = calculate_stats([])
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0

    def test_calculate_stats_percentiles(self):
        """Test statistics with custom percentiles."""
        values = list(range(100))
        stats = calculate_stats(values, percentiles=[50, 90, 99])

        assert "p50" in stats
        assert "p90" in stats
        assert "p99" in stats

    def test_format_percentile(self):
        """Test percentile formatting."""
        assert format_percentile(0.123) == "0.123"
        assert format_percentile(12.3) == "12.30"
        assert format_percentile(123.45) == "123.5"
        assert format_percentile(1234.5, "ms") == "1234.5ms"


class TestDisplay:
    """Test display utilities."""

    def test_print_summary_box(self, capsys):
        """Test summary box printing."""
        metrics = [
            ("Label1", "Value1"),
            ("Label2", "Value2"),
        ]

        print_summary_box("TEST", metrics)

        captured = capsys.readouterr()
        assert "SUMÁRIO ESTATÍSTICO - TEST" in captured.out
        assert "Label1" in captured.out
        assert "Value1" in captured.out

    def test_print_summary_box_spacer(self, capsys):
        """Test summary box with spacer line."""
        metrics = [
            ("Spacer", None),
            ("Label", "Value"),
        ]

        print_summary_box("TEST", metrics)

        captured = capsys.readouterr()
        assert "Spacer" in captured.out
        assert "Label" in captured.out
