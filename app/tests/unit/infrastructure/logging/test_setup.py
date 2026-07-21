"""Unit tests for infrastructure.logging.setup module.

Tests cover:
- configure_logging function
- Test logging suppression in test environment
"""

import logging

import pytest
import structlog

from infrastructure.logging.setup import (
    _is_test_environment,
    configure_logging,
)


@pytest.mark.unit
class TestIsTestEnvironment:
    """Test suite for _is_test_environment helper."""

    def test_detects_pytest_in_sys_modules(self):
        """Returns True when pytest is in sys.modules."""
        # pytest is running these tests, so it's in sys.modules
        assert _is_test_environment() is True

    def test_returns_true_during_test_run(self):
        """During test execution, should always return True."""
        result = _is_test_environment()
        assert result is True


@pytest.mark.unit
class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_logging_returns_bound_logger(self, mock_settings):
        """configure_logging returns a BoundLogger instance."""
        result = configure_logging(settings=mock_settings)

        assert result is not None
        assert hasattr(result, "info")
        assert hasattr(result, "debug")
        assert hasattr(result, "warning")
        assert hasattr(result, "error")

    def test_configure_logging_default_parameters(self, mock_settings):
        """configure_logging works with default parameters."""
        logger = configure_logging(settings=mock_settings)

        assert logger is not None

    def test_configure_logging_with_log_level(self, mock_settings):
        """configure_logging accepts log_level parameter."""
        # In test environment, logging is suppressed, but function should still work
        logger = configure_logging(settings=mock_settings, log_level="DEBUG")
        assert logger is not None

        logger = configure_logging(settings=mock_settings, log_level="INFO")
        assert logger is not None

        logger = configure_logging(settings=mock_settings, log_level="WARNING")
        assert logger is not None

    def test_configure_logging_production_mode_from_environment(self, mock_settings):
        """configure_logging derives production mode from ENVIRONMENT."""
        mock_settings.ENVIRONMENT = "production"
        logger = configure_logging(settings=mock_settings)
        assert logger is not None

        mock_settings.ENVIRONMENT = "local"
        logger = configure_logging(settings=mock_settings)
        assert logger is not None

    def test_configure_logging_idempotent(self, mock_settings):
        """Multiple configure_logging calls are safe."""
        logger1 = configure_logging(settings=mock_settings)
        logger2 = configure_logging(settings=mock_settings)

        assert logger1 is not None
        assert logger2 is not None

    def test_configure_logging_suppresses_in_test_env(self, mock_settings):
        """In test environment, root logger level is set high to suppress output."""
        configure_logging(settings=mock_settings)

        # In test environment, root logger should be set to suppress output
        root_logger = logging.getLogger()
        # Level should be CRITICAL + 1 (51) to suppress all output
        assert root_logger.level >= logging.CRITICAL


@pytest.mark.unit
class TestLoggingBestPractices:
    """Tests demonstrating structlog best practices."""

    def test_standard_structlog_pattern(self, mock_settings):
        """Standard structlog.get_logger() pattern works."""
        configure_logging(settings=mock_settings)

        # This is the recommended pattern
        logger = structlog.get_logger()

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "bind")

    def test_bind_for_context(self, mock_settings):
        """Use .bind() for adding context."""
        configure_logging(settings=mock_settings)

        logger = structlog.get_logger()
        log = logger.bind(user_id="123", operation="test")

        assert log is not None
        assert hasattr(log, "info")

    def test_chained_binds(self, mock_settings):
        """Multiple .bind() calls can be chained."""
        configure_logging(settings=mock_settings)

        logger = structlog.get_logger()
        log = logger.bind(request_id="req-123")
        log = log.bind(user_id="user-456")

        assert log is not None

    def test_logging_methods_dont_raise(self, mock_settings):
        """Logging methods execute without raising exceptions."""
        configure_logging(settings=mock_settings)

        logger = structlog.get_logger()
        log = logger.bind(component="test")

        # None of these should raise (output is suppressed in tests)
        log.debug("debug message", extra="data")
        log.info("info message", key="value")
        log.warning("warning message")
        log.error("error message", error_code="E001")

    def test_exception_logging(self, mock_settings):
        """Exception logging works correctly."""
        configure_logging(settings=mock_settings)

        logger = structlog.get_logger()

        try:
            raise ValueError("test error")
        except ValueError:
            # Should not raise
            logger.exception("An error occurred")
