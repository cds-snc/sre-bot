"""Unit tests for the static-field processor in the production logging pipeline.

configure_logging returns early under pytest, so each test forces the production
path by patching _is_test_environment and turns the structlog logger cache off,
then restores structlog and the root logger. Output goes to a StringIO handler
that replaces the root handler's stream: one record through structlog and one
through the standard library, both parsed as JSON. The static fields must reach
both, survive clear_contextvars, and must not be altered by key-name redaction.
Probes log at warning because pytest resets the root level to WARNING for each test phase.
"""

import json
import logging
from collections.abc import Iterator
from io import StringIO

import pytest
import structlog

from infrastructure.logging.settings import LoggingSettings
from infrastructure.logging.setup import configure_logging

pytestmark = pytest.mark.unit

FIELDS = {
    "service.name": "sre-bot",
    "service.version": "abc123",
    "service.instance.id": "11111111-1111-4111-8111-111111111111",
    "deployment.environment.name": "production",
}


@pytest.fixture
def output(monkeypatch: pytest.MonkeyPatch) -> Iterator[StringIO]:
    """Configure the production pipeline with the static fields and capture the root handler's stream."""
    monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
    configure = structlog.configure
    monkeypatch.setattr(structlog, "configure", lambda **kw: configure(**{**kw, "cache_logger_on_first_use": False}))
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    configure_logging("production", LoggingSettings(), static_fields=FIELDS)
    stream = StringIO()
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(stream)
    yield stream
    root.handlers, root.level = saved_handlers, saved_level
    structlog.reset_defaults()


def _records(stream: StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def test_a_structlog_record_carries_the_static_fields(output: StringIO) -> None:
    """Every field is on the record as a flat dotted key, unredacted."""
    structlog.get_logger().warning("probe")

    record = _records(output)[0]
    assert {name: record[name] for name in FIELDS} == FIELDS


def test_a_standard_library_record_carries_the_static_fields(output: StringIO) -> None:
    """A record from a third-party stdlib logger goes through the same chain."""
    logging.getLogger("uvicorn.error").warning("probe")

    record = _records(output)[0]
    assert {name: record[name] for name in FIELDS} == FIELDS


def test_the_static_fields_survive_clearing_the_context(output: StringIO) -> None:
    """clear_contextvars wipes bound context, but the fields are not context."""
    structlog.contextvars.bind_contextvars(correlation_id="c-1")
    structlog.contextvars.clear_contextvars()
    structlog.get_logger().warning("probe")

    record = _records(output)[0]
    assert "correlation_id" not in record
    assert record["service.name"] == "sre-bot"


def test_bound_context_is_kept_alongside_the_static_fields(output: StringIO) -> None:
    """Static fields do not displace the request context merged ahead of them."""
    structlog.contextvars.bind_contextvars(correlation_id="c-2")
    try:
        structlog.get_logger().warning("probe")
    finally:
        structlog.contextvars.clear_contextvars()

    record = _records(output)[0]
    assert record["correlation_id"] == "c-2"
    assert record["deployment.environment.name"] == "production"
