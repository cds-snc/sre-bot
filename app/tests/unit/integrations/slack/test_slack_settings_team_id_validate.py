"""Unit tests for the Slack tenant id (SLACK_TEAM_ID) in SlackSettings.

Settings are built from monkeypatched environment variables with the .env
file disabled, so a developer's local file cannot satisfy a check. Building
the settings makes no network call. The id is optional on the slice and only
shape-checked when present; requiring it when the transport runs is the
configuration phase's cross-slice rule (test_server_configuration_slack_transport_rules.py).
The id is opaque (Slack documents no format), so any non-blank value is
accepted. The validated id is exposed as the slice's tenant entry, which
readers use instead of the field.
"""

import pytest
from pydantic import ValidationError

from integrations.slack.settings import SlackSettings, SlackTenant

pytestmark = pytest.mark.unit


@pytest.fixture
def no_team_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SLACK_TEAM_ID", raising=False)


@pytest.mark.usefixtures("no_team_id")
@pytest.mark.parametrize("team_id", ["T0123ABCD", "T0123456789ABCDEFGHIJ"])
def test_accepts_any_non_blank_team_id(monkeypatch: pytest.MonkeyPatch, team_id: str) -> None:
    """No length or character format is assumed, including ids longer than today's."""
    monkeypatch.setenv("SLACK_TEAM_ID", team_id)

    assert team_id == SlackSettings(_env_file=None).team_id  # type: ignore[call-arg]


@pytest.mark.usefixtures("no_team_id")
def test_team_id_is_optional() -> None:
    """With no id, Slack is simply not configured."""
    assert SlackSettings(_env_file=None).team_id is None  # type: ignore[call-arg]


@pytest.mark.usefixtures("no_team_id")
def test_treats_an_empty_team_id_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty value (an unset key in a dotenv file) means the entry is absent."""
    monkeypatch.setenv("SLACK_TEAM_ID", "")

    assert SlackSettings(_env_file=None).team_id is None  # type: ignore[call-arg]


@pytest.mark.usefixtures("no_team_id")
def test_rejects_a_whitespace_team_id_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present entry is shape-checked whether or not the transport runs."""
    monkeypatch.setenv("SLACK_TEAM_ID", "   ")

    with pytest.raises(ValidationError, match="SLACK_TEAM_ID"):
        SlackSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("no_team_id")
def test_keeps_a_present_team_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured workspace id is available whether or not the transport runs."""
    monkeypatch.setenv("SLACK_TEAM_ID", "T0123ABCD")

    assert SlackSettings(_env_file=None).team_id == "T0123ABCD"  # type: ignore[call-arg]


@pytest.mark.usefixtures("no_team_id")
def test_tenant_entry_carries_the_stripped_team_id_as_the_tenant_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry holds the workspace id without surrounding whitespace and names it as Slack's tenant."""
    monkeypatch.setenv("SLACK_TEAM_ID", " T0123ABCD ")

    tenant = SlackSettings(_env_file=None).tenant  # type: ignore[call-arg]

    assert tenant is not None
    assert tenant == SlackTenant(team_id="T0123ABCD")
    assert tenant.tenant_id == "T0123ABCD"


@pytest.mark.usefixtures("no_team_id")
@pytest.mark.parametrize("value", [None, ""])
def test_tenant_entry_is_absent_without_a_team_id(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """An unset or empty id means Slack is not configured, so there is no entry."""
    if value is not None:
        monkeypatch.setenv("SLACK_TEAM_ID", value)

    assert SlackSettings(_env_file=None).tenant is None  # type: ignore[call-arg]


def test_tenant_entry_is_frozen() -> None:
    """The entry is the expected tenant for the process lifetime, so it cannot be reassigned."""
    tenant = SlackTenant(team_id="T0123ABCD")

    with pytest.raises(ValidationError):
        tenant.team_id = "T0OTHER"  # type: ignore[misc]
