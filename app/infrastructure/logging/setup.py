"""Structlog configuration and logger setup.

This module provides the core logging configuration for the application.
It configures structlog with enhanced processors for debugging context,
proper exception formatting, and environment-aware rendering.

Usage:
    from infrastructure.logging import configure_logging

    # Configure logging at app startup
    configure_logging()

    # Get a logger (standard structlog pattern)
    import structlog
    logger = structlog.get_logger()
    logger.info("event_name", key="value")

Dependencies:
    - infrastructure.configuration.Settings
"""

import logging
import sys
import structlog
from structlog.stdlib import BoundLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.configuration import Settings


def _is_test_environment() -> bool:
    """Detect if running in a test environment.

    Returns:
        True if pytest is in sys.modules, False otherwise
    """
    return "pytest" in sys.modules


def configure_logging(
    settings: "Settings",
    log_level: str | None = None,
    is_production: bool | None = None,
) -> BoundLogger:
    """Configure structured logging with enhanced processors.

    Configures structlog with:
    - Enhanced processors for file/line/function context
    - Proper exception formatting with stack traces
    - Context variable merging for correlation IDs
    - Test environment detection for log suppression

    Args:
        settings: Settings instance (REQUIRED). Must be passed explicitly.
        log_level: Optional override for log level (DEBUG, INFO, WARNING, etc).
            Defaults to settings.LOG_LEVEL if not provided.
        is_production: Optional override for production mode. Defaults to
            settings.is_production if not provided. Controls JSON vs console output.

    Returns:
        Configured logger instance

    Example:
        # At application startup
        from infrastructure.services import get_settings
        settings = get_settings()
        logger = configure_logging(settings=settings)

        # With overrides for testing
        logger = configure_logging(settings=settings, log_level="DEBUG", is_production=False)
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


# =============================================================================
# DEPRECATED FUNCTIONS - For backward compatibility only
# =============================================================================


def get_module_logger() -> BoundLogger:
    """Get a logger for the calling module with context.

    .. deprecated::
        This function is deprecated. Use `structlog.get_logger()` instead
        with explicit `.bind()` for context. This follows structlog best practices.

        Migration example:
            # OLD
            from infrastructure.logging import get_module_logger
            logger = get_module_logger()

            # NEW (best practice)
            import structlog
            logger = structlog.get_logger()
            log = logger.bind(component="my_module")  # explicit context

    Returns:
        Configured logger instance with module context
    """
    import warnings
    import inspect

    warnings.warn(
        "get_module_logger() is deprecated. Use structlog.get_logger() with "
        "explicit .bind() for context instead. See structlog best practices.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Auto-detect calling module for backward compatibility
    current_frame = inspect.currentframe()
    if current_frame is None:
        return structlog.get_logger()

    frame = current_frame.f_back
    if frame is None:
        return structlog.get_logger()

    module = inspect.getmodule(frame)
    if module:
        module_name = module.__name__
        parts = module_name.split(".")
        context = {
            "component": parts[-1],
            "module_path": module_name,
        }
        return structlog.get_logger().bind(**context)

    return structlog.get_logger().bind(component="unknown")
