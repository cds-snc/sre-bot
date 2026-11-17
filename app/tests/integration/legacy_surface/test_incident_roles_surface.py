"""Pinning tests for ``/sre incident roles manage`` and its modal submission.

Each test sends ``/sre incident roles manage`` through ``slack_bolt.App.dispatch``,
and the provider routes it to the rebuilt ``incident.response`` plugin
(TASK-145.8.5.1). The opened modal is read from the recorded ``views.open`` call
and submitted with the callback id, private metadata, block ids and action ids
that modal carries. Assertions are on what the channel sees (role-assignment
messages, the channel purpose) and what the modal shows.

The fixture is rewired to the target's fakes (decisions/migration.md step 4): the
plugin's scope opener resolves an in-memory record store holding the channel's
legacy incident and its report, the response providers return the core in-memory
conversation (open, with the purpose ``Checkout outage``) and a legacy roles
reader seeded with the roles U0OLDIC and U0OLDOL the report carried in Drive.
The behaviour the rebuild ended (the roles written as the report document's Drive
properties, the ``roles show`` stub) was pinned in ``test_legacy_only_*`` tests,
deleted with it; the new behaviour is tested under
tests/integration/features/incident/response/.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation, InMemoryLegacyRolesReader
from features.incident.core.api import ReportReference
from features.incident.response import plugin, providers
from tests.factories.i18n import load_plugin_catalogues, reset_translation_service
from tests.factories.incident import (
    GOOGLE_TENANT,
    SLACK_TENANT,
    SwitchableRecordStore,
    incident_scopes,
    seed_legacy_incident,
    slack_conversation,
)

from .conftest import (
    CHANNEL_ID,
    REPORT_DOCUMENT_ID,
    REPORT_URL,
    IncidentSurface,
    last_view,
    submission_payload,
    view_elements,
)

pytestmark = pytest.mark.integration

IC_BLOCK = "incident.response.roles.incident_commander"
OL_BLOCK = "incident.response.roles.operations_lead"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=REPORT_DOCUMENT_ID)
INCIDENT_ID = "inc-1"


@dataclass
class RolesSurface:
    """The incident surface read back in domain terms: the channel's posts and purpose, the modal, the replies."""

    surface: IncidentSurface
    records: SwitchableRecordStore
    conversations: InMemoryIncidentConversation
    legacy: InMemoryLegacyRolesReader

    @property
    def slack(self) -> Any:
        return self.surface.slack

    def sre(self, text: str, **fields: str) -> Any:
        return self.surface.sre(text, **fields)

    def purpose(self) -> str | None:
        """The channel purpose the incident's channel carries."""
        return self.conversations.purpose_of(slack_conversation(CHANNEL_ID))


_TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}


