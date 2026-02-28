"""
HTML Report Generator for BotSalinha metrics.

This module provides a centralized HTML generator using Jinja2 templates,
separating presentation logic from data processing.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


class HTMLReportGenerator:
    """
    Generate HTML reports using Jinja2 templates.

    This class encapsulates all HTML generation logic, using templates
    for separation of concerns and maintainability.
    """

    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize the HTML report generator.

        Args:
            templates_dir: Path to templates directory (default: metricas/templates/)
        """
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))

    def generate_report(
        self,
        results: dict[str, tuple[bool, str, str]],
        csv_data: dict[str, list[dict[str, str]] | None],
        metrics_metadata: dict[str, dict[str, str]],
        output_path: Path,
    ) -> None:
        """
        Generate a complete HTML report.

        Args:
            results: Mapping of metric name to (success, stdout, stderr)
            csv_data: Mapping of metric name to parsed CSV data
            metrics_metadata: Mapping of metric name to metadata dict
            output_path: Path to write the HTML report
        """
        # Calculate summary statistics
        total_results = len(results)
        successful_results = sum(1 for r in results.values() if r[0])
        failed_results = total_results - successful_results

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y.%m.%d.%H%M")

        # Load and render template
        template = self.env.get_template("report.html")
        html = template.render(
            timestamp=timestamp,
            total_results=total_results,
            successful_results=successful_results,
            failed_results=failed_results,
            results=results,
            csv_data=csv_data,
            metrics=metrics_metadata,
        )

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    def generate_summary(
        self,
        total: int,
        successful: int,
        failed: int,
        timestamp: str | None = None,
    ) -> str:
        """
        Generate HTML summary section.

        Args:
            total: Total number of metrics
            successful: Number of successful metrics
            failed: Number of failed metrics
            timestamp: Optional timestamp string

        Returns:
            HTML string for summary section
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y.%m.%d.%H%M")

        template = self.env.get_template("summary.html")
        return template.render_summary(total, successful, failed)

    def generate_section(
        self,
        name: str,
        description: str,
        success: bool,
        data: list[dict[str, str]] | None = None,
        stderr: str = "",
        stdout: str = "",
    ) -> str:
        """
        Generate HTML for a metric section.

        Args:
            name: Section name
            description: Section description
            success: Whether the metric succeeded
            data: Optional CSV data rows
            stderr: Optional error output
            stdout: Optional standard output

        Returns:
            HTML string for the section
        """
        template = self.env.get_template("section.html")
        return template.render_section(
            name=name,
            description=description,
            success=success,
            data=data,
            stderr=stderr,
            stdout=stdout,
        )

    def generate_chart(
        self,
        chart_type: str,
        data: list[dict[str, Any]],
        title: str,
    ) -> str:
        """
        Generate HTML for a chart.

        Args:
            chart_type: Type of chart ('access', 'rag', 'quality', 'performance')
            data: Data rows for the chart
            title: Chart title

        Returns:
            HTML string for the chart

        Raises:
            ValueError: If chart_type is not recognized
        """
        template = self.env.get_template("charts.html")

        chart_macros = {
            "access": template.access_chart,
            "rag": template.rag_chart,
            "quality": template.quality_chart,
            "performance": template.performance_chart,
        }

        if chart_type not in chart_macros:
            raise ValueError(
                f"Unknown chart type: {chart_type}. "
                f"Valid types: {list(chart_macros.keys())}"
            )

        chart_html = chart_macros[chart_type](data)
        return template.module.chart_container(title, chart_html)


# Singleton instance for convenience
_generator_instance: HTMLReportGenerator | None = None


def get_html_generator() -> HTMLReportGenerator:
    """
    Get a cached HTMLReportGenerator instance.

    Returns:
        HTMLReportGenerator singleton instance
    """
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = HTMLReportGenerator()
    return _generator_instance
