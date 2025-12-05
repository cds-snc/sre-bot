"""SRE Bot structure logging module."""

import logging
import inspect
import sys
import structlog
from structlog.stdlib import BoundLogger
from .config import settings


def _is_test_environment() -> bool:
    """Detect if running in a test environment."""
    return "pytest" in sys.modules


def configure_logging():
    """Configure structured logging for the application."""
    # Suppress all logging during tests
    if _is_test_environment():
        # Set root logger to suppress all output during tests
        logging.root.setLevel(logging.CRITICAL + 1)

        # Configure structlog with minimal processors for tests
        # We need basic processors to avoid errors, but logs won't be emitted
        # because the root logger level is set to CRITICAL + 1
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Configure standard logging with silent handler
        logging.basicConfig(
            format="%(message)s",
            level=logging.CRITICAL + 1,
            force=True,
        )
        return structlog.stdlib.get_logger()

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
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
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
