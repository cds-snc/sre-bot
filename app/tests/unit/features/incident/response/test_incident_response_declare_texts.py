"""``SlackDeclareTexts``: the declare's words from the catalogue, each post in the languages it is given.

Pure rendering over the real EN and FR catalogues (the directory's conftest loads
them). Assertions are on the text Slack would show: a post has one block per
language in the order given (decisions/languages.md), the product is the
placement's label, SEV0 renders as a severity (value 0 is not unset), and the
report placeholders carry the day, product, channel link, on-call people and status.
"""

from datetime import UTC, datetime

import pytest

from capabilities.oncall.api import Account, OnCallPerson
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.api import ConversationReference, Incident, MessageReference, ReportPlacement
from features.incident.response.entrypoints.slack_declare_texts import SlackDeclareTexts
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT

pytestmark = pytest.mark.unit

PLACEMENT = ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0FORMS", label="Forms")
INCIDENT = Incident(
    id="inc-1",
    title="db down",
    status=IncidentStatus.OPEN,
    declared_by="U0DECLARER",
    declared_at=datetime(2026, 11, 27, 15, 0, tzinfo=UTC),
    security_incident=False,
)
CHANNEL = ConversationReference(
    system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id="C0NEW", url="https://slack.test/C0NEW"
)


def test_the_announcement_names_the_declarer_product_and_channel_in_each_language_in_order() -> None:
    text = SlackDeclareTexts(PLACEMENT, primary="en-US").announcement(INCIDENT, CHANNEL, ("fr-FR", "en-US"))

    assert text.plain_text() == (
        "<@U0DECLARER> a initié un nouvel incident: db down pour Forms dans <#C0NEW>\n"
        "<@U0DECLARER> has kicked off a new incident: db down for Forms in <#C0NEW>"
    )


def test_without_a_placement_the_product_reads_as_none_chosen() -> None:
    texts = SlackDeclareTexts(None, primary="en-US")

    assert texts.topic(INCIDENT) == "Incident: db down / no product"
    assert texts.report_placeholders(INCIDENT, None, ())["{{team}}"] == ""


def test_an_unrated_incident_has_no_severity_warning_and_sev0_has_one() -> None:
    texts = SlackDeclareTexts(PLACEMENT, primary="en-US")

    assert texts.severity_warning(INCIDENT, ("en-US",)) is None
    warning = texts.severity_warning(Incident(**{**INCIDENT.__dict__, "severity": Severity.SEV0}), ("en-US",))
    assert warning is not None and "SEVERITY WARNING: SEV-0" in warning.plain_text()


def test_the_report_placeholders_carry_the_day_product_channel_link_on_call_and_status() -> None:
    on_call = (
        OnCallPerson(email="oncall@example.org", account=None),
        OnCallPerson(email=None, account=Account(platform="slack", tenant=SLACK_TENANT, account_id="U0ROT")),
    )

    values = SlackDeclareTexts(PLACEMENT, primary="en-US").report_placeholders(INCIDENT, CHANNEL, on_call)

    assert values == {
        "{{date}}": "2026-11-27",
        "{{name}}": "db down",
        "{{on-call-names}}": "oncall@example.org, U0ROT",
        "{{team}}": "Forms",
        "{{slack-channel}}": "https://slack.test/C0NEW",
        "{{status}}": "Open",
    }


def test_a_source_alert_without_its_permalink_names_its_channel() -> None:
    texts = SlackDeclareTexts(PLACEMENT, primary="en-US")
    alert = MessageReference(system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, conversation_id="C0ALERTS", message_id="1.2")

    assert texts.source_alert_posted(alert, ("en-US",)).plain_text() == "Source alert: a message in <#C0ALERTS>"
    linked = MessageReference(**{**alert.__dict__, "url": "https://slack.test/p12"})
    assert (
        texts.source_alert_posted(linked, ("en-US",)).plain_text() == "Source alert: <https://slack.test/p12|View original alert>"
    )


def test_single_text_slots_use_the_primary_language() -> None:
    texts = SlackDeclareTexts(PLACEMENT, primary="fr-FR")

    assert texts.topic(INCIDENT) == "Incident : db down / Forms"
    assert texts.report_bookmark() == "Rapport d'incident"
    assert texts.purpose(INCIDENT) == "db down"
