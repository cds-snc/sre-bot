"""Unit tests for the library loggers the production logging pipeline holds quiet.

configure_logging returns early under pytest, so each test forces the production path by
patching _is_test_environment, then restores structlog, the root logger and botocore's level.
botocore writes credential and endpoint discovery at INFO once per client; the pipeline
holds it at WARNING unless the configured level is DEBUG.
"""

import logging
from collections.abc import Iterator

import pytest
import structlog

from infrastructure.logging.settings import LoggingSettings
from infrastructure.logging.setup import configure_logging

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _production_pipeline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
    configure = structlog.configure
    monkeypatch.setattr(structlog, "configure", lambda **kw: configure(**{**kw, "cache_logger_on_first_use": False}))
    root = logging.getLogger()
    botocore = logging.getLogger("botocore")
    saved_handlers, saved_level, saved_botocore = root.handlers[:], root.level, botocore.level
    yield
    root.handlers, root.level = saved_handlers, saved_level
    botocore.setLevel(saved_botocore)
    structlog.reset_defaults()


def test_botocore_is_held_at_warning_at_the_info_level() -> None:
    """At INFO the botocore logger drops its INFO connection lines."""
    configure_logging("production", LoggingSettings(log_level="INFO"))

    assert logging.getLogger("botocore").level == logging.WARNING


def test_botocore_keeps_its_lines_at_the_debug_level() -> None:
    """At DEBUG the botocore logger is left to inherit the root level, so its detail shows."""
    logging.getLogger("botocore").setLevel(logging.NOTSET)

    configure_logging("production", LoggingSettings(log_level="DEBUG"))

    assert logging.getLogger("botocore").level == logging.NOTSET
