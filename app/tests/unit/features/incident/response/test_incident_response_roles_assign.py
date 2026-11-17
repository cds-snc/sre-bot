"""``assign_roles``: the record first, then the role announcements and the channel purpose.

Runs over the core in-memory fakes (incident store, conversation and legacy roles reader), which
the core parity suites hold to the adapters' rules; a test-local subclass fails one port or counts
calls. Assertions read the fakes back in domain terms (the stored roles, the channel's posts and
purpose) and the stage outcomes the service returns, since the entry point renders its reply from them.

The record is the commit point (decisions/incident-management.md): a refused command check or a
failed record write writes nothing else; a failed follower is reported and the rest still run.
"""

from dataclasses import replace

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentStore,
    InMemoryLegacyRolesReader,
)
from features.incident.core.api import Incident, ReportReference
from features.incident.response.service.roles import RolesChange, assign_roles
from features.incident.response.service.status import StageOutcome
from tests.factories.incident import GOOGLE_TENANT, incident_on, slack_conversation

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
INCIDENT_ID = "inc-1"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0REPORT")
IC, OL, COMMS, POLICY, OWNER = (
    IncidentRole.INCIDENT_COMMANDER,
    IncidentRole.OPERATIONS_LEAD,
    IncidentRole.COMMUNICATIONS_LEAD,
    IncidentRole.POLICY_LEAD,
    IncidentRole.POSTMORTEM_OWNER,
)
ON_RECORD = {IC: "U0IC", OL: "U0OL", COMMS: "U0COMMS", POLICY: None, OWNER: None}


def _announce(role: IncidentRole, holder: str) -> str:
    return f"<@{holder}> is {role.value}"


class _Ports:
    """The ports over in-memory fakes: an incident holding ``roles`` on an open channel with a purpose."""

    def __init__(self, roles: dict[IncidentRole, str | None] | None = None, *, with_report: bool = False) -> None:
        held = {role.value: holder for role, holder in (roles or {}).items() if holder}
        self.incident = replace(incident_on(CHANNEL_ID, INCIDENT_ID), report=REPORT if with_report else None, **held)
        self.incidents = InMemoryIncidentStore()
        self.incidents.seed(self.incident)
        self.conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID])
        self.conversations.seed_purpose(slack_conversation(CHANNEL_ID), "Checkout outage")
        self.legacy = InMemoryLegacyRolesReader()

    async def assign(self, roles: dict[IncidentRole, str | None]) -> OperationResult[RolesChange]:
        return await assign_roles(
            self.incidents, self.conversations, self.legacy, slack_conversation(CHANNEL_ID), roles, announce=_announce
        )

    async def stored(self) -> Incident:
        found = await self.incidents.get(INCIDENT_ID)
        assert found.data is not None
        return found.data

    def posts(self) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def purpose(self) -> str | None:
        return self.conversations.purpose_of(slack_conversation(CHANNEL_ID))


def _changed(result: OperationResult[RolesChange]) -> RolesChange:
    assert result.is_success and result.data is not None, result
    return result.data


async def test_five_new_roles_are_written_announced_in_role_order_and_put_in_the_purpose() -> None:
    ports = _Ports()
    submitted = {IC: "U1", OL: "U2", COMMS: "U3", POLICY: "U4", OWNER: "U5"}

    change = _changed(await ports.assign(submitted))

    stored = await ports.stored()
    assert [getattr(stored, role.value) for role in IncidentRole] == ["U1", "U2", "U3", "U4", "U5"]
    assert ports.posts() == tuple(f"<@U{n}> is {role.value}" for n, role in enumerate(IncidentRole, start=1))
    assert ports.purpose() == "Checkout outage \nIC: <@U1> / OL: <@U2>"
    assert change.announced == tuple(IncidentRole)
    assert [change.announcements.outcome, change.purpose.outcome] == [StageOutcome.DONE] * 2


async def test_only_the_role_whose_holder_changed_is_announced() -> None:
    ports = _Ports(ON_RECORD)

    change = _changed(await ports.assign({**ON_RECORD, OL: "U0NEWOL"}))

    assert ports.posts() == ("<@U0NEWOL> is operations_lead",)
    assert change.announced == (OL,)


async def test_unchanged_roles_announce_nothing_but_still_rewrite_the_purpose() -> None:
    ports = _Ports(ON_RECORD)

    _changed(await ports.assign(ON_RECORD))

    assert ports.posts() == ()
    assert ports.purpose() == "Checkout outage \nIC: <@U0IC> / OL: <@U0OL>"


async def test_an_optional_role_is_unassigned_without_an_announcement() -> None:
    ports = _Ports(ON_RECORD)

    _changed(await ports.assign({**ON_RECORD, COMMS: None}))

    assert (await ports.stored()).communications_lead is None
    assert ports.posts() == ()


