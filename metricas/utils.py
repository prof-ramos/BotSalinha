"""
Common utilities for metrics scripts in BotSalinha.

This module provides utility functions organized by category:
- Logging: configure_logging, get_logger
- CLI: get_base_parser
- CSV: save_results_csv, save_summary_csv, load_csv, read_csv_dict
- HTML: escape_html, generate_html_table
- Time: format_duration, format_timestamp, Timer context manager
- Stats: calculate_stats, format_percentile
- Display: print_summary_box, print_progress
"""

import argparse
import csv
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# Type aliases for better readability
CsvRow = dict[str, Any]
CsvData = list[CsvRow]
MetricTuple = tuple[str, Any] | tuple[str, Any, Any]

log = structlog.get_logger(__name__)


# ============================================================================
# LOGGING
# ============================================================================


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Configure logging level based on verbosity flags.

    Args:
        verbose: Enable DEBUG level logging
        quiet: Suppress INFO and DEBUG logs, show only ERROR
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (defaults to caller's module name)

    Returns:
        Configured structlog bound logger
    """
    return structlog.get_logger(name or __name__)


# ============================================================================
# CLI / ARGPARSE
# ============================================================================


def get_base_parser(description: str) -> argparse.ArgumentParser:
    """
    Create a base argument parser with common metrics flags.

    Args:
        description: Description for the argument parser

    Returns:
        ArgumentParser with standard arguments configured
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-o", "--output", help="Caminho do arquivo CSV de saída")
    parser.add_argument("-v", "--verbose", action="store_true", help="Habilitar log detalhado")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suprimir logs informativos")
    return parser


# ============================================================================
# CSV OPERATIONS
# ============================================================================


def save_results_csv(
    output_path: Path,
    results: CsvData,
    fieldnames: list[str],
) -> None:
    """
    Save raw results to a CSV file.

    Args:
        output_path: Path where CSV file will be saved
        results: List of dictionaries with data rows
        fieldnames: Column names for the CSV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    log.info("results_saved", file=str(output_path))


def save_summary_csv(
    output_path: Path,
    summary_data: CsvData,
) -> None:
    """
    Save aggregated metrics to a _summary.csv file.

    Args:
        output_path: Path to the original CSV (summary will be named *_summary.csv)
        summary_data: List of {metric, value} dictionaries
    """
    summary_path = output_path.parent / f"{output_path.stem}_summary{output_path.suffix}"
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(summary_data)
    log.info("summary_saved", file=str(summary_path))


def load_csv(csv_path: Path) -> list[list[str]]:
    """
    Load a CSV file as a list of lists.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of rows, where each row is a list of string values

    Raises:
        FileNotFoundError: If CSV file doesn't exist
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def read_csv_dict(csv_path: Path) -> CsvData:
    """
    Load a CSV file as a list of dictionaries.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of dictionaries mapping column names to values

    Raises:
        FileNotFoundError: If CSV file doesn't exist
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ============================================================================
# HTML OPERATIONS
# ============================================================================


def escape_html(text: str) -> str:
    """
    Escape HTML special characters in text.

    Args:
        text: Raw text that may contain HTML special characters

    Returns:
        Text with <, >, &, ", ' escaped to HTML entities
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def generate_html_table(
    headers: list[str],
    rows: list[dict[str, Any]],
    max_rows: int = 10,
) -> str:
    """
    Generate an HTML table from headers and data rows.

    Args:
        headers: Column header names
        rows: Data rows as dictionaries
        max_rows: Maximum number of rows to display

    Returns:
        HTML string for the table
    """
    html = "<table>\n  <tr>\n"
    for header in headers:
        html += f"    <th>{escape_html(header)}</th>\n"
    html += "  </tr>\n"

    for row in rows[:max_rows]:
        html += "  <tr>\n"
        for header in headers:
            value = row.get(header, "")
            html += f"    <td>{escape_html(str(value))}</td>\n"
        html += "  </tr>\n"

    if len(rows) > max_rows:
        html += f"  <tr><td colspan='{len(headers)}'><em>... e mais {len(rows) - max_rows} linhas</em></td></tr>\n"

    html += "</table>\n"
    return html


# ============================================================================
# TIME & TIMING
# ============================================================================


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1h 23m 45.6s")
    """
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"


def format_timestamp(dt: datetime | None = None) -> str:
    """
    Format a datetime object to a consistent timestamp string.

    Args:
        dt: DateTime object (defaults to current time)

    Returns:
        Timestamp string in YYYYMMDD_HHMMSS format
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")


@contextmanager
def Timer(name: str = "operation"):
    """
    Context manager for timing operations.

    Args:
        name: Name of the operation being timed

    Yields:
        None

    Example:
        with Timer("database_query"):
            result = db.query()
        # Logs: database_query completed in 1.23s
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        log.info(f"{name}_completed", duration_seconds=elapsed, duration_formatted=format_duration(elapsed))


# ============================================================================
# STATISTICS
# ============================================================================


def calculate_stats(
    values: list[float],
    percentiles: list[int] | None = None,
) -> dict[str, float]:
    """
    Calculate statistics for a list of numeric values.

    Args:
        values: List of numeric values
        percentiles: Percentiles to calculate (default: [50, 95, 99])

    Returns:
        Dictionary with min, max, mean, and requested percentiles
    """
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}

    import statistics

    stats = {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
    }

    if percentiles is None:
        percentiles = [50, 95, 99]

    for p in percentiles:
        try:
            stats[f"p{p}"] = statistics.quantiles(values, n=100)[p - 1]
        except (statistics.StatisticsError, IndexError):
            stats[f"p{p}"] = 0.0

    return stats


def format_percentile(value: float, unit: str = "") -> str:
    """
    Format a percentile value for display.

    Args:
        value: Numeric value to format
        unit: Optional unit string to append

    Returns:
        Formatted string with appropriate precision
    """
    if value < 1:
        result = f"{value:.3f}"
    elif value < 100:
        result = f"{value:.2f}"
    else:
        result = f"{value:.1f}"

    return f"{result}{unit}" if unit else result


# ============================================================================
# DISPLAY / FORMATTING
# ============================================================================


def print_summary_box(title: str, metrics: list[MetricTuple]) -> None:
    """
    Print a formatted statistical summary to the console.

    Args:
        title: Title for the summary box
        metrics: List of (label, value) or (label, value, width) tuples
                Use None as value to print a label only (spacer)
    """
    print("\n" + "=" * 60)
    print(f"SUMÁRIO ESTATÍSTICO - {title}")
    print("=" * 60)
    for item in metrics:
        if len(item) == 2:
            label, value = item
            if value is None:
                print(f"{label}")
            else:
                print(f"{label:30s} {value}")
        elif len(item) == 3:
            label, value, width = item
            if value is None:
                print(f"{label}")
            else:
                print(f"{label:{width}s} {value}")
    print("=" * 60)


def print_progress(
    current: int,
    total: int,
    prefix: str = "",
    suffix: str = "",
    bar_width: int = 40,
) -> None:
    """
    Print a progress bar to the console.

    Args:
        current: Current progress value
        total: Total value for completion
        prefix: Optional text prefix
        suffix: Optional text suffix
        bar_width: Width of the progress bar in characters
    """
    if total == 0:
        percent = 100
    else:
        percent = current / total * 100

    filled = int(bar_width * current // total) if total > 0 else bar_width
    bar = "█" * filled + "░" * (bar_width - filled)

    suffix_text = f" {current}/{total}" if total > 0 else ""
    print(f"\r{prefix} |{bar}| {percent:.1f}%{suffix_text}{suffix}", end="", flush=True)

    if current >= total:
        print()  # New line when complete
