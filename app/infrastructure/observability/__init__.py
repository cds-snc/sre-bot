"""Infrastructure observability module - logging and monitoring.

Exports:
    get_module_logger: Get a logger for the calling module (deprecated)
    logger: Global logger instance
    configure_logging: Configure structured logging

TODO: Remove this module in future major release.
"""

from infrastructure.observability.logging import (
    get_module_logger,
    logger,
    configure_logging,
)

__all__ = [
    "get_module_logger",
    "logger",
    "configure_logging",
]
