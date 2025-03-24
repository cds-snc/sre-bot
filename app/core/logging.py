"""SRE Bot structure logging module."""

import logging
import structlog
from .config import settings


def configure_logging():
    """Configure structured logging for the application."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Add pretty printing for development, JSON for production
    if not settings.is_production:  # Development mode
        processors.append(structlog.dev.ConsoleRenderer())
    else:  # Production mode
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

    return structlog.get_logger()


logger = configure_logging()
