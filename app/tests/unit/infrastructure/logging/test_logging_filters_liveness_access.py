"""Unit tests for the uvicorn access-log liveness filter.

A real logger carrying the filter and a capturing handler stand in for uvicorn.access.
Exact liveness probes (GET, /version or /health, no query string, status 200) are
re-levelled to DEBUG and emitted only when DEBUG is enabled; every other record keeps
INFO. A record is never dropped by the filter while its level is enabled.
"""

import logging
from collections.abc import Iterator

import pytest

from infrastructure.logging.filters import LivenessAccessFilter


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def access_logger() -> Iterator[tuple[logging.Logger, _Capture]]:
    """A logger named like uvicorn's access logger with the filter and a capturing handler."""
    logger = logging.getLogger("test.liveness.access")
    handler = _Capture()
    liveness_filter = LivenessAccessFilter()
    logger.addHandler(handler)
    logger.addFilter(liveness_filter)
    logger.propagate = False
    yield logger, handler
    logger.removeHandler(handler)
    logger.removeFilter(liveness_filter)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def _access(logger: logging.Logger, method: str, path: str, status: int) -> None:
    logger.info('%s - "%s %s HTTP/%s" %d', "10.0.0.1:1234", method, path, "1.1", status)


LIVENESS = [("GET", "/version", 200), ("GET", "/health", 200)]
STAYS_INFO = [
    ("GET", "/version?x=1", 200),
    ("GET", "/health?", 200),
    ("POST", "/version", 200),
    ("HEAD", "/health", 200),
    ("GET", "/version", 404),
    ("GET", "/version", 500),
    ("GET", "/health", 204),
    ("GET", "/versions", 200),
    ("GET", "/health/", 200),
    ("GET", "/api/health", 200),
    ("GET", "/", 200),
]


@pytest.mark.unit
@pytest.mark.parametrize(("method", "path", "status"), LIVENESS)
def test_liveness_hit_is_debug_and_absent_at_info(access_logger, method, path, status):
    """An exact liveness probe is not emitted when the logger is at INFO."""
    logger, handler = access_logger
    logger.setLevel(logging.INFO)

    _access(logger, method, path, status)

    assert handler.records == []


@pytest.mark.unit
@pytest.mark.parametrize(("method", "path", "status"), LIVENESS)
def test_liveness_hit_is_emitted_at_debug_level_when_debug_is_enabled(access_logger, method, path, status):
    """With DEBUG enabled the probe is emitted, re-levelled to DEBUG rather than dropped."""
    logger, handler = access_logger
    logger.setLevel(logging.DEBUG)

    _access(logger, method, path, status)

    (record,) = handler.records
    assert record.levelno == logging.DEBUG
    assert record.levelname == "DEBUG"


@pytest.mark.unit
@pytest.mark.parametrize(("method", "path", "status"), STAYS_INFO)
@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
def test_every_other_access_line_stays_at_info(access_logger, method, path, status, level):
    """A different method, status, path or query is emitted unchanged at INFO at either logger level."""
    logger, handler = access_logger
    logger.setLevel(level)

    _access(logger, method, path, status)

    (record,) = handler.records
    assert record.levelno == logging.INFO


@pytest.mark.unit
@pytest.mark.parametrize(
    ("msg", "args"),
    [
        ("msg", None),
        ("msg", ()),
        ("%s %s", ("only", "two")),
        ("%(method)s", {"method": "GET"}),
        ('%s - "%s %s HTTP/%s" %s', ("a", "GET", "/version", "1.1", "200")),
    ],
)
def test_malformed_access_arguments_pass_through_unchanged(access_logger, msg, args):
    """A record whose arguments are not the access shape (or a non-integer status) is left at INFO.

    Each message matches its arguments so any handler attached to the logger can render it.
    """
    logger, handler = access_logger
    logger.setLevel(logging.INFO)

    record = logging.LogRecord(logger.name, logging.INFO, __file__, 1, msg, None, None)
    record.args = args
    logger.handle(record)

    assert [item.levelno for item in handler.records] == [logging.INFO]
