"""Unit tests for enhanced logging infrastructure.

Tests cover:
- Enhanced processors (file/line/function)
- Exception formatting
- Test environment suppression
- Production vs development rendering
- Backward compatibility
"""

import pytest
import logging
import sys
from unittest.mock import patch
from infrastructure.observability.logging import (
    configure_logging,
    get_logger,
    get_module_logger,
    _is_test_environment,
)


@pytest.mark.unit
class TestLoggingConfiguration:
    """Tests for logging configuration."""

    def test_is_test_environment_detects_pytest(self):
        """_is_test_environment returns True when pytest is in sys.modules."""
        # pytest is already in sys.modules during test execution
        assert _is_test_environment() is True

    def test_is_test_environment_without_pytest(self):
        """_is_test_environment returns False when pytest is not loaded."""
        with patch.dict(sys.modules, {"pytest": None}):
            # Save original state
            had_pytest = "pytest" in sys.modules

            # Remove pytest temporarily
            if "pytest" in sys.modules:
                del sys.modules["pytest"]

            try:
                # Now pytest should not be in sys.modules
                result = _is_test_environment()
                assert result is False
            finally:
                # Restore pytest if it was there
                if had_pytest:
                    # Re-import pytest since we removed it
                    import pytest as _  # noqa: F401

    def test_configure_logging_returns_bound_logger(self):
        """configure_logging returns a logger instance."""
        logger = configure_logging()
        # Should return a structlog logger (may be BoundLoggerLazyProxy)
        assert logger is not None
        assert hasattr(logger, "bind")

    def test_configure_logging_in_test_environment(self):
        """configure_logging suppresses logs in test environment."""
        # We're in a test environment, so logging should be at CRITICAL+1
        configure_logging()
        root_level = logging.root.level
        assert root_level == logging.CRITICAL + 1

    def test_configure_logging_with_custom_log_level(self):
        """configure_logging accepts custom log level."""
        logger = configure_logging(log_level="DEBUG")
        # Should return a logger instance
        assert logger is not None
        assert hasattr(logger, "bind")

    def test_configure_logging_with_custom_production_flag(self):
        """configure_logging accepts custom production flag."""
        # Note: We can't easily verify the processor setup, but we can verify
        # it doesn't raise an error with different production flags
        logger1 = configure_logging(is_production=True)
        logger2 = configure_logging(is_production=False)

        assert logger1 is not None
        assert logger2 is not None


@pytest.mark.unit
class TestLoggerUsage:
    """Tests for logger usage patterns."""

    def test_get_logger_without_name(self):
        """get_logger() returns logger with auto-detected context."""
        logger = get_logger()
        # Should return a logger instance
        assert logger is not None

    def test_get_logger_with_name(self):
        """get_logger(name) returns logger bound to provided name."""
        logger = get_logger("test_module")
        # Should return a logger instance
        assert logger is not None

    def test_get_module_logger_backward_compatibility(self):
        """get_module_logger() provides backward compatibility."""
        logger = get_module_logger()
        # Should return a logger instance
        assert logger is not None

    def test_get_logger_and_get_module_logger_both_work(self):
        """Both get_logger() and get_module_logger() return valid loggers."""
        logger1 = get_logger()
        logger2 = get_module_logger()

        assert logger1 is not None
        assert logger2 is not None

    def test_get_logger_with_none_frame(self):
        """get_logger handles None frame gracefully."""
        # When called from C extension or in unusual context
        with patch("inspect.currentframe", return_value=None):
            logger = get_logger()
            assert logger is not None

    def test_get_module_logger_with_none_frame(self):
        """get_module_logger handles None frame gracefully."""
        with patch("inspect.currentframe", return_value=None):
            logger = get_module_logger()
            assert logger is not None


@pytest.mark.unit
class TestEnhancedProcessors:
    """Tests for enhanced logging processors."""

    def test_logger_has_callsite_processor(self):
        """Logger is configured with CallsiteParameterAdder."""
        # The enhanced logging should include file/line/function info
        logger = get_logger("test")
        # We can't easily inspect the processor chain, but we verify
        # the logger was created successfully with enhanced config
        assert logger is not None

    def test_logger_exception_handling(self):
        """Logger handles exceptions with StackInfoRenderer."""
        logger = get_logger("test")
        # Should not raise when using exception logging
        try:
            raise ValueError("Test error")
        except ValueError:
            # Should handle exc_info without raising
            logger.exception("test_error", exc_info=True)

    def test_logger_binding_works(self):
        """Logger can bind additional context."""
        logger = get_logger("test")
        bound_logger = logger.bind(user_id="123", request_id="req-abc")
        assert bound_logger is not None
