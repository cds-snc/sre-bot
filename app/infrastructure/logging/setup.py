"""Structlog configuration and logger setup.

This module provides the core logging configuration for the application.
It configures structlog with enhanced processors for debugging context,
proper exception formatting, and environment-aware rendering.

Usage:
    from infrastructure.logging import configure_logging

    # Configure logging once, in the app factory's configuration phase
    configure_logging(identity.environment, get_logging_settings())

    # Get a logger (standard structlog pattern)
    import structlog
    logger = structlog.get_logger()
    logger.info("event_name", key="value")

The same pipeline renders uvicorn's own loggers (their handlers are cleared so they
propagate to the root handler), Python warnings and, through a bootstrap pipeline and an
uncaught-exception hook, failures before the [logging] slice loads
(decisions/observability.md). Lines emitted while modules import, before the app
factory runs, stay plain.

Dependencies:
    - infrastructure.logging.settings.LoggingSettings (the [logging] slice)
"""

import contextlib
import logging
import sys
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

import structlog
from structlog.processors import CallsiteParameter
from structlog.stdlib import BoundLogger

from infrastructure.logging.filters import LivenessAccessFilter
from infrastructure.logging.formatters import downgrade_transient_socket_mode_errors, mask_sensitive_data
from infrastructure.logging.settings import LoggingSettings


def _apply_otel_code_conventions(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...]:
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
        except ValueError, IndexError:
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


def _add_static_fields(fields: Mapping[str, str]) -> Callable[[Any, str, MutableMapping[str, Any]], Mapping[str, Any]]:
    """Return a processor that puts the same fields on every record.

    The fields are not context: clear_contextvars cannot remove them, and the chain
    reaches standard-library records too (decisions/observability.md, Service identity).
    """

    def processor(logger: Any, method_name: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
        event_dict.update(fields)
        return event_dict

    return processor


def _build_base_processors(
    logging_settings: LoggingSettings,
    static_fields: Mapping[str, str] | None = None,
) -> list[
    Callable[
        [Any, str, MutableMapping[str, Any]],
        Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...],
    ]
]:
    return [
        # 1. Context propagation (must be first)
        structlog.contextvars.merge_contextvars,
        # Service identity: the same fields on every record, ahead of the redaction processor
        _add_static_fields(static_fields or {}),
        # 2. Add metadata
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
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
        # 6. Redact sensitive fields before final rendering
        mask_sensitive_data(additional_patterns=frozenset(logging_settings.redaction_extra_keys)),
    ]


def configure_logging(
    environment: Literal["local", "ci", "production"],
    logging_settings: LoggingSettings,
    log_level: str | None = None,
    static_fields: Mapping[str, str] | None = None,
) -> BoundLogger:
    """Configure structured logging with OpenTelemetry semantic conventions.

    Called once by the app factory's configuration phase, right after the identity
    and [logging] slices load, so every later configuration event is rendered by
    this pipeline (decisions/observability.md). Configures structlog with:
    - OpenTelemetry code attributes (code.file.path, code.function.name, code.line.number)
    - Proper exception formatting with stack traces
    - Context variable merging for correlation IDs
    - Test environment detection for log suppression

    Args:
        environment: The deployment environment; production renders JSON, others the console.
        logging_settings: The [logging] slice.
        log_level: Optional override for log level (DEBUG, INFO, WARNING, etc).
            Defaults to logging_settings.log_level if not provided.
        static_fields: Fields added to every record, the service identity; they survive
            clear_contextvars and reach standard-library records.

    Returns:
        Configured logger instance

    Example:
        logger = configure_logging("local", get_logging_settings(), log_level="DEBUG")
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
            # Cached loggers keep a stale processor list across reconfigures, which breaks capture_logs.
            cache_logger_on_first_use=False,
        )

        # Configure standard logging with silent handler
        logging.basicConfig(
            format="%(message)s",
            level=logging.CRITICAL + 1,
            force=True,
        )
        return structlog.stdlib.get_logger()

    # Determine production mode
    prod_mode = environment == "production"

    # Build processor pipeline per structlog best practices
    # Order matters: context vars first, then enrichment, then formatting
    processors = _build_base_processors(logging_settings, static_fields)

    # 6. Final rendering (environment-specific)
    renderers: list[Any] = [structlog.stdlib.ProcessorFormatter.remove_processors_meta]
    if not prod_mode:  # Development mode
        # Pretty exceptions with colors (requires rich or better-exceptions)
        with contextlib.suppress(ImportError):
            renderers.append(structlog.processors.ExceptionPrettyPrinter())
        renderers.append(structlog.dev.ConsoleRenderer())
    else:  # Production mode
        renderers.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=[
            *processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Render stdlib records (slack_bolt, slack_sdk, botocore, ...) through the same pipeline.
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[
                *processors,
                downgrade_transient_socket_mode_errors,
            ],
            processors=renderers,
        )
    )
    effective_log_level = log_level or logging_settings.log_level
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, effective_log_level.upper(), logging.INFO))
    if root_logger.level > logging.DEBUG:
        for library_logger in _QUIET_LIBRARY_LOGGERS:
            logging.getLogger(library_logger).setLevel(logging.WARNING)

    _route_uvicorn_through_root()
    logging.captureWarnings(True)

    return structlog.stdlib.get_logger()


# Library loggers whose INFO lines are connection detail (credential and endpoint discovery, once
# per client). They are held at WARNING unless the root level is DEBUG, which shows them again.
_QUIET_LIBRARY_LOGGERS = ("botocore",)

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")


def _route_uvicorn_through_root() -> None:
    """Let uvicorn's loggers propagate to the root handler and classify liveness access lines.

    uvicorn installs its own handlers (propagate False) before it imports the app, so
    clearing them here, from the app factory, puts every later uvicorn line in the pipeline.
    """
    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(logging.NOTSET)
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, LivenessAccessFilter) for item in access_logger.filters):
        access_logger.addFilter(LivenessAccessFilter())


def configure_bootstrap_logging() -> None:
    """Install the production JSON pipeline at INFO with no service identity.

    Runs first in the configuration phase so a failure before the [logging] slice loads
    (identity, file selection) is one JSON line; configure_logging replaces it once the
    real settings are known. The default slice is built without reading any file.
    """
    if _is_test_environment():
        return
    configure_logging("production", LoggingSettings.model_construct())


def install_uncaught_exception_hook(reported: tuple[type[BaseException], ...]) -> None:
    """Render an exception that escapes the app factory as one CRITICAL JSON line.

    uvicorn logs only a TypeError from the factory; anything else reaches sys.excepthook
    and would print a raw multi-line traceback. Exceptions in ``reported`` were already
    logged where they were raised and are not logged twice. The exit status is unchanged.
    """
    if _is_test_environment():
        return

    def hook(exc_type: type[BaseException], exc: BaseException, traceback: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, traceback)
            return
        if issubclass(exc_type, reported):
            return
        structlog.get_logger(__name__).critical("uncaught_exception", exc_info=(exc_type, exc, traceback))

    sys.excepthook = hook
