"""Pinning tests for the legacy ``/sre incident roles manage`` modal and its submission.

Each test sends ``/sre incident roles manage`` through ``slack_bolt.App.dispatch``,
reads the opened modal from the recorded ``views.open`` call, and submits it with
the callback id, private metadata, block ids and action ids that modal carries,
so no modal-internal id is hard-coded. The external edges are faked: the Slack
Web API, the ``response_url`` post, and the Google Drive service that holds the
incident report document and its metadata. Assertions are on what the channel
sees (role-assignment messages, the channel purpose) and what the modal shows.

The two report-properties tests carry ``legacy_only_`` in their names: the incident's roles
move to the incident record and the report document stops carrying them.
"""

from typing import Any

import pytest

from .conftest import CHANNEL_ID, INCIDENT_CHANNEL_NAME, IncidentSurface, last_view, submission_payload, view_elements

pytestmark = pytest.mark.integration


@pytest.fixture
def surface(incident_surface: IncidentSurface) -> IncidentSurface:
    """The incident surface with the channel's report document in Drive, roles U0OLDIC and U0OLDOL set."""
    incident_surface.google.add_incident_report()
    incident_surface.slack.client.replies["conversations_info"] = {
        "ok": True,
        "channel": {"name": INCIDENT_CHANNEL_NAME, "purpose": {"value": "Checkout outage"}},
    }
    return incident_surface


def open_roles_modal(surface: IncidentSurface) -> dict[str, Any]:
    surface.sre("incident roles manage")
    return last_view(surface.slack.client)


def posted_texts(surface: IncidentSurface) -> list[str]:
    return [call["text"] for call in surface.slack.client.calls_to("chat_postMessage") if call["channel"] == CHANNEL_ID]


def test_roles_command_opens_the_modal_with_the_current_commander_and_lead_selected(surface: IncidentSurface) -> None:
    """The command acks empty and opens a roles modal whose two user pickers start on the stored IC and OL."""
    response = surface.sre("incident roles manage")

    assert (response.status, response.body) == (200, "")
    view = last_view(surface.slack.client)
    assert view["title"]["text"] == "SRE - Roles management"
    assert view["blocks"][0]["text"]["text"] == "Roles for 2026-10-checkout"
    assert {element["placeholder"]["text"]: element["initial_user"] for element in view_elements(view)} == {
        "Select an incident commander": "U0OLDIC",
        "Select an operations lead": "U0OLDOL",
    }


def test_roles_command_leaves_the_pickers_empty_when_no_roles_are_stored(surface: IncidentSurface) -> None:
    """A report document without stored roles opens a modal with no preselected user."""
    for key in ("ic_id", "ol_id"):
        surface.google.drive.entries["F0REPORT"]["appProperties"].pop(key)

    open_roles_modal(surface)

    assert all("initial_user" not in element for element in view_elements(last_view(surface.slack.client)))


def test_roles_command_explains_when_no_report_document_matches_the_channel(surface: IncidentSurface) -> None:
    """With no document named after the channel, no modal opens and the invoker is told to check the channel name."""
    surface.sre("incident roles manage", channel_name="incident-2026-10-unknown")

    assert surface.slack.client.calls_to("views_open") == []
    [message] = surface.slack.responses
    assert message["text"] == (
        "No incident document found for `2026-10-unknown`. Please make sure the channel matches the document name."
    )


@pytest.mark.parametrize("command", ["incident roles", "incident roles show"])
def test_roles_command_without_manage_opens_no_modal(surface: IncidentSurface, command: str) -> None:
    """Only ``manage`` opens the modal; the bare command shows its usage and ``show`` is announced as upcoming."""
    surface.sre(command)

    assert surface.slack.client.calls_to("views_open") == []
    assert len(surface.slack.responses) == 1


def test_submitting_new_roles_announces_each_one_in_the_channel(surface: IncidentSurface) -> None:
    """Changing both pickers posts one assignment message per role and acks the submission empty."""
    view = open_roles_modal(surface)

    response = surface.slack.interaction(submission_payload(view, {"ic_name": "U0NEWIC", "ol_name": "U0NEWOL"}))

    assert (response.status, response.body) == (200, "")
    assert posted_texts(surface) == [
        "<@U0NEWIC> has been assigned as incident commander for this incident.",
        "<@U0NEWOL> has been assigned as operations lead for this incident.",
    ]


def test_submitting_one_changed_role_announces_only_that_role(surface: IncidentSurface) -> None:
    """A role left on its stored user is not announced again."""
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {"ol_name": "U0NEWOL"}))

    assert posted_texts(surface) == ["<@U0NEWOL> has been assigned as operations lead for this incident."]


def test_submitting_unchanged_roles_announces_nothing(surface: IncidentSurface) -> None:
    """Saving the modal as opened posts no assignment message."""
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {}))

    assert posted_texts(surface) == []


def test_submitting_roles_appends_them_to_a_channel_purpose_that_has_none(surface: IncidentSurface) -> None:
    """The channel purpose keeps its text and gains the ``IC: ... / OL: ...`` line."""
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {"ic_name": "U0NEWIC", "ol_name": "U0NEWOL"}))

    assert surface.slack.client.calls_to("conversations_setPurpose") == [
        {"channel": CHANNEL_ID, "purpose": "Checkout outage \nIC: <@U0NEWIC> / OL: <@U0NEWOL>"}
    ]


def test_submitting_roles_replaces_the_roles_line_already_in_the_purpose(surface: IncidentSurface) -> None:
    """An existing ``IC: ... / OL: ...`` line is replaced, not duplicated."""
    surface.slack.client.replies["conversations_info"] = {
        "ok": True,
        "channel": {"purpose": {"value": "Checkout outage\nIC: <@U0OLDIC> / OL: <@U0OLDOL>"}},
    }
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {"ic_name": "U0NEWIC"}))

    [purpose] = surface.slack.client.calls_to("conversations_setPurpose")
    assert purpose["purpose"] == "Checkout outage\n\nIC: <@U0NEWIC> / OL: <@U0OLDOL>"


def test_submitting_roles_cuts_the_purpose_to_slacks_250_characters(surface: IncidentSurface) -> None:
    """A long description is cut so the purpose fits Slack's limit."""
    surface.slack.client.replies["conversations_info"] = {"ok": True, "channel": {"purpose": {"value": "x" * 300}}}
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {"ic_name": "U0NEWIC"}))

    [purpose] = surface.slack.client.calls_to("conversations_setPurpose")
    assert purpose["purpose"] == "x" * 250


# legacy_only: behaviour the rebuild ends


def test_legacy_only_roles_are_written_as_report_document_properties(surface: IncidentSurface) -> None:
    """Saving roles stores both user ids on the report document's Drive metadata.

    The rebuild keeps the roles on the incident record only, so this test is
    deleted with the behaviour.
    """
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {"ic_name": "U0NEWIC", "ol_name": "U0NEWOL"}))

    assert surface.google.drive.properties("F0REPORT") == {"ic_id": "U0NEWIC", "ol_id": "U0NEWOL"}


def test_legacy_only_roles_are_read_back_from_the_report_document_properties(surface: IncidentSurface) -> None:
    """A second ``roles manage`` preselects the users saved on the report document.

    The rebuild reads the roles from the incident record, so this test is
    deleted with the behaviour.
    """
    view = open_roles_modal(surface)
    surface.slack.interaction(submission_payload(view, {"ic_name": "U0NEWIC", "ol_name": "U0NEWOL"}))

    reopened = open_roles_modal(surface)

    assert [element["initial_user"] for element in view_elements(reopened)] == ["U0NEWIC", "U0NEWOL"]
