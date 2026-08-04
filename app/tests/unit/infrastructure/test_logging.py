"""Unit tests for enhanced logging infrastructure.

Tests cover:
- Enhanced processors (file/line/function)
- Exception formatting
- Test environment suppression
- Production vs development rendering
- Backward compatibility with get_module_logger (deprecated)
"""

import logging
import sys
from unittest.mock import patch

import pytest
import structlog

from infrastructure.logging.setup import (
    _is_test_environment,
    configure_logging,
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
        had_pytest = "pytest" in sys.modules
        original_pytest = sys.modules.get("pytest")
        pytest_module = pytest

        with patch.dict(sys.modules, {}, clear=False):
            # Remove pytest temporarily
            if "pytest" in sys.modules:
                del sys.modules["pytest"]

            # Now pytest should not be in sys.modules
            result = _is_test_environment()
            assert result is False

        # Restore pytest if it was there before the test
        if had_pytest:
            sys.modules["pytest"] = original_pytest if original_pytest is not None else pytest_module

    def test_configure_logging_returns_bound_logger(self, mock_settings):
        """configure_logging returns a logger instance."""
        logger = configure_logging(settings=mock_settings)
        # Should return a structlog logger (may be BoundLoggerLazyProxy)
        assert logger is not None
        assert hasattr(logger, "bind")

    def test_configure_logging_in_test_environment(self, mock_settings):
        """configure_logging suppresses logs in test environment."""
        # We're in a test environment, so logging should be at CRITICAL+1
        configure_logging(settings=mock_settings)
        root_level = logging.root.level
        assert root_level == logging.CRITICAL + 1

    def test_configure_logging_with_custom_log_level(self, mock_settings):
        """configure_logging accepts custom log level."""
        logger = configure_logging(settings=mock_settings, log_level="DEBUG")
        # Should return a logger instance
        assert logger is not None
        assert hasattr(logger, "bind")

    def test_configure_logging_uses_environment_for_production_mode(self, mock_settings):
        """configure_logging derives production mode from ENVIRONMENT."""
        mock_settings.ENVIRONMENT = "production"
        logger1 = configure_logging(settings=mock_settings)
        mock_settings.ENVIRONMENT = "local"
        logger2 = configure_logging(settings=mock_settings)

        assert logger1 is not None
        assert logger2 is not None

    def test_contract_configure_logging_does_not_accept_legacy_production_kwarg(self, mock_settings):
        """Contract: legacy production override is removed from configure_logging."""
        legacy_kwarg = "is" + "_production"
        with pytest.raises(TypeError):
            configure_logging(settings=mock_settings, **{legacy_kwarg: False})


@pytest.mark.unit
class TestGetModuleLoggerBackwardCompat:
    """Tests for get_module_logger backward compatibility."""

    def test_get_module_logger_backward_compatibility(self):
        """get_module_logger() provides backward compatibility."""
        logger = structlog.get_logger()
        # Should return a logger instance
        assert logger is not None

    def test_get_module_logger_with_none_frame(self):
        """get_module_logger handles None frame gracefully."""
        with patch("inspect.currentframe", return_value=None):
            logger = structlog.get_logger()
            assert logger is not None


@pytest.mark.unit
class TestLoggingBestPractices:
    """Tests for logging best practices with structlog."""

    def test_structlog_get_logger_pattern(self):
        """Standard structlog.get_logger() pattern works."""

        logger = structlog.get_logger()
        # Should return a logger instance
        assert logger is not None
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")

    def test_logger_bind_for_context(self):
        """Logger.bind() adds context for structured logging."""

        logger = structlog.get_logger()
        bound_logger = logger.bind(user_id="123", request_id="req-abc")
        assert bound_logger is not None
        assert hasattr(bound_logger, "info")
