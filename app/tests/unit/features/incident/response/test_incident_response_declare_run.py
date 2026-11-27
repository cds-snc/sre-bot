"""``declare``: the record first, then the conversation and its binding, then the resources, invites and list row.

Runs over the core in-memory fakes (incident store, conversation, report, video call,
list projection and placement schedule lookup, each held to its adapter by a core
suite), the on-call capability's in-memory lookup, real claims (``ThreadedClaims``
over the in-memory conditional-write store) and test-local texts that render each
message from its inputs. A test-local subclass fails one port where a test needs it.
Assertions read the fakes back in domain terms: the stored record and its
references, the channel's posts, bookmarks and invites, the list rows and the stage
outcomes the service returns, since the cutover's entry points render their replies
from those.

Rules under test (decisions/incident-management.md, oncall.md; TASK-145.7.9 plan):
the record is the commit point, written first under the id derived from the
idempotency key, and never rolled back; a failed conversation leaves an open
incident with no surface and still writes the list row; each later failure leaves
its reference empty and the declare continues; a rerun with the same key is the
retry: it fills only what is missing and posts nothing twice; one run per incident
at a time; the declarer, on-call people and the configured groups are invited once
each, a group only when its id is configured; a failing on-call source invites
nobody and says so; the initial status comes from the policy.
"""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import pytest

from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from capabilities.oncall.api import OPSGENIE, Account, OnCallPerson, ScheduleReference
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryIncidentStore,
    InMemoryPlacementScheduleLookup,
    InMemoryVideoCall,
)
from features.incident.core.api import (
    ConversationName,
    ConversationReference,
    Incident,
    MessageReference,
    ReportPlacement,
    ReportReference,
    VideoCallReference,
)
from features.incident.response.adapters.claims import ThreadedClaims
from features.incident.response.service.conversation import name_claim_key
from features.incident.response.service.declare import (
    ChatSurface,
    Declared,
    DeclarePolicy,
    DeclarePorts,
    DeclareRequest,
    declare,
    declare_claim_key,
    incident_id_for,
)
from features.incident.response.service.status import StageOutcome
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT

pytestmark = pytest.mark.unit

AT = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
DECLARER = "U0DECLARER"
KEY = "slack:T0SLACK:V0VIEW"
PLACEMENT = ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0PAYMENTS", label="Payments")
NOTIFY = ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="F0NOTIFY", label="Notify")
SCHEDULE = ScheduleReference(system=OPSGENIE, id="sched-payments")
NOTIFY_SCHEDULE = ScheduleReference(system=OPSGENIE, id="sched-notify")
ANNOUNCEMENTS = "C0ANNOUNCE"
ALERT = MessageReference(
    system=WorkplaceSystem.SLACK,
    tenant=SLACK_TENANT,
    conversation_id="C0ALERTS",
    message_id="1700000000.000100",
    url="https://slack.example/archives/C0ALERTS/p1700000000000100",
)
GROUPS = {"S0SEC": ["U0SEC1", DECLARER], "S0POLICY": ["U0POL1", "U0SEC1"], "S0NOTIFY": ["U0NOTIFY"]}
ACCOUNTS = {"oncall@example.org": "U0ONCALL"}
POLICY = DeclarePolicy(
    initial_status=IncidentStatus.OPEN,
    production=True,
    announcement_channel_id=ANNOUNCEMENTS,
    security_group_id="S0SEC",
    policy_group_id="S0POLICY",
    notify_management_group_id="S0NOTIFY",
    notify_management_placement_id="F0NOTIFY",
    conversation_name_attempts=5,
)


class ChannelLanguages:
    """English only everywhere but the announcement channel, which is written in French then English."""

    def shared_languages(self, *, system: WorkplaceSystem, tenant: str, conversation_id: str) -> tuple[str, ...]:
        return ("fr-FR", "en-US") if conversation_id == ANNOUNCEMENTS else ("en-US",)

    def reply_languages(self, user_locale: str | None) -> tuple[str, ...]:
        return ("en-US",)


LANGUAGES = ChannelLanguages()


