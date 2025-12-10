"""Enhanced structured logging with improved debugging context.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from infrastructure.observability instead.

This module provides:
- File/line/function information in all logs
- Proper exception formatting with stack traces
- Integration with standard library logging
- Auto-detection of calling module
- Test environment suppression

Migration:
    from infrastructure.logging import get_module_logger  # OLD
    from infrastructure.observability import get_module_logger  # NEW
"""

# Re-export everything from infrastructure.observability for backward compatibility
from infrastructure.observability.logging import (  # noqa: F401
    configure_logging,
    logger,
    get_logger,
    get_module_logger,
    _is_test_environment,
)

__all__ = [
    "configure_logging",
    "logger",
    "get_logger",
    "get_module_logger",
    "_is_test_environment",
]
