"""Unit tests for infrastructure.logging.setup module.

Tests cover:
- configure_logging function
- uvicorn and warnings routed through the root pipeline; UTC timestamps and logger names
- Test logging suppression in test environment
- Recursive redaction installed in the real processor chain (TASK-8)
- The real (non-test-environment) processor-build code path (regression for
  a prod_mode/_prod_mode call-site vs. signature mismatch that only
  surfaced in production, see decisions/observability.md)
"""

import io
import json
import logging
import sys
import warnings
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
        result = configure_logging(mock_settings.environment, LoggingSettings())

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
        configure_logging(mock_settings.environment, LoggingSettings())
        logger = structlog.get_logger()
        logger.info("first_use")
        configure_logging(mock_settings.environment, LoggingSettings())

        with capture_logs() as entries:
            logger.warning("after_reconfigure")

        assert [entry["event"] for entry in entries] == ["after_reconfigure"]

    def test_configure_logging_default_parameters(self, mock_settings):
        """configure_logging works with default parameters."""
        logger = configure_logging(mock_settings.environment, LoggingSettings())

        assert logger is not None

    def test_configure_logging_with_log_level(self, mock_settings):
        """configure_logging accepts log_level parameter."""
        # In test environment, logging is suppressed, but function should still work
        logger = configure_logging(mock_settings.environment, LoggingSettings(), log_level="DEBUG")
        assert logger is not None

        logger = configure_logging(mock_settings.environment, LoggingSettings(), log_level="INFO")
        assert logger is not None

        logger = configure_logging(mock_settings.environment, LoggingSettings(), log_level="WARNING")
        assert logger is not None

    def test_configure_logging_production_mode_from_environment(self, mock_settings):
        """configure_logging derives production mode from ENVIRONMENT."""
        mock_settings.environment = "production"
        logger = configure_logging(mock_settings.environment, LoggingSettings())
        assert logger is not None

        mock_settings.environment = "local"
        logger = configure_logging(mock_settings.environment, LoggingSettings())
        assert logger is not None

    def test_configure_logging_idempotent(self, mock_settings):
        """Multiple configure_logging calls are safe."""
        logger1 = configure_logging(mock_settings.environment, LoggingSettings())
        logger2 = configure_logging(mock_settings.environment, LoggingSettings())

        assert logger1 is not None
        assert logger2 is not None

    def test_configure_logging_suppresses_in_test_env(self, mock_settings):
        """In test environment, root logger level is set high to suppress output."""
        configure_logging(mock_settings.environment, LoggingSettings())

        # In test environment, root logger should be set to suppress output
        root_logger = logging.getLogger()
        # Level should be CRITICAL + 1 (51) to suppress all output
        assert root_logger.level >= logging.CRITICAL


