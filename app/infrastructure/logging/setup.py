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
from pathlib import Path
import structlog
from structlog.stdlib import BoundLogger
from structlog.processors import CallsiteParameter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrastructure.configuration import Settings


def _apply_otel_code_conventions(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Apply OpenTelemetry semantic conventions for code attributes.

    Converts structlog callsite parameters to OTel standard fields:
        - code.file.path: Full file path
        - code.function.name: Fully qualified function name (includes module.function)
        - code.line.number: Line number

    Per OpenTelemetry specs, code.namespace is deprecated and should be
    included in code.function.name as a fully qualified name.

    References:
        - https://opentelemetry.io/docs/specs/semconv/attributes-registry/code/
    """
    # Extract pathname and convert to code.file.path (OTel standard)
    if "pathname" in event_dict:
        pathname = event_dict["pathname"]

        # Convert absolute path to relative from app root for cleaner logs
        try:
            path = Path(pathname)
            parts = path.parts
            if "app" in parts:
                app_index = parts.index("app")
                # Get path relative to app directory
                relative_parts = parts[app_index + 1 :]
                if relative_parts:
                    event_dict["code.file.path"] = "/".join(relative_parts)
                else:
                    event_dict["code.file.path"] = pathname
            else:
                event_dict["code.file.path"] = pathname
        except (ValueError, IndexError):
            event_dict["code.file.path"] = pathname

    # Create fully qualified function name (module.function)
    if "module" in event_dict and "func_name" in event_dict:
        module = event_dict["module"]
        func_name = event_dict["func_name"]
        event_dict["code.function.name"] = f"{module}.{func_name}"
    elif "func_name" in event_dict:
        # Fallback: just use function name if module unavailable
        event_dict["code.function.name"] = event_dict["func_name"]

    # Rename lineno to code.line.number (OTel standard)
    if "lineno" in event_dict:
        event_dict["code.line.number"] = event_dict["lineno"]

    # Clean up fields we don't need in final output
    event_dict.pop("pathname", None)
    event_dict.pop("module", None)
    event_dict.pop("func_name", None)
    event_dict.pop("lineno", None)
    event_dict.pop("filename", None)  # Redundant with code.file.path

    return event_dict


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
    """Configure structured logging with OpenTelemetry semantic conventions.

    Configures structlog with:
    - OpenTelemetry code attributes (code.file.path, code.function.name, code.line.number)
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

    # Build processor pipeline per structlog best practices
    # Order matters: context vars first, then enrichment, then formatting
    processors = [
        # 1. Context propagation (must be first)
        structlog.contextvars.merge_contextvars,
        # 2. Add metadata
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        # 3. Add OpenTelemetry code attributes for debugging
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                CallsiteParameter.LINENO,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.MODULE,  # For fully qualified function name
                CallsiteParameter.PATHNAME,  # For code.file.path
            ]
        ),
        # 4. Apply OpenTelemetry semantic conventions
        _apply_otel_code_conventions,
        # 5. Exception formatting
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 6. Final rendering (environment-specific)
    if not prod_mode:  # Development mode
        # Pretty exceptions with colors (requires rich or better-exceptions)
        try:
            processors.append(structlog.processors.ExceptionPrettyPrinter())
        except ImportError:
            pass  # Fall back to plain exceptions if rich not installed
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
