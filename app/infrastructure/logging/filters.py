"""Logging filters.

LivenessAccessFilter classifies the exact liveness probes on the uvicorn access
logger as DEBUG without ever dropping them (decisions/health-checks.md).
"""

import logging

LIVENESS_PATHS = frozenset({"/version", "/health"})
_ACCESS_ARGS_LENGTH = 5  # client, method, path (with query), http version, status


def _is_liveness_hit(args: object) -> bool:
    """True for a successful GET on exactly a liveness path with no query string."""
    if not isinstance(args, tuple) or len(args) != _ACCESS_ARGS_LENGTH:
        return False
    _client, method, path, _version, status = args
    return method == "GET" and path in LIVENESS_PATHS and status == 200


class LivenessAccessFilter(logging.Filter):
    """Re-level exact liveness access lines to DEBUG; every other record passes unchanged.

    Attach it to the logger, not a handler: a handler without a level would still emit
    the re-levelled record when DEBUG is off. A liveness record is emitted only when
    its logger has DEBUG enabled, so nothing is lost once DEBUG is switched on.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not _is_liveness_hit(record.args):
            return True
        record.levelno = logging.DEBUG
        record.levelname = logging.getLevelName(logging.DEBUG)
        return logging.getLogger(record.name).isEnabledFor(logging.DEBUG)
