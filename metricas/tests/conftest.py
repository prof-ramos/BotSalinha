"""
Pytest configuration and fixtures for metricas tests.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files.

    The directory is automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_metrics_data():
    """
    Sample metrics data for testing.

    Returns:
        List of dictionaries with sample metric data
    """
    return [
        {"metric": "test1", "value": "100", "status": "success"},
        {"metric": "test2", "value": "200", "status": "success"},
        {"metric": "test3", "value": "50", "status": "failed"},
    ]


@pytest.fixture
def sample_csv_data():
    """
    Sample CSV data for testing.

    Returns:
        List of dictionaries with CSV data
    """
    return [
        {"name": "operation1", "duration_ms": "123.45", "status": "success"},
        {"name": "operation2", "duration_ms": "67.89", "status": "success"},
        {"name": "operation3", "duration_ms": "234.56", "status": "failed"},
    ]


@pytest.fixture
def sample_html_template():
    """
    Sample HTML template for testing.

    Returns:
        String with basic HTML template
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Report</title>
    </head>
    <body>
        <h1>{{ title }}</h1>
        {% block content %}{% endblock %}
    </body>
    </html>
    """