async def test_a_legacy_incident_shows_the_report_roles_so_an_unchanged_submission_announces_none_and_fills_the_record() -> None:
    ports = _Ports(with_report=True)
    ports.legacy.seed(REPORT, {IC: "U0OLDIC", OL: "U0OLDOL"})

    _changed(await ports.assign({IC: "U0OLDIC", OL: "U0OLDOL", COMMS: None, POLICY: None, OWNER: None}))

    stored = await ports.stored()
    assert (stored.incident_commander, stored.operations_lead) == ("U0OLDIC", "U0OLDOL")
    assert ports.posts() == ()


async def test_an_incident_that_is_not_one_writes_and_posts_nothing() -> None:
    ports = _Ports()
    ports.incidents = InMemoryIncidentStore()

    result = await ports.assign(ON_RECORD)

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT
    assert ports.posts() == ()
    assert ports.purpose() == "Checkout outage"


async def test_a_failed_record_write_stops_before_any_post_or_purpose_change() -> None:
    ports = _Ports()

    class Store(InMemoryIncidentStore):
        async def set_roles(self, incident_id: str, roles: dict[IncidentRole, str | None]) -> OperationResult[Incident]:  # type: ignore[override]
            return OperationResult.permanent_error("conflict", ErrorCode.INCIDENT_RECORD_CONFLICT)

    ports.incidents = Store()
    ports.incidents.seed(ports.incident)

    result = await ports.assign(ON_RECORD)

    assert result.error_code == ErrorCode.INCIDENT_RECORD_CONFLICT
    assert ports.posts() == ()
    assert ports.purpose() == "Checkout outage"


async def test_a_channel_that_cannot_be_written_skips_the_announcements_and_the_purpose_and_keeps_the_record() -> None:
    ports = _Ports()
    ports.conversations = InMemoryIncidentConversation(archived_ids=[CHANNEL_ID])

    change = _changed(await ports.assign(ON_RECORD))

    assert (await ports.stored()).incident_commander == "U0IC"
    assert (change.announcements.outcome, change.purpose.outcome) == (StageOutcome.SKIPPED, StageOutcome.SKIPPED)
    assert change.announced == ()


async def test_a_failed_post_is_reported_while_the_other_announcements_and_the_purpose_still_run() -> None:
    ports = _Ports()

    class Conversations(InMemoryIncidentConversation):
        async def post(self, conversation, text, *, blocks=()):  # type: ignore[no-untyped-def]
            if "<@U1>" in text:
                return OperationResult.error(OperationStatus.TRANSIENT_ERROR, "slow", "ratelimited")
            return await super().post(conversation, text, blocks=blocks)

    ports.conversations = Conversations(open_ids=[CHANNEL_ID])
    ports.conversations.seed_purpose(slack_conversation(CHANNEL_ID), "Checkout outage")

    change = _changed(await ports.assign({IC: "U1", OL: "U2", COMMS: None, POLICY: None, OWNER: None}))

    assert change.announcements.outcome is StageOutcome.FAILED
    assert change.announcements.error_code == "ratelimited"
    assert change.announced == (OL,)
    assert change.purpose.outcome is StageOutcome.DONE


async def test_a_purpose_read_failure_is_reported_and_the_roles_stay() -> None:
    ports = _Ports()

    class Conversations(InMemoryIncidentConversation):
        async def purpose(self, conversation):  # type: ignore[no-untyped-def]
            return OperationResult.error(OperationStatus.TRANSIENT_ERROR, "down", "ratelimited")

    ports.conversations = Conversations(open_ids=[CHANNEL_ID])

    change = _changed(await ports.assign(ON_RECORD))

    assert change.purpose.outcome is StageOutcome.FAILED
    assert (await ports.stored()).incident_commander == "U0IC"


async def test_a_purpose_write_failure_is_reported() -> None:
    ports = _Ports()

    class Conversations(InMemoryIncidentConversation):
        async def set_purpose(self, conversation, text):  # type: ignore[no-untyped-def]
            return OperationResult.error(OperationStatus.TRANSIENT_ERROR, "down", "ratelimited")

    ports.conversations = Conversations(open_ids=[CHANNEL_ID])

    change = _changed(await ports.assign(ON_RECORD))

    assert (change.announcements.outcome, change.purpose.outcome) == (StageOutcome.DONE, StageOutcome.FAILED)


async def test_the_purpose_is_left_alone_when_the_commander_or_the_lead_is_unassigned() -> None:
    ports = _Ports()

    change = _changed(await ports.assign({IC: "U1", OL: None, COMMS: None, POLICY: None, OWNER: None}))

    assert change.purpose.outcome is StageOutcome.SKIPPED
    assert ports.purpose() == "Checkout outage"


async def test_a_failed_writability_check_is_reported_for_both_followers() -> None:
    ports = _Ports()
    ports.conversations = InMemoryIncidentConversation()  # the channel is unknown to Slack

    change = _changed(await ports.assign(ON_RECORD))

    assert (change.announcements.outcome, change.purpose.outcome) == (StageOutcome.FAILED, StageOutcome.FAILED)
    assert change.announcements.error_code == "channel_not_found"