@pytest.mark.unit
class TestLoggingBestPractices:
    """Tests demonstrating structlog best practices."""

    def test_standard_structlog_pattern(self, mock_settings):
        """Standard structlog.get_logger() pattern works."""
        configure_logging(mock_settings.environment, LoggingSettings())

        # This is the recommended pattern
        logger = structlog.get_logger()

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "bind")

    def test_bind_for_context(self, mock_settings):
        """Use .bind() for adding context."""
        configure_logging(mock_settings.environment, LoggingSettings())

        logger = structlog.get_logger()
        log = logger.bind(user_id="123", operation="test")

        assert log is not None
        assert hasattr(log, "info")

    def test_chained_binds(self, mock_settings):
        """Multiple .bind() calls can be chained."""
        configure_logging(mock_settings.environment, LoggingSettings())

        logger = structlog.get_logger()
        log = logger.bind(request_id="req-123")
        log = log.bind(user_id="user-456")

        assert log is not None

    def test_logging_methods_dont_raise(self, mock_settings):
        """Logging methods execute without raising exceptions."""
        configure_logging(mock_settings.environment, LoggingSettings())

        logger = structlog.get_logger()
        log = logger.bind(component="test")

        # None of these should raise (output is suppressed in tests)
        log.debug("debug message", extra="data")
        log.info("info message", key="value")
        log.warning("warning message")
        log.error("error message", error_code="E001")

    def test_exception_logging(self, mock_settings):
        """Exception logging works correctly."""
        configure_logging(mock_settings.environment, LoggingSettings())

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
        logging_settings = LoggingSettings(redaction_extra_keys=("custom_secret",))
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
def production_logging(mock_settings, monkeypatch, process_logging_state) -> Iterator[io.StringIO]:
    """Configure the real production pipeline writing to a buffer; process_logging_state restores the rest."""
    root = logging.getLogger()
    monkeypatch.setattr(logging_setup, "_is_test_environment", lambda: False)
    mock_settings.environment = "production"
    configure_logging(mock_settings.environment, LoggingSettings())
    stream = io.StringIO()
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(stream)
    yield stream


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

    def test_transient_socket_mode_error_renders_as_info(self, production_logging):
        """A Socket Mode broken-pipe ERROR renders as ``"level": "info"``, which the CloudWatch error filter skips."""
        logging.getLogger("slack_sdk.socket_mode").error(
            "on_error invoked (session id: abc, error: BrokenPipeError, message: [Errno 32] Broken pipe)"
        )

        record = json.loads(production_logging.getvalue().strip())
        assert record["level"] == "info"
        assert record["logger"] == "slack_sdk.socket_mode"
        assert record["error_type"] == "BrokenPipeError"
        assert record["socket_mode_transient"] is True

    def test_non_transient_socket_mode_error_still_renders_as_error(self, production_logging):
        """Socket Mode errors outside the transient set keep their ERROR level end to end."""
        logging.getLogger("slack_sdk.socket_mode").error("Failed to retrieve WSS URL: invalid_auth")

        record = json.loads(production_logging.getvalue().strip())
        assert record["level"] == "error"
        assert "socket_mode_transient" not in record


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
    def _reset_structlog(self, process_logging_state):
        yield

    def test_production_mode_builds_processors_without_error(self, mock_settings, monkeypatch):
        """The real code path builds the pipeline in production mode without raising."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
        mock_settings.environment = "production"

        logger = configure_logging(mock_settings.environment, LoggingSettings())

        assert logger is not None
        assert isinstance(_root_renderer(), structlog.processors.JSONRenderer)

    def test_development_mode_builds_processors_without_error(self, mock_settings, monkeypatch):
        """The real code path builds the pipeline in development mode without raising."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
        mock_settings.environment = "local"

        logger = configure_logging(mock_settings.environment, LoggingSettings())

        assert logger is not None
        assert isinstance(_root_renderer(), structlog.dev.ConsoleRenderer)

    def test_production_mode_redacts_through_full_pipeline(self, mock_settings, monkeypatch):
        """Secrets are redacted end-to-end when the production pipeline is built for real."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
        mock_settings.environment = "production"

        configure_logging(mock_settings.environment, LoggingSettings())
        config = structlog.get_config()
        # Drop the JSONRenderer so capture_logs can inspect the event dict directly.
        processors = config["processors"][:-1]

        with capture_logs(processors=processors) as entries:
            logger = structlog.get_logger()
            logger.info("login_attempt", password="hunter2")

        assert entries[0]["password"] == "***REDACTED***"

    def test_root_level_comes_from_the_logging_slice(self, mock_settings, monkeypatch):
        """With no explicit level, the root logger takes LoggingSettings.log_level."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)

        configure_logging(mock_settings.environment, LoggingSettings(log_level="WARNING"))

        assert logging.getLogger().level == logging.WARNING

    def test_explicit_log_level_argument_beats_the_logging_slice(self, mock_settings, monkeypatch):
        """The log_level argument still overrides the configured level."""
        monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)

        configure_logging(
            mock_settings.environment,
            LoggingSettings(log_level="WARNING"),
            log_level="DEBUG",
        )

        assert logging.getLogger().level == logging.DEBUG


def _json_lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _uvicorn_access_record(path: str = "/hook/abc", status: int = 200, method: str = "GET") -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", method, path, "1.1", status),
        None,
    )


@pytest.mark.unit
class TestUvicornRoutedThroughRootPipeline:
    """uvicorn's own loggers render through the same JSON chain as every other record."""

    def test_uvicorn_loggers_lose_their_handlers_and_propagate_to_root(self, production_logging):
        """The four uvicorn loggers end with no handler, propagation on and no level of their own."""
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
            logging.getLogger(name).handlers = [logging.StreamHandler()]
            logging.getLogger(name).propagate = False
            logging.getLogger(name).setLevel(logging.ERROR)

        configure_logging("production", LoggingSettings())

        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
            uvicorn_logger = logging.getLogger(name)
            assert uvicorn_logger.handlers == []
            assert uvicorn_logger.propagate is True
            assert uvicorn_logger.level == logging.NOTSET

    def test_access_record_renders_as_one_json_object_with_logger_and_utc_timestamp(self, production_logging):
        """An access-shaped record is one JSON object carrying level, logger name and a UTC ISO-8601 timestamp."""
        logging.getLogger("uvicorn.access").handle(_uvicorn_access_record("/hook/abc?x=1", 500, "POST"))

        (record,) = _json_lines(production_logging)
        assert record["logger"] == "uvicorn.access"
        assert record["level"] == "info"
        assert record["event"] == '127.0.0.1:5000 - "POST /hook/abc?x=1 HTTP/1.1" 500'
        assert record["timestamp"].endswith("Z")

    def test_uvicorn_error_with_exception_renders_as_exactly_one_line(self, production_logging, capfd):
        """An ERROR with exc_info is one JSON line holding the traceback, with nothing raw on stdout or stderr."""
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logging.getLogger("uvicorn.error").exception("Exception in ASGI application")

        (record,) = _json_lines(production_logging)
        assert record["level"] == "error"
        assert record["logger"] == "uvicorn.error"
        assert "RuntimeError: boom" in record["exception"]
        captured = capfd.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_sensitive_field_is_redacted_on_foreign_and_native_records(self, production_logging):
        """A sensitive-named static field is masked by the same processor on a uvicorn record and on a native event."""
        configure_logging("production", LoggingSettings(), static_fields={"session.id": "abc-123"})
        stream = io.StringIO()
        handler = logging.getLogger().handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        handler.setStream(stream)
        logging.getLogger("uvicorn.error").error("rejected")
        structlog.get_logger().error("rejected")

        foreign, native = _json_lines(stream)
        assert foreign["session.id"] == "***REDACTED***"
        assert native["session.id"] == "***REDACTED***"

    def test_foreign_callsite_fields_point_at_the_emitting_file(self, production_logging):
        """The record's own file and line become code.file.path and code.line.number, not the logging module's."""
        logging.getLogger("uvicorn.error").handle(
            logging.LogRecord("uvicorn.error", logging.ERROR, "/srv/app/vendor/h11_impl.py", 77, "m", None, None)
        )

        (record,) = _json_lines(production_logging)
        assert record["code.file.path"].endswith("h11_impl.py")
        assert record["code.line.number"] == 77

    def test_warnings_render_through_the_pipeline(self, production_logging):
        """A Python warning raised after configuration is one JSON line from the py.warnings logger."""
        warnings.warn("deprecated thing", UserWarning, stacklevel=1)

        (record,) = _json_lines(production_logging)
        assert record["logger"] == "py.warnings"
        assert "deprecated thing" in record["event"]


