"""Unit tests for the cross-slice Slack rules the configuration phase runs.

The rules join the [slack_transport] slice (whether and how the transport runs)
with the Slack vendor slice (credentials and the tenant entry). The vendor slice
is built with model_construct, so neither the environment nor a .env file can
satisfy a rule; the transport slice is built with explicit values. Failures must
name the missing key and never carry a credential value; the Socket Mode notice
is captured with structlog's capture_logs.
"""

import pytest
from structlog.testing import capture_logs

from contracts.configuration import ConfigurationError
from integrations.slack.settings import SlackSettings, SlackTenant
from server.configuration.host_configuration import validate_slack_transport
from server.slack.settings import SlackTransportSettings

pytestmark = pytest.mark.unit

NOTICE = "slack_signing_secret_not_set_in_socket_mode"
BOT_TOKEN = "xoxb-secret-bot-value"
APP_TOKEN = "xapp-secret-app-value"
SIGNING_SECRET = "secret-signing-value"


def _slack(
    team_id: str | None = "T0TEST",
    bot_token: str = BOT_TOKEN,
    app_token: str | None = APP_TOKEN,
    signing_secret: str | None = None,
) -> SlackSettings:
    tenant = SlackTenant(team_id=team_id) if team_id is not None else None
    return SlackSettings.model_construct(tenant=tenant, bot_token=bot_token, app_token=app_token, signing_secret=signing_secret)


def _transport(enabled: bool = True, socket_mode: bool = True) -> SlackTransportSettings:
    return SlackTransportSettings(enabled=enabled, socket_mode=socket_mode)


def _notices(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return [entry for entry in entries if entry.get("event") == NOTICE]


def test_transport_off_requires_nothing() -> None:
    """With the transport off, an unconfigured workspace and missing credentials boot."""
    with capture_logs() as entries:
        validate_slack_transport(_transport(enabled=False), _slack(team_id=None, bot_token="", app_token=None))

    assert not _notices(entries)


def test_transport_on_without_the_tenant_entry_fails_naming_the_key() -> None:
    """The transport cannot run without knowing its workspace."""
    with pytest.raises(ConfigurationError, match=r"\[slack.tenant\] team_id"):
        validate_slack_transport(_transport(), _slack(team_id=None))


def test_transport_on_without_the_bot_token_fails_naming_the_key() -> None:
    """Every Slack call the transport makes needs the bot token."""
    with pytest.raises(ConfigurationError, match="SLACK__BOT_TOKEN"):
        validate_slack_transport(_transport(), _slack(bot_token=""))


def test_socket_mode_without_the_app_token_fails_naming_the_key() -> None:
    """Socket Mode opens its connection with the app-level token."""
    with pytest.raises(ConfigurationError, match="SLACK__APP_TOKEN"):
        validate_slack_transport(_transport(), _slack(app_token=None))


def test_http_mode_without_the_signing_secret_fails_naming_the_key() -> None:
    """HTTP Events mode verifies every request's signature, so it cannot run without the secret."""
    with pytest.raises(ConfigurationError, match="SLACK__SIGNING_SECRET"):
        validate_slack_transport(_transport(socket_mode=False), _slack(app_token=None))


def test_http_mode_with_every_credential_passes_without_notice() -> None:
    """HTTP Events mode with the signing secret needs no app token and logs no notice."""
    with capture_logs() as entries:
        validate_slack_transport(_transport(socket_mode=False), _slack(app_token=None, signing_secret=SIGNING_SECRET))

    assert not _notices(entries)


def test_production_shape_boots_and_logs_the_notice_once_at_info() -> None:
    """Socket Mode without a signing secret is production's shape: it boots, with one info notice."""
    with capture_logs() as entries:
        validate_slack_transport(_transport(), _slack())

    notices = _notices(entries)
    assert len(notices) == 1
    assert notices[0]["log_level"] == "info"
    assert "socket_mode" in str(notices[0]["detail"])
    assert "SLACK__SIGNING_SECRET" in str(notices[0]["detail"])


def test_socket_mode_with_the_signing_secret_logs_no_notice() -> None:
    """Once the secret is set, switching to HTTP Events mode is ready and nothing is logged."""
    with capture_logs() as entries:
        validate_slack_transport(_transport(), _slack(signing_secret=SIGNING_SECRET))

    assert not _notices(entries)


@pytest.mark.parametrize(
    ("socket_mode", "slack_values"),
    [
        (True, {"team_id": None}),
        (True, {"app_token": None}),
        (False, {}),
    ],
)
def test_failures_and_notices_carry_no_credential_value(socket_mode: bool, slack_values: dict[str, None]) -> None:
    """Neither the raised message nor any log line repeats a token or secret."""
    with capture_logs() as entries, pytest.raises(ConfigurationError) as raised:
        validate_slack_transport(_transport(socket_mode=socket_mode), _slack(**slack_values))

    rendered = str(raised.value) + repr(entries)
    for value in (BOT_TOKEN, APP_TOKEN, SIGNING_SECRET):
        assert value not in rendered
