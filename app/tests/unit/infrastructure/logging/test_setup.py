"""Unit tests for infrastructure.logging.setup module.

Tests cover:
- configure_logging function
- Test logging suppression in test environment
- Recursive redaction installed in the real processor chain (TASK-8)
- The real (non-test-environment) processor-build code path (regression for
  a prod_mode/_prod_mode call-site vs. signature mismatch that only
  surfaced in production, see decisions/observability.md)
"""

import io
import json
import logging
from collections.abc import Iterator

import pytest
import structlog
from structlog.testing import capture_logs

from infrastructure.logging import setup as logging_setup
from infrastructure.logging.settings import LoggingSettings
from infrastructure.logging.setup import (
    _build_base_processors,
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

    def test_capture_logs_reaches_a_logger_used_before_a_reconfigure(self, mock_settings):
        """A long-lived logger used under one configuration is still captured after configure_logging runs again.

        Mirrors a module-level logger that first logs during one app lifespan and is later
        asserted on with capture_logs after another lifespan has reconfigured structlog.
        """
        configure_logging(settings=mock_settings)
        logger = structlog.get_logger()
        logger.info("first_use")
        configure_logging(settings=mock_settings)

        with capture_logs() as entries:
            logger.warning("after_reconfigure")

        assert [entry["event"] for entry in entries] == ["after_reconfigure"]

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


@pytest.mark.unit
class TestPipelineRedaction:
    """Pipeline-level tests for the recursive redaction processor (TASK-8, SEC-7).

    These exercise the real ordered processor chain built by
    ``_build_base_processors`` (contextvars merge -> log level -> timestamp ->
    callsite adder -> otel conventions -> exception formatting -> redaction),
    not just ``mask_sensitive_data`` in isolation.
    """

    def test_pipeline_redacts_nested_sensitive_value(self):
        """AC#1: {"config": {"api_token": "x"}} renders with the token redacted."""
        processors = _build_base_processors(logging_settings=LoggingSettings())

        with capture_logs(processors=processors) as entries:
            logger = structlog.get_logger()
            logger.info("config_loaded", config={"api_token": "x"})

        assert len(entries) == 1
        assert entries[0]["config"]["api_token"] == "***REDACTED***"

    def test_pipeline_redaction_extra_keys_extend_defaults(self):
        """AC#3: redaction_extra_keys extends the deny-list through the real chain."""
        logging_settings = LoggingSettings(REDACTION_EXTRA_KEYS=("custom_secret",))
        processors = _build_base_processors(logging_settings=logging_settings)

        with capture_logs(processors=processors) as entries:
            logger = structlog.get_logger()
            logger.info(
                "event_with_custom_field",
                custom_secret="squirrel",
                password="hunter2",
            )

        assert len(entries) == 1
        assert entries[0]["custom_secret"] == "***REDACTED***"
        assert entries[0]["password"] == "***REDACTED***"


def _root_renderer() -> object:
    """Return the final renderer of the root handler's structlog formatter."""
    formatter = logging.getLogger().handlers[0].formatter
    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)
    return formatter.processors[-1]


@pytest.fixture
def production_logging(mock_settings, monkeypatch) -> Iterator[io.StringIO]:
    """Configure the real production pipeline writing to a buffer, then restore root logging and structlog."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_config = structlog.get_config()
    monkeypatch.setattr(logging_setup, "_is_test_environment", lambda: False)
    monkeypatch.setattr(logging_setup, "get_logging_settings", LoggingSettings)
    mock_settings.ENVIRONMENT = "production"
    configure_logging(settings=mock_settings)
    stream = io.StringIO()
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(stream)
    yield stream
    root.handlers, root.level = saved_handlers, saved_level
    structlog.configure(**saved_config)


@pytest.mark.unit
class TestStdlibLoggingBridge:
    """Third-party stdlib loggers render through the structlog JSON pipeline in production."""

    def test_stdlib_exception_renders_as_one_json_line_with_level_and_logger(self, production_logging):
        """A third-party stdlib ``logger.exception`` becomes a single JSON object carrying level, logger and traceback.

        Uses a logger name no other test configures; Bolt pins its own loggers' levels when an App is built.
        """
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logging.getLogger("third_party.sdk").exception("Failed to run listener function")

        lines = production_logging.getvalue().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["level"] == "error"
        assert record["logger"] == "third_party.sdk"
        assert record["event"] == "Failed to run listener function"
        assert "RuntimeError: boom" in record["exception"]

    def test_structlog_events_still_render_as_redacted_json(self, production_logging):
        """Native structlog events keep their fields and redaction after moving rendering to the handler."""
        structlog.get_logger().error("structlog_event", api_token="secret")

        record = json.loads(production_logging.getvalue().strip())
        assert record["event"] == "structlog_event"
        assert record["level"] == "error"
        assert record["api_token"] == "***REDACTED***"


@pytest.mark.unit
class TestConfigureLoggingRealCodePath:
    """Exercises configure_logging's non-test-environment branch.

    ``configure_logging`` short-circuits to a minimal suppressed pipeline
    whenever pytest is detected in sys.modules, which means the call to
    ``_build_base_processors`` is never reached by any test running under
    ``make test``. That let a call-site/signature mismatch (calling with
    ``prod_mode=`` a function defined with ``_prod_mode``) reach production
    while the full suite stayed green. These tests patch ``_is_test_environment``
    to force the real branch, so the same class of bug fails CI immediately.
    """

    @pytest.fixture(autouse=True)
    def _reset_structlog(self):
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        yield
        root.handlers, root.level = saved_handlers, saved_level
        structlog.reset_defaults()

    def test_production_mode_builds_processors_without_error(self, mock_settings, monkeypatch):
        """The real code path builds the pipeline in production mode without raising."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
        mock_settings.ENVIRONMENT = "production"

        logger = configure_logging(settings=mock_settings)

        assert logger is not None
        assert isinstance(_root_renderer(), structlog.processors.JSONRenderer)

    def test_development_mode_builds_processors_without_error(self, mock_settings, monkeypatch):
        """The real code path builds the pipeline in development mode without raising."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
        mock_settings.ENVIRONMENT = "local"

        logger = configure_logging(settings=mock_settings)

        assert logger is not None
        assert isinstance(_root_renderer(), structlog.dev.ConsoleRenderer)

    def test_production_mode_redacts_through_full_pipeline(self, mock_settings, monkeypatch):
        """Secrets are redacted end-to-end when the production pipeline is built for real."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
        mock_settings.ENVIRONMENT = "production"

        configure_logging(settings=mock_settings)
        config = structlog.get_config()
        # Drop the JSONRenderer so capture_logs can inspect the event dict directly.
        processors = config["processors"][:-1]

        with capture_logs(processors=processors) as entries:
            logger = structlog.get_logger()
            logger.info("login_attempt", password="hunter2")

        assert entries[0]["password"] == "***REDACTED***"
