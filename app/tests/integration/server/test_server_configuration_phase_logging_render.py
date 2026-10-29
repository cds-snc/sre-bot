"""Integration tests for logging in the app factory's configuration phase.

load_host_configuration runs for real against a tmp_path holding the real
base.toml and an environment file the test may fill, with the working directory moved there
so no developer .env file is read and every slice cache cleared around each
test. The production pipeline is forced by patching _is_test_environment, and
structlog's logger cache is turned off so module-level loggers do not keep the
production processors into later tests. Output is captured at the file
descriptor level (capfd), because the root handler writes to stderr: every
captured line must parse as JSON, and no line nor the raised error may carry a
token-shaped value that failed validation.
"""

import json
import logging
import traceback
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog

from contracts.configuration import ConfigurationError, uninstall_configuration_files, uninstall_host_info
from features.incident.common.settings import get_incident_core_settings
from infrastructure.configuration.features.sre_ops import get_sre_ops_settings
from infrastructure.directory import get_directory_settings
from infrastructure.logging.settings import get_logging_settings
from infrastructure.security.settings import get_security_settings
from integrations.google_workspace.settings import get_google_workspace_settings
from integrations.slack.settings import get_slack_settings
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from server.configuration import CONFIG_DIR as REAL_CONFIG_DIR
from server.configuration import get_identity_settings, get_server_settings, load_host_configuration
from server.slack.settings import get_slack_transport_settings
from tests.factories.google_service_account import service_account_key

pytestmark = pytest.mark.integration

SECRET = "xoxb-secret-value-0002"
CANARY_CREDENTIAL = "xoxb-canary-credential-7788"
CANARY_NON_PUBLIC = "canary-board-id-0123456789"
REDACTED = "***REDACTED***"
# Names a key-name redaction pattern matches: "auth" in unauthorized_*, "token" in max_output_tokens.
EXPECTED_MASKED = {"aws.unauthorized_codes", "openai.max_output_tokens", "slack.unauthorized_errors"}
# The Fargate runtime splits a line over 16 KB, and Logs Insights extracts at most 200 fields of a JSON event.
LINE_LIMIT_BYTES = 16 * 1024
FIELD_LIMIT = 200

_GETTERS: tuple[Callable[[], Any], ...] = (
    get_identity_settings,
    get_logging_settings,
    get_server_settings,
    get_security_settings,
    get_directory_settings,
    get_sre_ops_settings,
    get_slack_settings,
    get_slack_transport_settings,
    get_google_workspace_settings,
    get_incident_core_settings,
    get_notify_api_key_leak_settings,
)


def _clear_caches() -> None:
    for getter in _GETTERS:
        getter.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _production_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Run the phase as production on the real base file, with no .env file and fresh slices."""
    (tmp_path / "base.toml").write_text((REAL_CONFIG_DIR / "base.toml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "production.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr("server.configuration.loader.CONFIG_DIR", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SLACK_TRANSPORT__ENABLED", raising=False)
    monkeypatch.delenv("SLACK__TENANT__TEAM_ID", raising=False)
    for field in ("bot_token", "user_token", "app_token", "signing_secret"):
        monkeypatch.setenv(f"SLACK__{field.upper()}", "")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", "")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "")
    monkeypatch.setattr("infrastructure.logging.setup._is_test_environment", lambda: False)
    configure = structlog.configure
    monkeypatch.setattr(structlog, "configure", lambda **kw: configure(**{**kw, "cache_logger_on_first_use": False}))
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    _clear_caches()
    yield tmp_path
    root.handlers, root.level = saved_handlers, saved_level
    structlog.reset_defaults()
    uninstall_host_info()
    uninstall_configuration_files()
    _clear_caches()


def _lines(capfd: pytest.CaptureFixture[str]) -> list[str]:
    out, err = capfd.readouterr()
    return [line for line in (out + err).splitlines() if line.strip()]


def _events(lines: list[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in lines]


def _transport_on(directory: Path, extra: str = "") -> None:
    (directory / "production.toml").write_text(f"[slack_transport]\nenabled = true\n{extra}", encoding="utf-8")


def test_configuration_phase_event_renders_as_json_in_production(
    _production_phase: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """The Slack transport rules' socket-mode notice, emitted while slices validate, is one JSON line at info."""
    _transport_on(_production_phase, '[slack.tenant]\nteam_id = "T0001"\n')
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-bot")
    monkeypatch.setenv("SLACK__APP_TOKEN", "xapp-app")
    # The legacy incident handlers need Google Workspace while the transport is on.
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C03abc123")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", service_account_key())

    load_host_configuration()

    events = _events(_lines(capfd))
    notices = [event for event in events if event["event"] == "slack_signing_secret_not_set_in_socket_mode"]
    assert len(notices) == 1
    assert notices[0]["level"] == "info"


def test_logging_is_configured_before_any_other_slice_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    """configure_logging runs with the environment and the [logging] slice before the [server] slice builds."""
    order: list[str] = []
    calls: list[tuple[Any, ...]] = []

    def record_logging(*args: Any, **kwargs: Any) -> None:
        order.append("logging")
        calls.append(args)

    def record_server() -> Any:
        order.append("server")
        return get_server_settings()

    monkeypatch.setattr("server.configuration.host_configuration.configure_logging", record_logging)
    monkeypatch.setattr("server.configuration.host_configuration.get_server_settings", record_server)

    load_host_configuration()

    assert order[:2] == ["logging", "server"]
    assert calls[0] == ("production", get_logging_settings())


