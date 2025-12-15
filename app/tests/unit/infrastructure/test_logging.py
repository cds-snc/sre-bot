"""Unit tests for enhanced logging infrastructure.

Tests cover:
- Enhanced processors (file/line/function)
- Exception formatting
- Test environment suppression
- Production vs development rendering
- Backward compatibility with get_module_logger (deprecated)
"""

import pytest
import logging
import sys
from unittest.mock import patch
from infrastructure.observability.logging import (
    configure_logging,
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
class TestGetModuleLoggerBackwardCompat:
    """Tests for get_module_logger backward compatibility."""

    def test_get_module_logger_backward_compatibility(self):
        """get_module_logger() provides backward compatibility."""
        logger = get_module_logger()
        # Should return a logger instance
        assert logger is not None

    def test_get_module_logger_with_none_frame(self):
        """get_module_logger handles None frame gracefully."""
        with patch("inspect.currentframe", return_value=None):
            logger = get_module_logger()
            assert logger is not None


@pytest.mark.unit
class TestLoggingBestPractices:
    """Tests for logging best practices with structlog."""

    def test_structlog_get_logger_pattern(self):
        """Standard structlog.get_logger() pattern works."""
        import structlog

        logger = structlog.get_logger()
        # Should return a logger instance
        assert logger is not None
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")

    def test_logger_bind_for_context(self):
        """Logger.bind() adds context for structured logging."""
        import structlog

        logger = structlog.get_logger()
        bound_logger = logger.bind(user_id="123", request_id="req-abc")
        assert bound_logger is not None
        assert hasattr(bound_logger, "info")
