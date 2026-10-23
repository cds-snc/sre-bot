"""Integration tests for logging in the app factory's configuration phase.

load_host_configuration runs for real against a tmp_path holding the real
base.toml and an empty environment file, with the working directory moved there
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
from infrastructure.configuration.features.sre_ops import get_sre_ops_settings
from infrastructure.directory import get_directory_settings
from infrastructure.logging.settings import get_logging_settings
from infrastructure.security.settings import get_security_settings
from integrations.google_workspace.settings import get_google_workspace_settings
from integrations.slack.settings import get_slack_settings
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from server.configuration import CONFIG_DIR as REAL_CONFIG_DIR
from server.configuration import get_identity_settings, get_server_settings, load_host_configuration

pytestmark = pytest.mark.integration

SECRET = "xoxb-secret-value-0002"

_GETTERS: tuple[Callable[[], Any], ...] = (
    get_identity_settings,
    get_logging_settings,
    get_server_settings,
    get_security_settings,
    get_directory_settings,
    get_sre_ops_settings,
    get_slack_settings,
    get_google_workspace_settings,
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
    monkeypatch.setenv("SLACK_ENABLED", "false")
    monkeypatch.delenv("SLACK_TEAM_ID", raising=False)
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "")
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)
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


def test_configuration_phase_event_renders_as_json_in_production(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """The Slack slice's socket-mode notice, emitted while slices validate, is one JSON line at info."""
    monkeypatch.setenv("SLACK_ENABLED", "true")
    monkeypatch.setenv("SLACK_SOCKET_MODE", "true")
    monkeypatch.setenv("SLACK_TEAM_ID", "T0001")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-bot")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-app")

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


def test_invalid_vendor_slice_on_plain_settings_fails_without_the_token(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """A vendor slice not yet on the files fails naming its key, with its tokens absent from the error and the log."""
    monkeypatch.setenv("SLACK_ENABLED", "true")
    monkeypatch.setenv("SLACK_BOT_TOKEN", SECRET)
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-app")

    with pytest.raises(ConfigurationError, match="SLACK_TEAM_ID") as raised:
        load_host_configuration()

    lines = _lines(capfd)
    assert [event["event"] for event in _events(lines)].count("configuration_invalid") == 1
    assert SECRET not in "\n".join(lines)
    assert SECRET not in "".join(traceback.format_exception(raised.value))
