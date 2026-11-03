"""Fixtures for infrastructure.logging tests."""

import logging
import sys
import warnings
from collections.abc import Iterator
from unittest.mock import Mock

import pytest
import structlog

from contracts.configuration import HostInfo


@pytest.fixture
def mock_settings():
    """Mock HostInfo instance for testing."""
    settings = Mock(spec=HostInfo)
    settings.environment = "local"
    return settings


@pytest.fixture
def process_logging_state() -> Iterator[None]:
    """Restore the process-wide logging state a real configure_logging call changes.

    Covers the root handler and level, the four uvicorn loggers, sys.excepthook,
    warnings capture and structlog's configuration.
    """
    root = logging.getLogger()
    saved_root = (root.handlers[:], root.level)
    uvicorn_loggers = [logging.getLogger(name) for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")]
    saved_uvicorn = [(item, item.handlers[:], item.propagate, item.level, item.filters[:]) for item in uvicorn_loggers]
    saved_hook = sys.excepthook
    saved_showwarning = warnings.showwarning
    saved_config = structlog.get_config()
    yield
    root.handlers, root.level = saved_root
    for item, handlers, propagate, level, filters in saved_uvicorn:
        item.handlers, item.propagate, item.filters = handlers, propagate, filters
        item.setLevel(level)
    sys.excepthook = saved_hook
    logging.captureWarnings(False)
    warnings.showwarning = saved_showwarning
    structlog.reset_defaults()
    structlog.configure(**saved_config)