@pytest.fixture
def unseeded(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> Iterator[RolesSurface]:
    """The incident surface with the response plugin's commands registered over the core in-memory fakes, no incident yet.

    The channel is open with the bot a member and its purpose is ``Checkout outage``; the legacy roles
    reader holds U0OLDIC and U0OLDOL for the channel's report. The response catalogue is loaded as the
    lifespan loads it.
    """
    records = SwitchableRecordStore()
    conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
    conversations.seed_purpose(slack_conversation(CHANNEL_ID), "Checkout outage")
    legacy = InMemoryLegacyRolesReader()
    legacy.seed(REPORT, {IncidentRole.INCIDENT_COMMANDER: "U0OLDIC", IncidentRole.OPERATIONS_LEAD: "U0OLDOL"})
    monkeypatch.setattr(providers, "incident_conversation", lambda: conversations)
    monkeypatch.setattr(providers, "legacy_roles_reader", lambda: legacy)

    incident_surface.provider.set_scope_opener(incident_scopes(records, tenants=_TENANTS))
    plugin.register_slack_commands(registrar=incident_surface.provider)
    incident_surface.provider._attach_interaction_listeners()  # the Bolt app is built before the plugin registers
    load_plugin_catalogues(plugin.register_i18n_resources)
    yield RolesSurface(incident_surface, records, conversations, legacy)
    reset_translation_service()


@pytest.fixture
def surface(unseeded: RolesSurface) -> RolesSurface:
    """The surface with the channel's incident and its report, roles U0OLDIC and U0OLDOL set on the report."""
    seed_legacy_incident(unseeded.records, CHANNEL_ID, incident_id=INCIDENT_ID, report_url=REPORT_URL)
    return unseeded


def open_roles_modal(surface: RolesSurface) -> dict[str, Any]:
    surface.sre("incident roles manage")
    return last_view(surface.slack.client)


def posted_texts(surface: RolesSurface) -> list[str]:
    return list(surface.conversations.posts_in(slack_conversation(CHANNEL_ID)))


def test_roles_command_opens_the_modal_with_the_current_commander_and_lead_selected(surface: RolesSurface) -> None:
    """The command acks empty and opens a roles modal whose two user pickers start on the stored IC and OL."""
    response = surface.sre("incident roles manage")

    assert (response.status, response.body) == (200, "")
    view = last_view(surface.slack.client)
    assert view["title"]["text"] == "SRE - Roles management"
    assert view["blocks"][0]["text"]["text"] == "Roles for 2026-10-checkout"
    # TASK-145.8 ruling: the modal gains three optional pickers (communications lead, policy lead,
    # postmortem owner), so the map has five entries; the first two are as pinned.
    assert {element["placeholder"]["text"]: element.get("initial_user") for element in view_elements(view)} == {
        "Select an incident commander": "U0OLDIC",
        "Select an operations lead": "U0OLDOL",
        "Select a communications lead": None,
        "Select a policy lead": None,
        "Select a postmortem owner": None,
    }


def test_roles_command_leaves_the_pickers_empty_when_no_roles_are_stored(surface: RolesSurface) -> None:
    """A report document without stored roles opens a modal with no preselected user."""
    surface.legacy.seed(REPORT, {})

    open_roles_modal(surface)

    assert all("initial_user" not in element for element in view_elements(last_view(surface.slack.client)))


def test_roles_command_explains_when_the_channel_is_not_an_incident(unseeded: RolesSurface) -> None:
    """With no incident on the channel, no modal opens and the invoker is told the channel is not an incident's."""
    unseeded.sre("incident roles manage", channel_name="incident-2026-10-unknown")

    assert unseeded.slack.client.calls_to("views_open") == []
    [message] = unseeded.slack.responses
    # decisions/migration.md step 4 kind (b): the reply names what is missing, an incident record, not
    # a document found by channel name (TASK-145.8.5.1 named change).
    assert message["text"] == "This channel is not an incident channel, so it has no roles to manage."


@pytest.mark.parametrize("command", ["incident roles", "incident roles show"])
def test_roles_command_without_manage_opens_no_modal(surface: RolesSurface, command: str) -> None:
    """Only ``manage`` opens the modal; the bare command and ``show`` answer the roles help."""
    surface.sre(command)

    assert surface.slack.client.calls_to("views_open") == []
    assert len(surface.slack.responses) == 1


def test_submitting_new_roles_announces_each_one_in_the_channel(surface: RolesSurface) -> None:
    """Changing both pickers posts one assignment message per role and acks the submission empty."""
    view = open_roles_modal(surface)

    response = surface.slack.interaction(submission_payload(view, {IC_BLOCK: "U0NEWIC", OL_BLOCK: "U0NEWOL"}))

    assert (response.status, response.body) == (200, "")
    assert posted_texts(surface) == [
        "<@U0NEWIC> has been assigned as incident commander for this incident.",
        "<@U0NEWOL> has been assigned as operations lead for this incident.",
    ]


def test_submitting_one_changed_role_announces_only_that_role(surface: RolesSurface) -> None:
    """A role left on its stored user is not announced again."""
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {OL_BLOCK: "U0NEWOL"}))

    assert posted_texts(surface) == ["<@U0NEWOL> has been assigned as operations lead for this incident."]


def test_submitting_unchanged_roles_announces_nothing(surface: RolesSurface) -> None:
    """Saving the modal as opened posts no assignment message."""
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {}))

    assert posted_texts(surface) == []


def test_submitting_roles_appends_them_to_a_channel_purpose_that_has_none(surface: RolesSurface) -> None:
    """The channel purpose keeps its text and gains the ``IC: ... / OL: ...`` line."""
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {IC_BLOCK: "U0NEWIC", OL_BLOCK: "U0NEWOL"}))

    assert surface.purpose() == "Checkout outage \nIC: <@U0NEWIC> / OL: <@U0NEWOL>"


def test_submitting_roles_replaces_the_roles_line_already_in_the_purpose(surface: RolesSurface) -> None:
    """An existing ``IC: ... / OL: ...`` line is replaced, not duplicated."""
    surface.conversations.seed_purpose(slack_conversation(CHANNEL_ID), "Checkout outage\nIC: <@U0OLDIC> / OL: <@U0OLDOL>")
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {IC_BLOCK: "U0NEWIC"}))

    assert surface.purpose() == "Checkout outage\n\nIC: <@U0NEWIC> / OL: <@U0OLDOL>"


def test_submitting_roles_cuts_the_purpose_to_slacks_250_characters(surface: RolesSurface) -> None:
    """A long description is cut so the purpose fits Slack's limit."""
    surface.conversations.seed_purpose(slack_conversation(CHANNEL_ID), "x" * 300)
    view = open_roles_modal(surface)

    surface.slack.interaction(submission_payload(view, {IC_BLOCK: "U0NEWIC"}))

    assert surface.purpose() == "x" * 250