def _in(languages: tuple[str, ...]) -> str:
    """Nothing for the incident channel's English; the languages otherwise, so a test sees which ones a post got."""
    return "" if languages == ("en-US",) else f" [{', '.join(languages)}]"


class Texts:
    """Renders each message from its inputs, so a test can tell which incident and reference it names."""

    def topic(self, incident: Incident) -> str:
        return f"topic {incident.title}"

    def purpose(self, incident: Incident) -> str:
        return f"purpose {incident.title}"

    def canvas(self, incident: Incident) -> str:
        return f"# canvas {incident.title}"

    def announcement(self, incident: Incident, conversation: ConversationReference, languages: tuple[str, ...]) -> str:
        return f"announce {incident.id} in {conversation.vendor_id}{_in(languages)}"

    def severity_warning(self, incident: Incident, languages: tuple[str, ...]) -> str | None:
        return None if incident.severity is None else f"severity {incident.severity.name}{_in(languages)}"

    def report_bookmark(self) -> str:
        return "Report"

    def report_posted(self, report: ReportReference, languages: tuple[str, ...]) -> str:
        return f"report {report.vendor_id}{_in(languages)}"

    def report_placeholders(
        self, incident: Incident, conversation: ConversationReference | None, on_call: tuple[OnCallPerson, ...]
    ) -> dict[str, str]:
        channel = conversation.vendor_id if conversation is not None else ""
        return {"{{name}}": incident.title, "{{slack-channel}}": channel, "{{on-call}}": str(len(on_call))}

    def video_call_bookmark(self) -> str:
        return "Meet"

    def video_call_posted(self, call: VideoCallReference, languages: tuple[str, ...]) -> str:
        return f"meet {call.url}{_in(languages)}"

    def source_alert_bookmark(self) -> str:
        return "Alert"

    def source_alert_posted(self, alert: MessageReference, languages: tuple[str, ...]) -> str:
        return f"alert {alert.message_id}{_in(languages)}"

    def on_call_unavailable(self, incident: Incident, languages: tuple[str, ...]) -> str:
        return f"nobody on call invited{_in(languages)}"

    def next_steps(self, incident: Incident, languages: tuple[str, ...]) -> str:
        return f"next steps{_in(languages)}"


@dataclass
class World:
    """The ports over fakes, each kept for assertions."""

    incidents: InMemoryIncidentStore
    conversations: InMemoryIncidentConversation
    reports: InMemoryIncidentReport
    video_calls: InMemoryVideoCall
    projection: InMemoryIncidentListProjection
    claims: ThreadedClaims
    schedules: InMemoryPlacementScheduleLookup
    oncall: InMemoryOnCallLookup

    def ports(self, *, chat: bool = True) -> DeclarePorts:
        return DeclarePorts(
            incidents=self.incidents,
            reports=self.reports,
            video_calls=self.video_calls,
            projection=self.projection,
            claims=self.claims,
            schedules=self.schedules,
            oncall=self.oncall,
            chat=ChatSurface(self.conversations, tenant=SLACK_TENANT, languages=LANGUAGES) if chat else None,
        )


def _world(
    *,
    conversations: InMemoryIncidentConversation | None = None,
    video_calls: InMemoryVideoCall | None = None,
    projection: InMemoryIncidentListProjection | None = None,
    oncall: InMemoryOnCallLookup | None = None,
) -> World:
    return World(
        incidents=InMemoryIncidentStore(),
        conversations=conversations
        if conversations is not None
        else InMemoryIncidentConversation(
            tenant=SLACK_TENANT, open_ids=[ANNOUNCEMENTS, "C0ALERTS"], groups=GROUPS, accounts=ACCOUNTS
        ),
        reports=InMemoryIncidentReport(next_ids=["D0REPORT"]),
        video_calls=video_calls if video_calls is not None else InMemoryVideoCall(),
        projection=projection if projection is not None else InMemoryIncidentListProjection(),
        claims=ThreadedClaims(InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300)),
        schedules=InMemoryPlacementScheduleLookup({"F0PAYMENTS": SCHEDULE, "F0NOTIFY": NOTIFY_SCHEDULE}),
        oncall=oncall
        if oncall is not None
        else InMemoryOnCallLookup(
            people={
                SCHEDULE: (
                    OnCallPerson(email="oncall@example.org", account=None),
                    OnCallPerson(email=None, account=Account(platform="slack", tenant=SLACK_TENANT, account_id="U0ROT")),
                ),
                NOTIFY_SCHEDULE: (),
            }
        ),
    )


