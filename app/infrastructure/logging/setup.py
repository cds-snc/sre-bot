"""Structlog configuration and logger setup.

This module provides the core logging configuration for the application.
It configures structlog with enhanced processors for debugging context,
proper exception formatting, and environment-aware rendering.

Usage:
    from infrastructure.logging import configure_logging, get_module_logger

    # Configure logging at app startup
    configure_logging()

    # Get a logger for your module
    logger = get_module_logger()
    logger.info("event_name", key="value")

Dependencies:
    - infrastructure.configuration.Settings
"""

import logging
import sys
import inspect
import structlog
from structlog.stdlib import BoundLogger
from typing import Optional
from infrastructure.configuration import settings


def _is_test_environment() -> bool:
    """Detect if running in a test environment.

    Returns:
        True if pytest is in sys.modules, False otherwise
    """
    return "pytest" in sys.modules


def configure_logging(
    log_level: Optional[str] = None,
    is_production: Optional[bool] = None,
) -> BoundLogger:
    """Configure structured logging with enhanced processors.

    Configures structlog with:
    - Enhanced processors for file/line/function context
    - Proper exception formatting with stack traces
    - Context variable merging for correlation IDs
    - Test environment detection for log suppression

    Args:
        log_level: Optional override for log level (DEBUG, INFO, WARNING, etc).
            Defaults to settings.LOG_LEVEL if not provided.
        is_production: Optional override for production mode. Defaults to
            settings.is_production if not provided. Controls JSON vs console output.

    Returns:
        Configured logger instance

    Example:
        # At application startup
        logger = configure_logging()

        # With overrides for testing
        logger = configure_logging(log_level="DEBUG", is_production=False)
    """
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

    # Determine production mode
    prod_mode = is_production if is_production is not None else settings.is_production

    # Build processor pipeline
    processors = [
        # Add context variables (correlation IDs, user info, etc)
        structlog.contextvars.merge_contextvars,
        # Add log level
        structlog.stdlib.add_log_level,
        # Add timestamp in ISO 8601 format
        structlog.processors.TimeStamper(fmt="iso"),
        # Add file, line, and function information (enhanced debugging)
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ]
        ),
        # Format exceptions with full stack traces
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add pretty printing for development, JSON for production
    if not prod_mode:  # Development mode
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
    effective_log_level = log_level or settings.LOG_LEVEL
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, effective_log_level.upper(), logging.INFO),
    )

    return structlog.stdlib.get_logger()


# Module-level logger (auto-configured on import)
logger: BoundLogger = configure_logging()


def get_logger(name: Optional[str] = None) -> BoundLogger:
    """Get a logger instance with automatic context detection.

    If name is provided, binds the logger to that name for context.
    Otherwise, uses the current module name for context.

    Args:
        name: Optional logger name (typically __name__ in calling module)

    Returns:
        Configured logger instance with context

    Example:
        # With explicit name
        logger = get_logger("my_module")

        # With auto-detection
        logger = get_logger()
    """
    if name:
        return logger.bind(logger_name=name)

    # Auto-detect calling module
    current_frame = inspect.currentframe()
    if current_frame is None:
        return logger

    frame = current_frame.f_back
    if frame is None:
        return logger

    module = inspect.getmodule(frame)
    if module:
        module_name = module.__name__
        return logger.bind(logger_name=module_name)

    return logger.bind(logger_name="unknown")


def get_module_logger() -> BoundLogger:
    """Get a logger for the calling module with full path context.

    Automatically detects the calling module and binds component
    and module_path context for structured logging.

    Returns:
        Configured logger instance with module context

    Example:
        # In modules/groups/service.py
        logger = get_module_logger()
        # logger has context: {"component": "service", "module_path": "modules.groups.service"}

        logger.info("group_created", group_id="123")
    """
    # Auto-detect calling module
    current_frame = inspect.currentframe()
    if current_frame is None:
        return logger

    frame = current_frame.f_back
    if frame is None:
        return logger

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
