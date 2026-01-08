"""Structured logging infrastructure.

This package provides centralized logging configuration and utilities
for the SRE Bot application using structlog.

Best Practices (per structlog documentation):
    1. Use structlog.get_logger() to get a logger (standard API)
    2. Use logger.bind(key=value) to add context to a logger
    3. Use bind_request_context() in middleware for request-scoped context
    4. Use configure_logging() at application startup

Public API:
    - configure_logging(): Initialize logging for the application
    - bind_request_context(): Context manager for request-scoped logging
    - get_correlation_id(): Get current correlation ID from context
    - set_correlation_id(): Set correlation ID in context
    - clear_request_context(): Clear all request context

Deprecated (backward compatibility only):
    - get_module_logger(): DEPRECATED - Use structlog.get_logger() instead
    - logger: DEPRECATED - Use structlog.get_logger() instead

Formatters:
    - add_app_info(): Processor to add app name/version
    - mask_sensitive_data(): Processor to redact sensitive fields
    - truncate_large_values(): Processor to limit string lengths
    - add_environment_info(): Processor to add environment name

Example (Best Practice):
    import structlog
    from infrastructure.logging import (
        configure_logging,
        bind_request_context,
    )

    # At application startup
    configure_logging()

    # In a module (standard structlog pattern)
    logger = structlog.get_logger()

    def process_item(item_id: str):
        log = logger.bind(item_id=item_id)
        log.info("processing_item")

    # In request handler middleware
    with bind_request_context(correlation_id="req-123", user_email="user@example.com"):
        logger.info("processing_request")  # Includes correlation_id and user_email
"""

# Core logging setup
from infrastructure.logging.setup import (
    configure_logging,
    # Deprecated - kept for backward compatibility
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
    # Deprecated - backward compatibility only
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