def _request(**changes: object) -> DeclareRequest:
    request = DeclareRequest(
        idempotency_key=KEY,
        title="Payments down",
        security_incident=False,
        declarer=DECLARER,
        declared_at=AT,
        placement=PLACEMENT,
    )
    return replace(request, **changes)  # type: ignore[arg-type]


async def _declare(
    world: World, request: DeclareRequest | None = None, *, policy: DeclarePolicy = POLICY, chat: bool = True
) -> Declared:
    result = await declare(request or _request(), world.ports(chat=chat), POLICY if policy is None else policy, Texts())
    assert result.is_success, result.message
    assert result.data is not None
    return result.data


def _channel(declared: Declared) -> ConversationReference:
    assert declared.incident.conversation is not None
    return declared.incident.conversation


async def test_full_success_writes_the_record_and_every_reference_under_the_keys_id() -> None:
    world = _world()

    declared = await _declare(world)

    stored = (await world.incidents.get(incident_id_for(KEY))).data
    assert stored == declared.incident
    assert stored is not None
    assert stored.status is IncidentStatus.OPEN
    assert stored.declared_by == DECLARER
    assert stored.conversation == ConversationReference(system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id="C0NEW1")
    assert stored.report is not None and stored.report.vendor_id == "D0REPORT"
    assert stored.video_call is not None and stored.video_call.vendor_id == "spaces/call-1"
    assert declared.created
    assert [stage.outcome for stage in (declared.conversation, declared.report, declared.video_call, declared.list_row)] == [
        StageOutcome.DONE
    ] * 4


async def test_the_conversation_is_named_set_up_bookmarked_and_announced() -> None:
    world = _world()

    declared = await _declare(world)

    channel = _channel(declared)
    assert world.conversations.topic_of(channel) == "topic Payments down"
    assert world.conversations.purpose_of(channel) == "purpose Payments down"
    assert world.conversations.canvas_of(channel) == "# canvas Payments down"
    assert world.conversations.bookmarks_of(channel) == (
        ("Report", "https://docs.google.com/document/d/D0REPORT/edit"),
        ("Meet", "https://meet.google.com/call-1"),
    )
    assert world.conversations.posts_in(channel) == ("report D0REPORT", "meet https://meet.google.com/call-1", "next steps")
    announcements = ConversationReference(system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id=ANNOUNCEMENTS)
    assert world.conversations.posts_in(announcements) == (f"announce {declared.incident.id} in C0NEW1 [fr-FR, en-US]",)


async def test_the_report_is_filed_in_the_placement_with_its_placeholders() -> None:
    world = _world()

    declared = await _declare(world)

    report = declared.incident.report
    assert report is not None
    assert world.reports.filed_in(report) == "F0PAYMENTS"
    assert world.reports.placeholders_of(report) == {
        "{{name}}": "Payments down",
        "{{slack-channel}}": "C0NEW1",
        "{{on-call}}": "2",
    }


async def test_the_declarer_is_the_incident_commander() -> None:
    world = _world()

    declared = await _declare(world)

    stored = (await world.incidents.get(incident_id_for(KEY))).data
    assert stored is not None
    assert stored.incident_commander == DECLARER == declared.incident.incident_commander


async def test_the_initial_status_comes_from_the_policy() -> None:
    world = _world()

    declared = await _declare(world, policy=replace(POLICY, initial_status=IncidentStatus.IN_PROGRESS))

    assert declared.incident.status is IncidentStatus.IN_PROGRESS
    assert world.projection.rows[0][3] == "In Progress"


