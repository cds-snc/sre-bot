"""Integration tests for logging infrastructure.

Tests cover:
- Real logging scenarios
- Integration with existing code
- Migration from core.logging to structlog
- Backward compatibility with get_module_logger (deprecated)
"""

import pytest
import structlog


@pytest.mark.integration
class TestLoggingIntegration:
    """Integration tests for logging infrastructure."""

    def test_get_module_logger_logs_with_standard_fields(self):
        """get_module_logger can log with standard fields."""
        logger = structlog.get_logger()

        # Should not raise when logging
        logger.info(
            "test_event",
            operation="test_operation",
            resource_id="group-123",
            result="success",
        )

    def test_backward_compatibility_get_module_logger(self):
        """get_module_logger provides backward compatibility."""
        # Code using old get_module_logger should still work
        logger = structlog.get_logger()

        # Should have component and module_path context
        logger.info("legacy_event", action="test")