def test_invalid_slice_logs_one_critical_event_and_fails_without_the_value(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """A bad [server] value logs configuration_invalid once at critical, naming the key; the value appears nowhere."""
    monkeypatch.setenv("SERVER__WEBHOOK_MAX_BODY_BYTES", SECRET)

    with pytest.raises(ConfigurationError) as raised:
        load_host_configuration()

    lines = _lines(capfd)
    events = _events(lines)
    invalid = [event for event in events if event["event"] == "configuration_invalid"]
    assert len(invalid) == 1
    assert invalid[0]["level"] == "critical"
    assert "webhook_max_body_bytes" in invalid[0]["error"]
    assert invalid[0]["error"] == str(raised.value)
    assert SECRET not in "\n".join(lines)
    assert SECRET not in "".join(traceback.format_exception(raised.value))


def test_transport_on_without_the_tenant_entry_fails_without_the_token(
    _production_phase: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """The transport switched on without the Slack tenant entry fails naming its key, with the tokens absent from the error and the log."""
    _transport_on(_production_phase)
    monkeypatch.setenv("SLACK__BOT_TOKEN", SECRET)
    monkeypatch.setenv("SLACK__APP_TOKEN", "xapp-app")

    with pytest.raises(ConfigurationError, match=r"\[slack.tenant\] team_id") as raised:
        load_host_configuration()

    lines = _lines(capfd)
    assert [event["event"] for event in _events(lines)].count("configuration_invalid") == 1
    assert SECRET not in "\n".join(lines)
    assert SECRET not in "".join(traceback.format_exception(raised.value))


def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    (summary,) = [event for event in events if event["event"] == "configuration_summary"]
    return summary


def _slice_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {event["slice"]: event for event in events if event["event"] == "configuration_slice"}


def _flattened_fields(value: Any) -> int:
    """Count leaves the way Logs Insights flattens JSON: nested keys and list positions each become a field."""
    if isinstance(value, dict):
        return sum(_flattened_fields(member) for member in value.values()) or 1
    if isinstance(value, list):
        return sum(_flattened_fields(member) for member in value) or 1
    return 1


def test_the_summary_is_one_json_event_with_names_only_for_files(
    _production_phase: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """configuration_summary closes the phase at info with file names, a hash and the slices, each logged on its own."""
    load_host_configuration()

    events = _events(_lines(capfd))
    summary = _summary(events)
    assert [event["event"] for event in events][-1] == "configuration_summary"
    assert set(_slice_events(events)) == set(summary["slices"])
    assert summary["level"] == "info"
    assert summary["phase"] == "configuration"
    assert "environment" not in summary
    assert summary["files"] == ["base.toml", "production.toml"]
    assert len(summary["config_hash"]) == 64
    assert set(summary["slices"]) >= {"logging", "server", "security", "slack", "google_workspace"}


def test_key_name_redaction_masks_only_the_known_names_and_never_a_withheld_state(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Section and shown-field names are dict keys, so a name matching a redaction pattern is masked.

    Every masked name is one the unit test over all slices pins; withheld names are list
    members, so set and unset survive the pipeline.
    """
    load_host_configuration()

    sections = _slice_events(_events(_lines(capfd)))
    masked = {
        f"{table}.{name}"
        for table, section in sections.items()
        for name, value in section.get("values", {}).items()
        if value == REDACTED
    }
    assert "slack.unauthorized_errors" in masked
    assert masked <= EXPECTED_MASKED
    assert "bot_token" in sections["slack"]["unset"]


def test_a_canary_credential_appears_nowhere_and_a_non_public_value_only_as_its_tail(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """A set Slack bot credential logs as state only; a set non-public board id logs as state and its last four characters."""
    monkeypatch.setenv("SLACK__TENANT__TEAM_ID", "T0001")
    monkeypatch.setenv("SLACK__BOT_TOKEN", CANARY_CREDENTIAL)
    monkeypatch.setenv("INCIDENT_CORE__FOLDER_ID", CANARY_NON_PUBLIC)

    load_host_configuration()

    lines = _lines(capfd)
    sections = _slice_events(_events(lines))
    output = "\n".join(lines)
    assert CANARY_CREDENTIAL not in output
    assert CANARY_NON_PUBLIC not in output
    assert "bot_token" in sections["slack"]["set"]
    assert sections["incident_core"]["partial"]["folder_id"] == CANARY_NON_PUBLIC[-4:]


def test_every_summary_line_fits_the_runtime_buffer_and_the_query_field_limit(capfd: pytest.CaptureFixture[str]) -> None:
    """A line over 16 KB arrives split and unparseable, and fields past 200 are not queryable, so each event stays under both."""
    load_host_configuration()

    lines = [line for line in _lines(capfd) if '"configuration_s' in line]
    assert len(lines) > 1
    for line in lines:
        assert len(line.encode("utf-8")) < LINE_LIMIT_BYTES
        assert _flattened_fields(json.loads(line)) < FIELD_LIMIT


def test_the_service_identity_rides_every_record_without_an_event_of_its_own(capfd: pytest.CaptureFixture[str]) -> None:
    """Every record carries the four resource attributes, so no separate identity event is logged."""
    load_host_configuration()

    events = _events(_lines(capfd))
    assert "service_identity" not in {event["event"] for event in events}
    for event in events:
        assert event["deployment.environment.name"] == "production"
        assert {"service.name", "service.version", "service.instance.id"} <= set(event)
    assert len({event["service.instance.id"] for event in events}) == 1


def test_an_invalid_slice_logs_only_configuration_invalid_and_no_summary(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """A boot that fails validation reports the failure and never a summary of a half-validated set."""
    monkeypatch.setenv("SERVER__WEBHOOK_MAX_BODY_BYTES", SECRET)

    with pytest.raises(ConfigurationError):
        load_host_configuration()

    names = [event["event"] for event in _events(_lines(capfd))]
    assert "configuration_invalid" in names
    assert "configuration_summary" not in names