@pytest.mark.unit
class TestStructlogNativeLines:
    """Structlog-native events carry the caller's logger name and an explicit UTC timestamp."""

    def test_native_event_carries_the_caller_module_as_logger(self, production_logging):
        """A logger from get_logger() without a name is named after the module that created it."""
        logging.getLogger().setLevel(logging.INFO)
        structlog.get_logger().info("native_event")

        (record,) = _json_lines(production_logging)
        assert record["logger"] == __name__
        assert record["timestamp"].endswith("Z")

    def test_explicit_logger_name_is_kept(self, production_logging):
        """A name passed to get_logger() is the logger field."""
        logging.getLogger().setLevel(logging.INFO)
        structlog.get_logger("explicit.name").info("native_event")

        (record,) = _json_lines(production_logging)
        assert record["logger"] == "explicit.name"

    def test_time_stamper_sets_utc_explicitly(self):
        """The timestamp processor is built with utc=True rather than relying on the library default."""
        stampers = [
            item for item in _build_base_processors(LoggingSettings()) if isinstance(item, structlog.processors.TimeStamper)
        ]
        assert len(stampers) == 1
        assert stampers[0].utc is True


@pytest.mark.unit
class TestPytestBranchLeavesProcessAlone:
    """Under pytest configure_logging keeps silencing output and touches nothing else."""

    def test_uvicorn_loggers_and_excepthook_are_untouched(self, process_logging_state):
        """The suppression branch neither clears uvicorn handlers nor replaces sys.excepthook."""
        marker = logging.StreamHandler()
        logging.getLogger("uvicorn").handlers = [marker]
        hook = sys.excepthook

        configure_logging("production", LoggingSettings())

        assert logging.getLogger("uvicorn").handlers == [marker]
        assert sys.excepthook is hook
        assert logging.getLogger().level > logging.CRITICAL


@pytest.mark.unit
class TestBootstrapThenConfigure:
    """The bootstrap pipeline is replaced, never stacked, by the configured one."""

    def test_bootstrap_renders_production_json_at_info_without_identity(self, monkeypatch, process_logging_state):
        """The bootstrap handler is a JSON renderer at INFO with no service identity fields."""
        monkeypatch.setattr(logging_setup, "_is_test_environment", lambda: False)

        logging_setup.configure_bootstrap_logging()

        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(_root_renderer(), structlog.processors.JSONRenderer)
        assert root.level == logging.INFO

    def test_configure_logging_replaces_the_bootstrap_handler_and_adds_identity(self, monkeypatch, process_logging_state):
        """After the real call there is one root handler, and a logger first used afterwards carries the identity."""
        monkeypatch.setattr(logging_setup, "_is_test_environment", lambda: False)
        logging_setup.configure_bootstrap_logging()

        configure_logging("production", LoggingSettings(), static_fields={"service.name": "sre-bot"})
        stream = io.StringIO()
        handler = logging.getLogger().handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        handler.setStream(stream)
        structlog.get_logger("first.used.after").info("after")

        assert len(logging.getLogger().handlers) == 1
        (record,) = _json_lines(stream)
        assert record["service.name"] == "sre-bot"

    def test_bootstrap_is_a_no_op_under_pytest(self):
        """Under pytest the bootstrap call leaves the root handlers as they were."""
        before = logging.getLogger().handlers[:]

        logging_setup.configure_bootstrap_logging()

        assert logging.getLogger().handlers == before
