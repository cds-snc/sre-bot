"""Infrastructure observability module - logging and monitoring.

Exports:
    get_module_logger: Get a logger for the calling module
    logger: Global logger instance
    configure_logging: Configure structured logging
    get_logger: Get a logger with optional context
"""

from infrastructure.observability.logging import (
    get_module_logger,
    logger,
    configure_logging,
    get_logger,
)

__all__ = [
    "get_module_logger",
    "logger",
    "configure_logging",
    "get_logger",
]
