"""Infrastructure observability module - structured logging.

This module re-exports the logging API from infrastructure.logging for backward
compatibility. New code should import directly from infrastructure.logging.

Maintained exports:
    - configure_logging: Initialize logging
    - get_logger: Get logger with name
    - get_module_logger: Get logger for calling module
    - logger: Module-level logger instance
    - _is_test_environment: Internal test detection (for test compatibility)

Migration:
    from infrastructure.observability.logging import get_module_logger  # OLD
    from infrastructure.logging import get_module_logger  # NEW
"""

# Re-export from canonical location
from infrastructure.logging.setup import (
    configure_logging,
    get_logger,
    get_module_logger,
    logger,
    _is_test_environment,  # For test backward compatibility
)

__all__ = [
    "configure_logging",
    "get_logger",
    "get_module_logger",
    "logger",
    "_is_test_environment",
]
