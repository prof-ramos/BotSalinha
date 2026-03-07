#!/usr/bin/env python3
"""
Simple script to view BotSalinha metrics.

Usage:
    python scripts/view_metrics.py          # View all metrics
    python scripts/view_metrics.py --provider  # View only provider metrics
    python scripts/view_metrics.py --rag     # View only RAG metrics
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.metrics import get_metrics_text, is_prometheus_available


def main() -> int:
    """Main entry point."""
    if not is_prometheus_available():
        print("❌ Metrics unavailable: prometheus_client not installed")
        print("   Install with: uv add prometheus-client")
        return 1

    metrics = get_metrics_text()

    # Parse simple args
    filter_type = None
    if len(sys.argv) > 1:
        filter_type = sys.argv[1].lstrip("-").lower()

    # Filter metrics based on type
    if filter_type:
        lines = metrics.split("\n")
        filtered_lines = []
        for line in lines:
            if filter_type in line.lower() or line.startswith("#"):
                filtered_lines.append(line)
        metrics = "\n".join(filtered_lines)

    print("📊 BotSalinha Metrics")
    print("=" * 60)
    print(metrics)
    print("=" * 60)
    print(f"\n💡 Run 'uv run botsalinha' with --enable-metrics to start the metrics server")
    print(f"   Then visit http://localhost:9090/metrics for Prometheus exposition")
    print(f"   Or http://localhost:9090/health for health check")

    return 0


if __name__ == "__main__":
    sys.exit(main())
