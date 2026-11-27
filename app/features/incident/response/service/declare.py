"""Declare: the record first, then the conversation and its binding, then the resources, invites and list row.

``declare`` serves every way an incident is declared (the Slack modal and the alert
buttons today); it names no platform. The record is the commit point
(decisions/incident-management.md): it is written first, under the id derived from the
declare's idempotency key, with the declarer as incident commander, and never rolled back. Every
later step is retriable and leaves its reference empty when it fails; the declare
continues and reports each step's outcome. Running the declare again with the same key
is the retry: the record write replays, each step is skipped when its reference is set,
and each one-time message is posted once (a claim per message). One run per incident
holds the run claim at a time; a second is refused with ``DECLARE_IN_PROGRESS``.

Steps, in order: the record; the conversation (``ensure_conversation``) and its primary
binding; who is on call for the chosen placement's schedule (the on-call capability);
the report filed in the placement with its placeholders; the video call; then, in the
conversation, its topic, purpose and canvas, the report and video call bookmarks and
links, the severity warning, the source alert, the announcement, the invites (the
declarer, the on-call people, and the security, policy and Notify management groups,
each group only when its id is configured), the on-call notice when nobody on call
could be invited, and the next steps; last, the list row, written whatever failed
before it. Each message posted to a conversation is rendered in that conversation's
languages, read from the chat surface's language policy.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

import structlog

from capabilities.oncall.api import OnCallLookup, OnCallPerson
from contracts.coordination import ClaimResult
from contracts.languages import LanguagePolicy
from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.api import (
    BindingKind,
    ConversationReference,
    Incident,
    IncidentBinding,
    IncidentConversation,
    IncidentListProjection,
    IncidentReport,
    IncidentStore,
    MessageReference,
    PlacementScheduleLookup,
    ReferenceKind,
    ReportPlacement,
    VideoCall,
    incident_conversation_names,
)
from features.incident.response.interfaces import Claims, DeclareTexts
from features.incident.response.service.conversation import ensure_conversation
from features.incident.response.service.status import StageOutcome, StageResult, stage_result
from features.incident.response.settings import IncidentResponseSettings

logger = structlog.get_logger()

DECLARE_NAMESPACE = UUID("6f1c3a52-9d0e-4d61-9a3b-1f2e7c4b8a90")
"""The namespace of incident ids derived from a declare's idempotency key (uuid5); never changed."""

_DONE = StageResult(StageOutcome.DONE)


@dataclass(frozen=True)
class DeclareRequest:
    """What a declare asks for, from any entry point.

    Attributes:
        idempotency_key: The entry point's key for this declare (the Slack view, the alert
            message, the HTTP Idempotency-Key with its caller); the incident id derives from it.
        title: Short name of the incident.
        security_incident: Whether it is declared a security incident.
        declarer: The chat account id of the person declaring.
        declared_at: When it was declared, timezone-aware.
        severity: The severity chosen at declare, ``None`` when not rated yet.
        placement: The report placement chosen (a product folder), ``None`` for the default folder.
        policy_help: Whether policy help was asked for; invites the policy group, never stored.
        source_alert: The alert message it was declared from.
    """

    idempotency_key: str
    title: str
    security_incident: bool
    declarer: str
    declared_at: datetime
    severity: Severity | None = None
    placement: ReportPlacement | None = None
    policy_help: bool = False
    source_alert: MessageReference | None = None


@dataclass(frozen=True)
class ChatSurface:
    """The chat platform declare creates the conversation on, its tenant, and the languages each conversation is written in."""

    conversations: IncidentConversation
    tenant: str
    languages: LanguagePolicy


@dataclass(frozen=True)
class DeclarePorts:
    """The ports a declare writes and reads through; ``chat`` is ``None`` on an instance without a chat platform."""

    incidents: IncidentStore
    reports: IncidentReport
    video_calls: VideoCall
    projection: IncidentListProjection
    claims: Claims
    schedules: PlacementScheduleLookup
    oncall: OnCallLookup
    chat: ChatSurface | None


@dataclass(frozen=True)
class DeclarePolicy:
    """The organisation's declare choices, read from ``[incident_response]``; an empty id means none.

    ``conversation_name_attempts`` is ``[incident_core]``'s bound on the conversation's candidate names.
    """

    initial_status: IncidentStatus
    production: bool
    announcement_channel_id: str
    security_group_id: str
    policy_group_id: str
    notify_management_group_id: str
    notify_management_placement_id: str
    conversation_name_attempts: int

    @classmethod
    def from_settings(
        cls, settings: IncidentResponseSettings, *, production: bool, conversation_name_attempts: int
    ) -> DeclarePolicy:
        """Build the policy from the response slice and core's name bound; ``production`` names conversations without ``-dev``."""
        return cls(
            initial_status=settings.initial_status,
            production=production,
            announcement_channel_id=settings.announcement_channel_id,
            security_group_id=settings.security_group_id,
            policy_group_id=settings.policy_group_id,
            notify_management_group_id=settings.notify_management_group_id,
            notify_management_placement_id=settings.notify_management_placement_id,
            conversation_name_attempts=conversation_name_attempts,
        )


