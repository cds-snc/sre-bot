"""Integration tests for logging infrastructure.

Tests cover:
- Real logging scenarios
- Integration with existing code
- Migration from core.logging to infrastructure.observability
- Backward compatibility
"""

import pytest
from infrastructure.observability import get_logger, get_module_logger


@pytest.mark.integration
class TestLoggingIntegration:
    """Integration tests for logging infrastructure."""

    def test_get_logger_logs_with_standard_fields(self):
        """get_logger can log with standard fields."""
        logger = get_logger("test_module")

        # Should not raise when logging
        logger.info(
            "test_event",
            operation="test_operation",
            correlation_id="req-123",
            user_email="test@example.com",
        )

    def test_get_module_logger_logs_with_standard_fields(self):
        """get_module_logger can log with standard fields."""
        logger = get_module_logger()

        # Should not raise when logging
        logger.info(
            "test_event",
            operation="test_operation",
            resource_id="group-123",
            result="success",
        )

    def test_logger_with_metadata_fields(self):
        """Logger can bind metadata fields."""
        logger = get_logger("test").bind(
            correlation_id="req-456",
            user_email="alice@example.com",
            module="groups",
        )

        # Should not raise when logging with bound context
        logger.info(
            "member_added",
            resource_id="eng@example.com",
            result="success",
            provider="google",
        )

    def test_logger_handles_errors_correctly(self):
        """Logger handles error logging with exceptions."""
        logger = get_logger("test")

        try:
            raise ValueError("Test error for logging")
        except ValueError:
            # Should not raise when logging exception
            logger.error("operation_failed", error_message="Test error", exc_info=True)

    def test_logger_with_numeric_fields(self):
        """Logger can log numeric fields (metrics)."""
        logger = get_logger("test")

        logger.info(
            "operation_completed",
            duration_ms=1234,
            api_calls=3,
            retry_count=1,
            success_rate=98.5,
        )

    def test_multiple_loggers_work_independently(self):
        """Multiple logger instances work independently."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both should log without interference
        logger1.info("event1", module="module1")
        logger2.info("event2", module="module2")

    def test_backward_compatibility_get_module_logger(self):
        """get_module_logger provides backward compatibility."""
        # Code using old get_module_logger should still work
        logger = get_module_logger()

        # Should have component and module_path context
        logger.info("legacy_event", action="test")

    def test_logger_with_empty_bind_context(self):
        """Logger with empty bind context still works."""
        logger = get_logger("test").bind()

        logger.info("event_with_empty_context")

    def test_logger_chaining_bind_calls(self):
        """Logger can chain multiple bind calls."""
        logger = (
            get_logger("test")
            .bind(correlation_id="req-789")
            .bind(user_email="bob@example.com")
        )

        logger.info("chained_context_event")

    def test_logger_with_special_characters_in_fields(self):
        """Logger handles special characters in field values."""
        logger = get_logger("test")

        logger.info(
            "event_with_special_chars",
            error_message='Error: "invalid" input\\nfrom user',
            path="/path/to/resource",
            json_data='{"key": "value"}',
        )

    def test_get_logger_called_from_different_modules(self):
        """get_logger works when called from different modules."""
        # This tests the automatic module detection
        logger_here = get_logger()
        assert logger_here is not None

        # In a real scenario, this would be called from different modules
        # The logger would auto-detect the calling module
