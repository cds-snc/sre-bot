"""Structured logging infrastructure.

This package provides centralized logging configuration and utilities
for the SRE Bot application using structlog.

Public API:
    - configure_logging(): Initialize logging for the application
    - get_logger(): Get a logger instance with a specific name
    - get_module_logger(): Get a logger for the calling module
    - bind_request_context(): Context manager for request-scoped logging
    - get_correlation_id(): Get current correlation ID from context
    - set_correlation_id(): Set correlation ID in context
    - clear_request_context(): Clear all request context

Formatters:
    - add_app_info(): Processor to add app name/version
    - mask_sensitive_data(): Processor to redact sensitive fields
    - truncate_large_values(): Processor to limit string lengths
    - add_environment_info(): Processor to add environment name

Example:
    from infrastructure.logging import (
        configure_logging,
        get_module_logger,
        bind_request_context,
    )

    # At application startup
    configure_logging()

    # In a module
    logger = get_module_logger()
    logger.info("module_initialized")

    # In request handler
    with bind_request_context(correlation_id="req-123"):
        logger.info("processing_request")
"""

# Core logging setup
from infrastructure.logging.setup import (
    configure_logging,
    get_logger,
    get_module_logger,
)

# Request context binding
from infrastructure.logging.context import (
    bind_request_context,
    get_correlation_id,
    set_correlation_id,
    clear_request_context,
)

# Log formatters/processors
from infrastructure.logging.formatters import (
    add_app_info,
    mask_sensitive_data,
    truncate_large_values,
    add_environment_info,
    SENSITIVE_PATTERNS,
)

__all__ = [
    # Setup
    "configure_logging",
    "get_logger",
    "get_module_logger",
    # Context
    "bind_request_context",
    "get_correlation_id",
    "set_correlation_id",
    "clear_request_context",
    # Formatters
    "add_app_info",
    "mask_sensitive_data",
    "truncate_large_values",
    "add_environment_info",
    "SENSITIVE_PATTERNS",
]