async def test_the_declarer_and_the_on_call_people_are_invited_once() -> None:
    world = _world()

    declared = await _declare(world)

    assert world.conversations.invited_to(_channel(declared)) == (DECLARER, "U0ROT", "U0ONCALL")
    assert declared.on_call.outcome is StageOutcome.DONE


async def test_a_security_incident_with_policy_help_invites_both_groups_without_duplicates() -> None:
    world = _world()

    declared = await _declare(world, _request(security_incident=True, policy_help=True))

    assert world.conversations.invited_to(_channel(declared)) == (DECLARER, "U0ROT", "U0ONCALL", "U0SEC1", "U0POL1")


async def test_a_group_whose_id_is_not_configured_is_not_invited() -> None:
    world = _world()
    unconfigured = replace(POLICY, security_group_id="", policy_group_id="")

    declared = await _declare(world, _request(security_incident=True, policy_help=True), policy=unconfigured)

    assert world.conversations.invited_to(_channel(declared)) == (DECLARER, "U0ROT", "U0ONCALL")
    assert declared.invites.outcome is StageOutcome.DONE


async def test_the_notify_placement_invites_the_notify_management_group() -> None:
    world = _world()

    declared = await _declare(world, _request(placement=NOTIFY))

    assert world.conversations.invited_to(_channel(declared)) == (DECLARER, "U0NOTIFY")


@pytest.mark.parametrize(
    "oncall",
    [
        pytest.param(InMemoryOnCallLookup(), id="source-fails"),
        pytest.param(None, id="no-placement"),
    ],
)
async def test_without_an_on_call_answer_nobody_on_call_is_invited_and_the_channel_says_so(
    oncall: InMemoryOnCallLookup | None,
) -> None:
    world = _world(oncall=oncall)
    request = _request() if oncall is not None else _request(placement=None)

    declared = await _declare(world, request)

    channel = _channel(declared)
    assert world.conversations.invited_to(channel) == (DECLARER,)
    assert "nobody on call invited" in world.conversations.posts_in(channel)
    assert declared.on_call.outcome is not StageOutcome.DONE


async def test_a_severity_and_a_source_alert_are_posted_and_the_alert_bookmarked() -> None:
    world = _world()

    declared = await _declare(world, _request(severity=Severity.SEV2, source_alert=ALERT))

    channel = _channel(declared)
    assert "severity SEV2" in world.conversations.posts_in(channel)
    assert f"alert {ALERT.message_id}" in world.conversations.posts_in(channel)
    assert ("Alert", ALERT.url) in world.conversations.bookmarks_of(channel)
    assert declared.incident.source_alert == ALERT


class NoCreate(InMemoryIncidentConversation):
    """Every conversation create fails transiently with nothing created."""

    async def create(self, name: ConversationName, *, private: bool) -> OperationResult[ConversationReference]:
        return OperationResult.transient_error("Slack create timed out")


async def test_the_policys_name_bound_limits_the_candidates_declare_tries() -> None:
    """With a bound of two and both names held by another incident, declare stops at two.

    Real claims hold attempts 1 and 2 for another incident, so each is skipped
    without a create; a third name would be free, so reaching it would create a
    conversation. The stage failing with CONVERSATION_NAME_TAKEN and no conversation
    created proves the policy's bound, not a default, reached the loop.
    """
    world = _world()
    for attempt in (1, 2):
        key = name_claim_key(SLACK_TENANT, ConversationName("Payments down", AT.date(), production=True, attempt=attempt))
        held = await world.claims.claim(key)
        assert held.claim_token is not None
        await world.claims.complete(key, {"incident_id": "inc-other"}, held.claim_token)

    declared = await _declare(world, policy=replace(POLICY, conversation_name_attempts=2))

    assert declared.conversation.outcome is StageOutcome.FAILED
    assert declared.conversation.error_code == ErrorCode.CONVERSATION_NAME_TAKEN
    assert declared.incident.conversation is None
    third = ConversationName("Payments down", AT.date(), production=True, attempt=3)
    assert (await world.conversations.find_own(third)).data is None


