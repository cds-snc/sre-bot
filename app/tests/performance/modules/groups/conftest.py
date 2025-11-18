"""Performance test fixtures for groups module."""

import pytest


@pytest.fixture
def performance_metrics():
    """Container for collecting performance metrics."""
    return {
        "operations": [],
        "latencies": [],
        "errors": [],
        "start_time": None,
        "end_time": None,
    }
