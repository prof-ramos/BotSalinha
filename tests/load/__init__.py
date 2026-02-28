"""Load testing suite for BotSalinha RAG system.

This package contains load tests for validating performance, scalability,
and system limits under concurrent user conditions.
"""

from tests.load.load_test_runner import LoadTestRunner
from tests.load.metrics import LoadTestMetrics, QueryMetrics
from tests.load.workload_generator import LegalWorkloadGenerator

__all__ = [
    "LoadTestRunner",
    "LoadTestMetrics",
    "QueryMetrics",
    "LegalWorkloadGenerator",
]
