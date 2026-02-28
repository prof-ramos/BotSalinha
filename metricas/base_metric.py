"""
Base class for BotSalinha metrics scripts.

This module provides a standardized interface for all metric collection scripts,
reducing code duplication and ensuring consistency across metrics.
"""

import argparse
import csv
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from metricas.config import get_metrics_config
from metricas.utils import (
    configure_logging,
    get_base_parser,
    print_summary_box,
    save_results_csv,
    save_summary_csv,
)


class BaseMetric(ABC):
    """
    Abstract base class for metric collection scripts.

    All metric scripts should inherit from this class and implement
    the required methods to ensure consistent behavior.

    Example:
        class DatabaseAccessMetric(BaseMetric):
            def __init__(self):
                super().__init__(
                    name='database_access',
                    description='Database write/read operation latency',
                    output_file='performance_acesso.csv'
                )

            async def collect(self) -> list[dict[str, Any]]:
                # Collect metric data
                return results

            def calculate_summary(self, data: list[dict[str, Any]]) -> list[tuple[str, Any]]:
                # Calculate summary statistics
                return metrics
    """

    def __init__(
        self,
        name: str,
        description: str,
        output_file: str,
    ):
        """
        Initialize the metric collector.

        Args:
            name: Metric identifier (e.g., 'database_access', 'rag_quality')
            description: Human-readable description of the metric
            output_file: Default CSV output filename
        """
        self.name = name
        self.description = description
        self.output_file = output_file
        self.config = get_metrics_config()

    @abstractmethod
    async def collect(self, **kwargs) -> list[dict[str, Any]]:
        """
        Collect metric data.

        This method must be implemented by subclasses to perform
        the actual metric collection.

        Args:
            **kwargs: Optional parameters for metric collection
                (e.g., num_inserts, num_reads, num_prompts)

        Returns:
            List of dictionaries containing metric data rows

        Raises:
            Exception: If metric collection fails
        """
        pass

    def get_fieldnames(self, data: list[dict[str, Any]]) -> list[str]:
        """
        Get CSV fieldnames from collected data.

        Args:
            data: Collected metric data

        Returns:
            List of field names for CSV output
        """
        if not data:
            return []
        return list(data[0].keys())

    def calculate_summary(
        self,
        data: list[dict[str, Any]],
    ) -> list[tuple[str, Any]]:
        """
        Calculate summary statistics from collected data.

        This method can be overridden by subclasses to provide
        custom summary calculations.

        Args:
            data: Collected metric data

        Returns:
            List of (label, value) tuples for summary display
        """
        return [
            ("Total de registros:", len(data)),
            ("Arquivo de saída:", self.output_file),
        ]

    def calculate_summary_metrics(
        self,
        data: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """
        Calculate summary metrics for CSV export.

        This method can be overridden by subclasses to provide
        custom summary metrics for the _summary.csv file.

        Args:
            data: Collected metric data

        Returns:
            List of {metric, value} dictionaries
        """
        return [
            {"metric": "total_records", "value": str(len(data))},
            {"metric": "output_file", "value": self.output_file},
        ]

    def get_parser(self) -> argparse.ArgumentParser:
        """
        Get argument parser for this metric.

        This method can be overridden to add metric-specific arguments.

        Returns:
            ArgumentParser with base arguments already configured
        """
        parser = get_base_parser(f"Generate {self.name} metrics")
        return parser

    def parse_args(self) -> argparse.Namespace:
        """
        Parse command line arguments.

        Returns:
            Parsed arguments namespace
        """
        return self.get_parser().parse_args()

    async def run(self, **kwargs) -> int:
        """
        Run the metric collection pipeline.

        This method orchestrates the full metric collection process:
        1. Setup logging
        2. Collect data
        3. Save results to CSV
        4. Calculate and display summary
        5. Save summary metrics

        Args:
            **kwargs: Optional parameters passed to collect()

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        args = self.parse_args()

        # Configure logging
        configure_logging(verbose=args.verbose, quiet=args.quiet)

        # Determine output file
        output_file = args.output or str(
            self.config.metrics_output_dir / self.output_file
        )

        try:
            # Collect data
            data = await self.collect(**kwargs)

            if not data:
                print(f"Warning: No data collected for {self.name}")
                return 0

            # Save results
            fieldnames = self.get_fieldnames(data)
            output_path = Path(output_file)
            save_results_csv(output_path, data, fieldnames)

            # Calculate and display summary
            summary = self.calculate_summary(data)
            print_summary_box(self.name.upper(), summary)

            # Save summary metrics
            summary_metrics = self.calculate_summary_metrics(data)
            save_summary_csv(output_path, summary_metrics)

            return 0

        except Exception as e:
            print(f"Error collecting {self.name} metrics: {e}")
            return 1


def create_metric_cli(metric_class: type[BaseMetric]) -> None:
    """
    Create a CLI entry point for a metric script.

    This helper function creates a main() function for metric scripts
    that follow the BaseMetric pattern.

    Args:
        metric_class: BaseMetric subclass to instantiate

    Example:
        def main() -> None:
            create_metric_cli(DatabaseAccessMetric)

        if __name__ == "__main__":
            import asyncio
            asyncio.run(main())
    """
    import asyncio
    import sys

    async def _main() -> None:
        metric = metric_class()
        exit_code = await metric.run()
        sys.exit(exit_code)

    asyncio.run(_main())
