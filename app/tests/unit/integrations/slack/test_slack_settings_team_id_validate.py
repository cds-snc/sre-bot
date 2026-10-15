"""Unit tests for the Slack tenant id (SLACK_TEAM_ID) in SlackSettings.

Settings are built from monkeypatched environment variables with the .env
file disabled, so a developer's local file cannot satisfy a check. Building
the settings makes no network call. SLACK_ENABLED is the interim transport
switch: switched on, it needs the workspace id; switched off, the id is
optional and only shape-checked when present. The id is opaque (Slack
documents no format), so any non-blank value is accepted.
"""

import pytest
from pydantic import ValidationError

from integrations.slack.settings import SlackSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def transport_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_ENABLED", "true")
    monkeypatch.setenv("SLACK_SOCKET_MODE", "true")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-token")
    monkeypatch.delenv("SLACK_TEAM_ID", raising=False)


@pytest.fixture
def transport_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_ENABLED", "false")
    monkeypatch.delenv("SLACK_TEAM_ID", raising=False)


@pytest.mark.usefixtures("transport_on")
@pytest.mark.parametrize("value", [None, "", "   "])
def test_transport_on_without_a_team_id_fails_naming_the_key(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """The transport cannot run without knowing its workspace, so boot fails naming SLACK_TEAM_ID."""
    if value is not None:
        monkeypatch.setenv("SLACK_TEAM_ID", value)

    with pytest.raises(ValidationError, match="SLACK_TEAM_ID"):
        SlackSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("transport_on")
@pytest.mark.parametrize("team_id", ["T0123ABCD", "T0123456789ABCDEFGHIJ"])
def test_transport_on_accepts_any_non_blank_team_id(monkeypatch: pytest.MonkeyPatch, team_id: str) -> None:
    """No length or character format is assumed, including ids longer than today's."""
    monkeypatch.setenv("SLACK_TEAM_ID", team_id)

    assert team_id == SlackSettings(_env_file=None).TEAM_ID  # type: ignore[call-arg]


@pytest.mark.usefixtures("transport_off")
def test_transport_off_needs_no_team_id() -> None:
    """With the transport off and no id, Slack is simply not configured."""
    assert SlackSettings(_env_file=None).TEAM_ID is None  # type: ignore[call-arg]


@pytest.mark.usefixtures("transport_off")
def test_transport_off_treats_an_empty_team_id_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty value (an unset key in a dotenv file) means the entry is absent."""
    monkeypatch.setenv("SLACK_TEAM_ID", "")

    assert SlackSettings(_env_file=None).TEAM_ID is None  # type: ignore[call-arg]


@pytest.mark.usefixtures("transport_off")
def test_transport_off_rejects_a_whitespace_team_id_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present entry is shape-checked even when the transport is off."""
    monkeypatch.setenv("SLACK_TEAM_ID", "   ")

    with pytest.raises(ValidationError, match="SLACK_TEAM_ID"):
        SlackSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("transport_off")
def test_transport_off_keeps_a_present_team_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured workspace id is available whether or not the transport runs."""
    monkeypatch.setenv("SLACK_TEAM_ID", "T0123ABCD")

    assert SlackSettings(_env_file=None).TEAM_ID == "T0123ABCD"  # type: ignore[call-arg]
