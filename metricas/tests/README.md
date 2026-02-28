# Metricas Tests

Unit tests for the BotSalinha metrics module.

## Structure

```
metricas/tests/
├── __init__.py           # Package marker
├── conftest.py           # Pytest fixtures
├── test_config.py        # Tests for config.py
├── test_utils.py         # Tests for utils.py
└── README.md             # This file
```

## Running Tests

### Run all metrics tests:
```bash
pytest metricas/tests/
```

### Run specific test file:
```bash
pytest metricas/tests/test_config.py
pytest metricas/tests/test_utils.py
```

### Run with coverage:
```bash
pytest metricas/tests/ --cov=metricas --cov-report=html
```

### Run with verbose output:
```bash
pytest metricas/tests/ -v
```

## Test Coverage Goals

| Module | Target Coverage | Status |
|--------|----------------|--------|
| config.py | >= 90% | ✅ |
| utils.py | >= 80% | ✅ |
| html_generator.py | >= 70% | ⏳ |
| base_metric.py | >= 70% | ⏳ |

## Fixtures

### temp_dir
Creates a temporary directory that is cleaned up after the test.

### sample_metrics_data
Provides sample metrics data for testing.

### sample_csv_data
Provides sample CSV data for testing.

### sample_html_template
Provides a sample HTML template for testing.

## Adding New Tests

When adding a new module to `metricas/`, create a corresponding test file:

```python
"""
Tests for metricas.new_module
"""

import pytest
from metricas.new_module import NewClass


class TestNewClass:
    """Test NewClass functionality."""

    def test_initialization(self):
        """Test that NewClass can be initialized."""
        obj = NewClass()
        assert obj is not None
```

## Notes

- Tests use `pytest` and standard pytest fixtures
- Mock external dependencies (structlog, database, etc.)
- Tests should be fast (< 1 second per test)
- Use descriptive test names that explain what is being tested
