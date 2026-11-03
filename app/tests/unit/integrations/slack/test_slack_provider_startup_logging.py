"""Unit tests for the Slack provider's startup log levels.

The Bolt bootstrap and Socket Mode handler are replaced with fakes so ``initialize_app``
runs unchanged under structlog's capture_logs. The transport phase logs one info
event, slack_app_initialized, with the registered command count; construction and
per-item lines are debug.
"""

from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider

pytestmark = pytest.mark.unit


class _BoltApp:
    client = object()

    def command(self, command: str):
        return lambda listener: listener


@pytest.fixture
def bolt_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "integrations.slack.provider.LegacySlackBootstrap", lambda: SimpleNamespace(create_app=lambda **_: _BoltApp())
    )
    monkeypatch.setattr("integrations.slack.provider.SocketModeHandler", lambda app, token, logger=None: SimpleNamespace(app=app))


def _provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
    return SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())


@pytest.mark.usefixtures("bolt_app")
def test_initializing_the_app_logs_one_info_event_with_the_command_count() -> None:
    """slack_app_initialized is the only info event of an initialisation, named for the transport phase."""
    with capture_logs() as entries:
        provider = _provider()
        provider.initialize_app()

    info = [entry for entry in entries if entry["log_level"] == "info"]
    assert [entry["event"] for entry in info] == ["slack_app_initialized"]
    assert info[0]["phase"] == "slack_transport"
    assert info[0]["commands"] == 0
    assert {"slack_provider_initialized", "initializing_slack_app", "socket_mode_handler_prepared"} <= {
        entry["event"] for entry in entries if entry["log_level"] == "debug"
    }