@dataclass(frozen=True)
class Declared:
    """A committed declare: the incident as stored and each step's outcome.

    ``created`` is False when the record already existed (a retry). ``on_call`` is
    skipped with a reason when there was no placement or no schedule.
    """

    incident: Incident
    created: bool
    conversation: StageResult
    on_call: StageResult
    report: StageResult
    video_call: StageResult
    messages: StageResult
    invites: StageResult
    list_row: StageResult


def incident_id_for(idempotency_key: str) -> str:
    """The incident id a declare under ``idempotency_key`` writes: the same key always gives the same id."""
    return str(uuid5(DECLARE_NAMESPACE, idempotency_key))


def declare_claim_key(incident_id: str) -> str:
    """The run claim of one incident's declare."""
    return f"incident:declare:{incident_id}"


async def declare(
    request: DeclareRequest, ports: DeclarePorts, policy: DeclarePolicy, texts: DeclareTexts
) -> OperationResult[Declared]:
    """Declare an incident, or retry a declare under the same key.

    Args:
        request: What is declared.
        ports: The stores and systems written through.
        policy: The organisation's declare choices.
        texts: The words of every message, rendered by the caller.

    Returns:
        The committed declare with each step's outcome; ``DECLARE_IN_PROGRESS`` while
        another run holds the incident; the record write's failure with nothing written.
    """
    incident_id = incident_id_for(request.idempotency_key)
    run_key = declare_claim_key(incident_id)
    run = await ports.claims.claim(run_key)
    if run.result is not ClaimResult.NEW or run.claim_token is None:
        logger.info("incident_declare_in_progress", incident_id=incident_id)
        return OperationResult.transient_error(
            "This incident's declare is already running", error_code=ErrorCode.DECLARE_IN_PROGRESS
        )
    try:
        return await _run(incident_id, request, ports, policy, texts)
    finally:
        await ports.claims.release(run_key, run.claim_token)


async def _run(
    incident_id: str, request: DeclareRequest, ports: DeclarePorts, policy: DeclarePolicy, texts: DeclareTexts
) -> OperationResult[Declared]:
    new = Incident(
        id=incident_id,
        title=request.title,
        status=policy.initial_status,
        declared_by=request.declarer,
        declared_at=request.declared_at,
        security_incident=request.security_incident,
        incident_commander=request.declarer,
        severity=request.severity,
        source_alert=request.source_alert,
    )
    written = await ports.incidents.create(new)
    if not written.is_success or written.data is None:
        logger.warning("incident_declare_record_failed", incident_id=incident_id, status=written.status.value)
        return OperationResult.error(
            status=written.status,
            message=written.message or "The incident could not be recorded",
            error_code=written.error_code,
            retry_after=written.retry_after,
        )
    incident = written.data
    created = incident == new
    step = _Steps(incident, request, ports, policy, texts)

    conversation = await step.conversation()
    people, on_call = await step.on_call()
    report = await step.report(people)
    video_call = await step.video_call()
    messages, invites = await step.in_conversation(people, on_call)
    list_row = stage_result(await ports.projection.append_row(step.incident))

    logger.info(
        "incident_declared",
        incident_id=incident_id,
        created=created,
        conversation=conversation.outcome.value,
        on_call=on_call.outcome.value,
        report=report.outcome.value,
        video_call=video_call.outcome.value,
        messages=messages.outcome.value,
        invites=invites.outcome.value,
        list_row=list_row.outcome.value,
    )
    return OperationResult.success(
        Declared(
            incident=step.incident,
            created=created,
            conversation=conversation,
            on_call=on_call,
            report=report,
            video_call=video_call,
            messages=messages,
            invites=invites,
            list_row=list_row,
        )
    )


