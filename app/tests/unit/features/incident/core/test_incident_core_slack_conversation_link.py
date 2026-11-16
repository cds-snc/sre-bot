"""The channel link and label the incident list shows for a Slack conversation.

The Slack tenant is stubbed at the settings getter. A stored url wins; otherwise
the legacy ``app_redirect`` deep link, naming the workspace when the tenant has a
team id. The label is the legacy slug (the channel name without ``incident-``),
derived from the title and the declared date; it is display only.
"""

from types import SimpleNamespace

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters import slack
from features.incident.core.domain import ConversationReference
from tests.factories.incident_list_sheet import listed_incident

pytestmark = pytest.mark.unit


def _tenant(monkeypatch: pytest.MonkeyPatch, team_id: str | None, *, present: bool = True) -> None:
    tenant = SimpleNamespace(team_id=team_id) if present else None
    monkeypatch.setattr(slack, "get_slack_settings", lambda: SimpleNamespace(tenant=tenant))


def _conversation(url: str | None = None) -> ConversationReference:
    return ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="C123", url=url)


def test_stored_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reference that carries its link is linked as stored."""
    _tenant(monkeypatch, "T0SLACK")

    assert (
        slack.slack_conversation_link(_conversation("https://x.slack.com/archives/C123")) == "https://x.slack.com/archives/C123"
    )


def test_deep_link_names_the_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a stored url the legacy deep link carries the channel and the tenant's team id."""
    _tenant(monkeypatch, "T0SLACK")

    assert slack.slack_conversation_link(_conversation()) == "https://slack.com/app_redirect?channel=C123&team=T0SLACK"


@pytest.mark.parametrize(("team_id", "present"), [(None, True), ("T1", False)])
def test_deep_link_without_a_team_id(monkeypatch: pytest.MonkeyPatch, team_id: str | None, present: bool) -> None:
    """With no tenant, or a tenant naming only an org, the link names the channel alone."""
    _tenant(monkeypatch, team_id, present=present)

    assert slack.slack_conversation_link(_conversation()) == "https://slack.com/app_redirect?channel=C123"


def test_label_is_the_legacy_slug() -> None:
    """The label is the channel name's slug: the date and the title, lowercased and dashed."""
    assert slack.slack_conversation_label(listed_incident(title="Database outage!")) == "2026-10-01-database-outage"


def test_other_systems_are_refused() -> None:
    """A conversation of another chat system has no Slack link."""
    other = ConversationReference(system=WorkplaceSystem.GOOGLE, tenant="C0", vendor_id="spaces/x")

    with pytest.raises(ValueError, match="Slack"):
        slack.slack_conversation_link(other)