async def test_a_failing_conversation_leaves_an_open_incident_with_no_surface_and_writes_the_list_row() -> None:
    world = _world(conversations=NoCreate(tenant=SLACK_TENANT, open_ids=[ANNOUNCEMENTS], groups=GROUPS))

    declared = await _declare(world)

    stored = (await world.incidents.get(declared.incident.id)).data
    assert stored is not None and stored.status.is_open
    assert stored.conversation is None
    assert stored.report is not None
    assert declared.conversation.outcome is StageOutcome.FAILED
    assert declared.list_row.outcome is StageOutcome.DONE
    assert world.projection.rows[0][5] == declared.incident.id


async def test_without_a_chat_platform_the_incident_is_declared_through_the_api_alone() -> None:
    world = _world()

    declared = await _declare(world, chat=False)

    assert declared.incident.conversation is None
    assert declared.incident.report is not None
    assert declared.conversation.reason == "no_chat_platform"
    assert len(world.projection.rows) == 1


async def test_a_failing_video_call_leaves_its_reference_empty_and_the_declare_continues() -> None:
    world = _world(video_calls=InMemoryVideoCall(fail_with=OperationResult.transient_error("Meet down")))

    declared = await _declare(world)

    assert declared.incident.video_call is None
    assert declared.video_call.outcome is StageOutcome.FAILED
    assert declared.incident.report is not None
    assert "next steps" in world.conversations.posts_in(_channel(declared))


async def test_a_failing_list_row_is_reported_and_the_incident_stays_declared() -> None:
    world = _world(projection=InMemoryIncidentListProjection(fail_with=OperationResult.transient_error("Sheets down")))

    declared = await _declare(world)

    assert declared.list_row.outcome is StageOutcome.FAILED
    assert (await world.incidents.get(declared.incident.id)).data is not None


async def test_a_rerun_with_the_same_key_fills_what_is_missing_and_posts_nothing_twice() -> None:
    world = _world(video_calls=InMemoryVideoCall(fail_with=OperationResult.transient_error("Meet down")))
    first = await _declare(world)
    world.video_calls = InMemoryVideoCall()

    second = await _declare(world)

    channel = _channel(second)
    assert second.incident.id == first.incident.id
    assert not second.created
    assert second.incident.video_call is not None
    assert world.reports.filed_in(second.incident.report) == "F0PAYMENTS"  # type: ignore[arg-type]
    assert world.conversations.posts_in(channel) == (
        "report D0REPORT",
        "next steps",
        "meet https://meet.google.com/call-1",
    )
    announcements = ConversationReference(system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id=ANNOUNCEMENTS)
    assert len(world.conversations.posts_in(announcements)) == 1
    assert len(world.projection.rows) == 1


async def test_a_declare_already_running_for_the_key_is_refused_writing_nothing() -> None:
    world = _world()
    held = await world.claims.claim(declare_claim_key(incident_id_for(KEY)))
    assert held.claim_token is not None

    result = await declare(_request(), world.ports(), POLICY, Texts())

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == ErrorCode.DECLARE_IN_PROGRESS
    assert (await world.incidents.get(incident_id_for(KEY))).status is OperationStatus.NOT_FOUND


async def test_the_run_claim_is_released_so_a_later_retry_runs() -> None:
    world = _world()
    await _declare(world)

    held = await world.claims.claim(declare_claim_key(incident_id_for(KEY)))

    assert held.claim_token is not None


def test_the_id_is_derived_from_the_key_alone() -> None:
    assert incident_id_for(KEY) == incident_id_for(KEY)
    assert incident_id_for(KEY) != incident_id_for("slack:T0SLACK:V0OTHER")


async def test_the_conversation_is_named_for_the_declares_opening_day_in_production() -> None:
    world = _world()

    declared = await _declare(world, _request(declared_at=datetime(2026, 1, 2, 23, 0, tzinfo=UTC)))

    found = await world.conversations.find_own(ConversationName("Payments down", date(2026, 1, 2), production=True))
    assert found.data == _channel(declared)