class _Steps:
    """One declare run's steps over the incident as last written."""

    def __init__(
        self, incident: Incident, request: DeclareRequest, ports: DeclarePorts, policy: DeclarePolicy, texts: DeclareTexts
    ) -> None:
        self.incident = incident
        self._request = request
        self._ports = ports
        self._policy = policy
        self._texts = texts
        self._new_report = False
        self._new_video_call = False

    async def conversation(self) -> StageResult:
        """Find or create the conversation and bind it as the primary; skipped without a chat platform."""
        chat = self._ports.chat
        if chat is None:
            return StageResult(StageOutcome.SKIPPED, reason="no_chat_platform")
        if self.incident.conversation is not None:
            return _DONE
        names = incident_conversation_names(
            self.incident.title,
            self.incident.declared_at.date(),
            production=self._policy.production,
            attempts=self._policy.conversation_name_attempts,
        )
        ensured = await ensure_conversation(
            self.incident,
            incidents=self._ports.incidents,
            conversations=chat.conversations,
            claims=self._ports.claims,
            names=names,
            tenant=chat.tenant,
        )
        if not ensured.is_success or ensured.data is None:
            return stage_result(ensured)
        found = ensured.data
        binding = IncidentBinding(
            incident_id=self.incident.id,
            kind=BindingKind.CHAT_CONVERSATION,
            system=found.system,
            tenant=found.tenant,
            vendor_id=found.vendor_id,
            primary=True,
            bound_by=self._request.declarer,
            bound_at=self._request.declared_at,
            url=found.url,
        )
        return self._keep(await self._ports.incidents.attach_conversation(self.incident.id, binding))

    async def on_call(self) -> tuple[tuple[OnCallPerson, ...], StageResult]:
        """Ask the on-call capability who is on call for the placement's schedule; nobody when it cannot say."""
        placement = self._request.placement
        if placement is None:
            return (), StageResult(StageOutcome.SKIPPED, reason="no_placement")
        schedule = await self._ports.schedules.schedule_for(placement)
        if not schedule.is_success:
            return (), stage_result(schedule)
        if schedule.data is None:
            return (), StageResult(StageOutcome.SKIPPED, reason="no_schedule")
        people = await self._ports.oncall.on_call_now(schedule.data)
        if not people.is_success or people.data is None:
            logger.warning("incident_declare_on_call_failed", incident_id=self.incident.id, error_code=people.error_code)
            return (), stage_result(people)
        return people.data, _DONE

    async def report(self, people: tuple[OnCallPerson, ...]) -> StageResult:
        """Create the report in the placement and fill its placeholders; skipped when the record names one."""
        if self.incident.report is not None:
            return _DONE
        reports = self._ports.reports
        created = await reports.create_from_template(self.incident.title, self._request.placement)
        if not created.is_success or created.data is None:
            return stage_result(created)
        stored = self._keep(await self._ports.incidents.set_reference(self.incident.id, ReferenceKind.REPORT, created.data))
        if stored.outcome is not StageOutcome.DONE:
            return stored
        self._new_report = True
        values = self._texts.report_placeholders(self.incident, self.incident.conversation, people)
        return stage_result(await reports.replace_placeholders(created.data, values))

    async def video_call(self) -> StageResult:
        """Create the video call; skipped when the record names one."""
        if self.incident.video_call is not None:
            return _DONE
        created = await self._ports.video_calls.create()
        if not created.is_success or created.data is None:
            return stage_result(created)
        stored = self._keep(await self._ports.incidents.set_reference(self.incident.id, ReferenceKind.VIDEO_CALL, created.data))
        self._new_video_call = stored.outcome is StageOutcome.DONE
        return stored

    async def in_conversation(self, people: tuple[OnCallPerson, ...], on_call: StageResult) -> tuple[StageResult, StageResult]:
        """Set up, link, announce and invite in the conversation; both skipped when there is none."""
        chat = self._ports.chat
        conversation = self.incident.conversation
        if chat is None or conversation is None:
            skipped = StageResult(StageOutcome.SKIPPED, reason="no_conversation")
            return skipped, skipped
        talk = chat.conversations
        texts = self._texts
        incident = self.incident
        here = _languages(chat, conversation)
        results: list[StageResult] = [
            stage_result(await talk.set_topic(conversation, texts.topic(incident))),
            stage_result(await talk.set_purpose(conversation, texts.purpose(incident))),
            stage_result(await talk.create_canvas(conversation, texts.canvas(incident))),
        ]
        if self._new_report and incident.report is not None and incident.report.url:
            results.append(stage_result(await talk.add_bookmark(conversation, texts.report_bookmark(), incident.report.url)))
            results.append(stage_result(await talk.post(conversation, texts.report_posted(incident.report, here))))
        if self._new_video_call and incident.video_call is not None and incident.video_call.url:
            link = incident.video_call.url
            results.append(stage_result(await talk.add_bookmark(conversation, texts.video_call_bookmark(), link)))
            results.append(stage_result(await talk.post(conversation, texts.video_call_posted(incident.video_call, here))))
        warning = texts.severity_warning(incident, here)
        if warning is not None:
            results.append(await self._once("severity_warning", lambda: talk.post(conversation, warning)))
        alert = incident.source_alert
        if alert is not None:
            results.append(await self._once("source_alert", lambda: self._post_source_alert(talk, conversation, alert, here)))
        if self._policy.announcement_channel_id:
            channel = ConversationReference(
                system=conversation.system, tenant=conversation.tenant, vendor_id=self._policy.announcement_channel_id
            )
            announcement = texts.announcement(incident, conversation, _languages(chat, channel))
            results.append(await self._once("announcement", lambda: talk.post(channel, announcement)))
        invites = await self._invite(talk, conversation, people)
        if on_call.outcome is not StageOutcome.DONE:
            notice = texts.on_call_unavailable(incident, here)
            results.append(await self._once("on_call_unavailable", lambda: talk.post(conversation, notice)))
        steps = texts.next_steps(incident, here)
        results.append(await self._once("next_steps", lambda: talk.post(conversation, steps)))
        return _first_failure(results), invites

    async def _post_source_alert(
        self,
        talk: IncidentConversation,
        conversation: ConversationReference,
        alert: MessageReference,
        languages: tuple[str, ...],
    ) -> OperationResult[None]:
        if alert.url:
            bookmarked = await talk.add_bookmark(conversation, self._texts.source_alert_bookmark(), alert.url)
            if not bookmarked.is_success:
                return bookmarked
        posted = await talk.post(conversation, self._texts.source_alert_posted(alert, languages))
        return OperationResult.success() if posted.is_success else _as_none(posted)

    async def _invite(
        self, talk: IncidentConversation, conversation: ConversationReference, people: tuple[OnCallPerson, ...]
    ) -> StageResult:
        """Invite the declarer, the on-call people and each configured group in one call, each account once."""
        results: list[StageResult] = []
        accounts: list[str] = [self._request.declarer]
        on_call_ids, by_email = _on_call_accounts(people, conversation)
        accounts.extend(on_call_ids)
        if by_email:
            found = await talk.account_ids_for(conversation, by_email)
            results.append(stage_result(found))
            accounts.extend(found.data or ())
        for group_id in self._groups():
            members = await talk.group_members(conversation, group_id)
            if not members.is_success:
                logger.warning("incident_declare_group_read_failed", incident_id=self.incident.id, group_id=group_id)
            results.append(stage_result(members))
            accounts.extend(members.data or ())
        results.append(stage_result(await talk.invite(conversation, _unique(accounts))))
        return _first_failure(results)

    def _groups(self) -> list[str]:
        """The configured groups this incident invites: security, policy help, Notify placement."""
        policy = self._policy
        placement = self._request.placement
        groups: list[str] = []
        if self.incident.security_incident and policy.security_group_id:
            groups.append(policy.security_group_id)
        if self._request.policy_help and policy.policy_group_id:
            groups.append(policy.policy_group_id)
        notify = (
            placement is not None
            and policy.notify_management_placement_id
            and placement.vendor_id == policy.notify_management_placement_id
        )
        if notify and policy.notify_management_group_id:
            groups.append(policy.notify_management_group_id)
        return groups

    async def _once[T](self, kind: str, post: Callable[[], Awaitable[OperationResult[T]]]) -> StageResult:
        """Post one message once per incident: claimed before, completed on success, released on failure."""
        claims = self._ports.claims
        key = f"incident:declare_message:{self.incident.id}:{kind}"
        claimed = await claims.claim(key)
        if claimed.result is not ClaimResult.NEW or claimed.claim_token is None:
            return StageResult(StageOutcome.SKIPPED, reason="already_posted")
        result = stage_result(await post())
        if result.outcome is StageOutcome.DONE:
            await claims.complete(key, {"posted": True}, claimed.claim_token)
        else:
            await claims.release(key, claimed.claim_token)
        return result

    def _keep(self, written: OperationResult[Incident]) -> StageResult:
        """Keep the incident as a write returned it; a failed write keeps the last one."""
        if written.is_success and written.data is not None:
            self.incident = written.data
        return stage_result(written)


def _languages(chat: ChatSurface, conversation: ConversationReference) -> tuple[str, ...]:
    """The languages, in order, of a message posted to ``conversation``."""
    return chat.languages.shared_languages(
        system=conversation.system, tenant=conversation.tenant, conversation_id=conversation.vendor_id
    )


def _on_call_accounts(people: Sequence[OnCallPerson], conversation: ConversationReference) -> tuple[list[str], list[str]]:
    """Split the on-call people into accounts on the conversation's platform and emails to resolve."""
    platform = conversation.system.value
    accounts: list[str] = []
    emails: list[str] = []
    for person in people:
        account = person.account
        if account is not None and account.platform == platform and account.tenant in (None, conversation.tenant):
            accounts.append(account.account_id)
        elif person.email:
            emails.append(person.email)
    return accounts, emails


def _unique(account_ids: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(account_id for account_id in account_ids if account_id))


def _first_failure(results: Sequence[StageResult]) -> StageResult:
    return next((result for result in results if result.outcome is StageOutcome.FAILED), _DONE)


def _as_none[T](result: OperationResult[T]) -> OperationResult[None]:
    return OperationResult.error(
        status=result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )
