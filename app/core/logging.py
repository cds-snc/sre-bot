"""SRE Bot structure logging module."""

import logging
import inspect
import structlog
from structlog.stdlib import BoundLogger
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

    return structlog.stdlib.get_logger()


logger: BoundLogger = configure_logging()


def get_module_logger() -> BoundLogger:
    """Get a logger for the calling module with full path context."""
    current_frame = inspect.currentframe()
    if current_frame is None:
        return logger

    frame = current_frame.f_back
    module = inspect.getmodule(frame)

    if module:
        module_name = module.__name__

        parts = module_name.split(".")

        context = {
            "component": parts[-1],
            "module_path": module_name,
        }

        return logger.bind(**context)

    return logger.bind(component="unknown")
