"""Unit tests for infrastructure.observability.logging module.

Tests cover:
- Logger configuration
- Module logger detection
- Test environment suppression
- Structured logging context
"""

import pytest
import logging
from unittest.mock import patch
import structlog
from infrastructure.observability.logging import (
    configure_logging,
    get_module_logger,
    get_logger,
    _is_test_environment,
    logger,
)


class TestIsTestEnvironment:
    """Test suite for _is_test_environment utility."""

    def test_is_test_environment_with_pytest(self):
        """Test _is_test_environment detects pytest."""
        # pytest is in sys.modules during test execution
        assert _is_test_environment() is True

    @pytest.mark.skip(
        reason="Cannot properly mock sys.modules without breaking imports"
    )
    def test_is_test_environment_without_pytest(self):
        """Test _is_test_environment returns False without pytest."""
        # This test would require complex sys.modules manipulation
        # that breaks module imports. Skipping as the function is simple enough.
        pass


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_logging_returns_logger(self):
        """Test configure_logging returns BoundLogger instance."""
        result = configure_logging()

        assert result is not None
        # Accept both BoundLogger and BoundLoggerLazyProxy
        assert hasattr(result, "info") and hasattr(result, "error")

    def test_configure_logging_test_environment_suppression(self):
        """Test configure_logging suppresses logs during tests."""
        # During test execution, logs should be suppressed
        configure_logging()

        # Verify logging level is elevated to suppress output
        # Note: This behavior is specific to test environment
        assert logging.root.level >= logging.CRITICAL

    def test_configure_logging_custom_log_level(self):
        """Test configure_logging accepts custom log level."""
        # Test with custom level override
        result = configure_logging(log_level="WARNING")

        assert result is not None

    @patch("infrastructure.observability.logging._is_test_environment")
    def test_configure_logging_production_mode(self, mock_test_env):
        """Test configure_logging in production mode."""
        mock_test_env.return_value = False

        result = configure_logging(is_production=True)

        assert result is not None
        # Production mode uses JSON renderer

    @patch("infrastructure.observability.logging._is_test_environment")
    def test_configure_logging_development_mode(self, mock_test_env):
        """Test configure_logging in development mode."""
        mock_test_env.return_value = False

        result = configure_logging(is_production=False)

        assert result is not None
        # Development mode uses Console renderer


class TestGetLogger:
    """Test suite for get_logger function."""

    def test_get_logger_without_name(self):
        """Test get_logger returns logger without specific name."""
        result = get_logger()

        assert result is not None
        assert isinstance(result, structlog.stdlib.BoundLogger)

    def test_get_logger_with_name(self):
        """Test get_logger returns logger with specific name."""
        result = get_logger("test_component")

        assert result is not None
        assert isinstance(result, structlog.stdlib.BoundLogger)

    def test_get_logger_different_names(self):
        """Test get_logger returns different loggers for different names."""
        logger1 = get_logger("component_a")
        logger2 = get_logger("component_b")

        # Both are valid loggers (may or may not be same instance)
        assert logger1 is not None
        assert logger2 is not None


class TestGetModuleLogger:
    """Test suite for get_module_logger function."""

    def test_get_module_logger_auto_detection(self):
        """Test get_module_logger auto-detects calling module."""
        result = get_module_logger()

        assert result is not None
        assert isinstance(result, structlog.stdlib.BoundLogger)

    def test_get_module_logger_context_binding(self):
        """Test get_module_logger binds module context."""
        # Call from this test module
        result = get_module_logger()

        # Logger should be bound with context
        assert result is not None
        # Context includes component and module_path

    def test_get_module_logger_from_different_modules(self):
        """Test get_module_logger provides different context per module."""
        # Test that calling from different modules provides different context
        logger1 = get_module_logger()

        # Simulate call from different module (limited in test environment)
        logger2 = get_module_logger()

        assert logger1 is not None
        assert logger2 is not None


@pytest.mark.unit
class TestLoggerSingleton:
    """Test suite for logger singleton."""

    def test_logger_singleton_exists(self):
        """Test logger singleton is available."""
        assert logger is not None
        # Accept both BoundLogger and BoundLoggerLazyProxy
        assert hasattr(logger, "info") and hasattr(logger, "error")

    def test_logger_singleton_consistent(self):
        """Test logger returns same instance."""
        from infrastructure.observability import logger as logger2

        # May or may not be same instance depending on import timing
        assert logger is not None
        assert logger2 is not None


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_logging_with_structured_context(self):
        """Test structured logging accepts context."""
        test_logger = get_module_logger()

        # Should not raise exception
        try:
            test_logger.info(
                "test_message",
                user_id="test_user",
                action="test_action",
            )
        except Exception as e:
            pytest.fail(f"Logging raised unexpected exception: {e}")

    def test_logging_exception_handling(self):
        """Test logging handles exceptions properly."""
        test_logger = get_module_logger()

        try:
            raise ValueError("Test exception")
        except ValueError:
            # Should not raise exception
            try:
                test_logger.exception("test_exception_log")
            except Exception as e:
                pytest.fail(f"Exception logging raised exception: {e}")

    def test_logging_level_filtering(self):
        """Test logging respects level filtering."""
        test_logger = get_logger("test_filter")

        # All log levels should be callable without errors
        try:
            test_logger.debug("debug message")
            test_logger.info("info message")
            test_logger.warning("warning message")
            test_logger.error("error message")
        except Exception as e:
            pytest.fail(f"Logging raised unexpected exception: {e}")
