"""In-memory incident core stores and report with the real implementations' observable rules.

For tests and local runs. ``InMemoryStatusUpdateStore``: appends only where
nothing is stored, state changes only from the expected state, a repeat of a
write that landed is a conflict, newest first. ``InMemoryIncidentStore``: the incident reads
with the same classifications as ``RecordIncidentStore``, and the field writes with
its validation, replay and open-list rules. ``InMemoryTimelineStore``: one entry
per key, a repeat a replay that succeeds. ``InMemoryIncidentReport``:
the ``GoogleDocsIncidentReport`` rules (Google references only, unknown reports not
found, empty document ids refused naming the key, no draft copy without content; the
timeline holds one entry per message link, a message without a link or a system entry
unsupported, and an unknown report's timeline unreadable).
``InMemoryIncidentConversation``: the ``SlackIncidentConversation`` rules (Slack
references only, unknown conversations not found, archived or non-member
conversations not writable and refusing writes, repeated archives and empty
invites succeeding). ``InMemoryVideoCall``: the ``GoogleMeetVideoCall`` rules
(Google references under the tenant, a link only for Google references).
``InMemoryMeetingScheduler``: the ``GoogleCalendarMeetingScheduler`` rules (the id
derived from the key, a replayed key returning the booked meeting and a deleted
one's key a permanent 409, deleted or unknown meetings not found, a repeated
delete succeeding, patches applying only the fields set). ``InMemoryCalendarAvailability``:
the ``GoogleCalendarAvailability`` rules (one answer per case-folded address,
unknown is ``None`` and never free, intervals clipped to the window).
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from capabilities.oncall.api import ScheduleReference
from contracts.languages import MultilingualText
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole, IncidentStatus
from features.incident.core.adapters.google_calendar import meeting_event_id, meeting_summary
from features.incident.core.adapters.google_docs import timeline_entry_url, timeline_message_key
from features.incident.core.adapters.list_rows import list_row
from features.incident.core.adapters.slack import slack_channel_name, slack_conversation_label, slack_conversation_link
from features.incident.core.adapters.timeline_items import entry_key
from features.incident.core.api import CalendarAvailability, MeetingScheduler
from features.incident.core.domain import (
    AttendeeBusy,
    BindingKind,
    BusyInterval,
    ConversationName,
    ConversationReference,
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    Incident,
    IncidentBinding,
    IncidentChanges,
    MeetingChange,
    MeetingRequest,
    MeetingStatus,
    MessageReference,
    ReferenceKind,
    ReportPlacement,
    ReportReference,
    ResourceReference,
    ScheduledMeeting,
    SectionDraft,
    StatusUpdate,
    StatusUpdateState,
    TimelineEntry,
    VideoCallReference,
)
from features.incident.core.store import (
    IncidentStore,
    StatusUpdateStore,
    TimelineStore,
    ambiguous_conversation,
    apply_changes,
    apply_roles,
    no_such_incident,
    not_an_incident,
    record_conflict,
    select_active_bindings,
    severity_entry,
    validate_attachment,
    validate_field_update,
    validate_new_incident,
    validate_reference,
    validate_roles,
    validate_status_change,
)


class InMemoryTimelineStore(TimelineStore):
    """Hold timeline entries in a dict keyed by incident id and entry key."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], TimelineEntry] = {}

    def append(self, entry: TimelineEntry) -> OperationResult[TimelineEntry]:
        """Store ``entry`` unless its key is taken; a taken key is a replay that succeeds."""
        self._entries.setdefault((entry.incident_id, entry_key(entry.posted_at, entry.entry_id)), entry)
        return OperationResult.success(data=entry)

    def entries(self, incident_id: str) -> tuple[TimelineEntry, ...]:
        """Return the incident's entries in key order (time, then id)."""
        return tuple(entry for (owner, _), entry in sorted(self._entries.items()) if owner == incident_id)


class InMemoryStatusUpdateStore(StatusUpdateStore):
    """Hold status updates in a dict keyed by incident id and sequence."""

    def __init__(self) -> None:
        self._updates: dict[tuple[str, int], StatusUpdate] = {}

    async def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence; any record already there is a conflict."""
        if (update.incident_id, update.sequence) in self._updates:
            return _conflict()
        self._updates[(update.incident_id, update.sequence)] = update
        return OperationResult.success(data=update)

    async def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Replace the stored update with ``update`` while its stored state is ``expected_state``.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        if not expected_state.can_move_to(update.state):
            raise ValueError(f"no status update transition from {expected_state} to {update.state}")
        stored = self._updates.get((update.incident_id, update.sequence))
        if stored is None or stored.state is not expected_state:
            return _conflict()
        self._updates[(update.incident_id, update.sequence)] = update
        return OperationResult.success(data=update)

    async def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update, or success with ``None`` when it has none."""
        updates = self._newest_first(incident_id)
        return OperationResult.success(data=updates[0] if updates else None)

    async def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""
        return OperationResult.success(data=self._newest_first(incident_id))

    def _newest_first(self, incident_id: str) -> tuple[StatusUpdate, ...]:
        updates = (update for (owner, _), update in self._updates.items() if owner == incident_id)
        return tuple(sorted(updates, key=lambda update: update.sequence, reverse=True))


def _conflict[T]() -> OperationResult[T]:
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="The status update was changed or taken by another writer.",
        error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
    )


class InMemoryIncidentStore(IncidentStore):
    """Hold seeded incidents in a dict keyed by id; every seeded incident is readable.

    Open incidents are listed by ``declared_at``, a stand-in for the
    ``opened_at`` time the real store orders by and this fake does not hold.
    ``create``, ``attach_conversation``, ``set_reference`` and the field writes share
    the real store's validation; the fake holds no record version and has no
    concurrent writer, so only a different conversation conflicts and no guard is
    ever lost. Severity entries go to ``timeline`` (a new ``InMemoryTimelineStore``
    when none is given).
    """

    def __init__(self, timeline: TimelineStore | None = None) -> None:
        self.timeline = InMemoryTimelineStore() if timeline is None else timeline
        self._incidents: dict[str, Incident] = {}
        self._open: set[str] = set()
        self._bindings: dict[tuple[str, str, str, str, str], IncidentBinding] = {}

    def bind(self, binding: IncidentBinding) -> None:
        """Store ``binding``; one for an incident that is not seeded is dangling, as in the real store."""
        key = (binding.incident_id, binding.kind.value, binding.system.value, binding.tenant, binding.vendor_id)
        self._bindings[key] = binding

    def seed(self, incident: Incident, *, open: bool | None = None) -> None:
        """Store ``incident``; ``open`` puts it in the open list and defaults to whether its status is open."""
        self._incidents[incident.id] = incident
        if incident.status.is_open if open is None else open:
            self._open.add(incident.id)
        else:
            self._open.discard(incident.id)

    async def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the seeded incident with this id."""
        incident = self._incidents.get(incident_id)
        return OperationResult.success(data=incident) if incident is not None else no_such_incident()

    async def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one incident the lookup order of ``RecordIncidentStore`` finds: bindings first, then the conversation match."""
        if not conversation.vendor_id.strip():
            return not_an_incident()
        candidates = [
            binding
            for binding in self._bindings.values()
            if binding.kind is BindingKind.CHAT_CONVERSATION and binding.vendor_id == conversation.vendor_id
        ]
        live = [
            self._incidents[binding.incident_id]
            for binding in select_active_bindings(conversation, candidates)
            if binding.incident_id in self._incidents
        ]
        if len(live) > 1:
            return ambiguous_conversation(conversation, match_count=len(live))
        if live:
            return OperationResult.success(data=live[0])
        matches = [
            incident
            for incident in self._incidents.values()
            if incident.conversation is not None
            and (incident.conversation.system, incident.conversation.tenant, incident.conversation.vendor_id)
            == (conversation.system, conversation.tenant, conversation.vendor_id)
        ]
        if not conversation.vendor_id.strip() or not matches:
            return not_an_incident()
        if len(matches) > 1:
            return ambiguous_conversation(conversation, match_count=len(matches))
        return OperationResult.success(data=matches[0])

    async def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return the incidents seeded open, oldest declaration first."""
        incidents = (self._incidents[incident_id] for incident_id in self._open)
        return OperationResult.success(data=sorted(incidents, key=lambda incident: incident.declared_at))

    async def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return the seeded incident's security flag."""
        incident = self._incidents.get(incident_id)
        return OperationResult.success(data=incident.security_incident) if incident is not None else no_such_incident()

    async def create(self, incident: Incident) -> OperationResult[Incident]:
        """Store the incident; a stored incident under the id is a replay that changes nothing.

        Raises:
            ValueError: see ``IncidentStore.create``.
        """
        validate_new_incident(incident)
        stored = self._incidents.get(incident.id)
        if stored is not None:
            return OperationResult.success(data=stored)
        self.seed(incident)
        return OperationResult.success(data=incident)

    async def attach_conversation(self, incident_id: str, binding: IncidentBinding) -> OperationResult[Incident]:
        """Store the binding and, for a primary one, make its conversation the incident's.

        Raises:
            ValueError: see ``IncidentStore.attach_conversation``.
        """
        validate_attachment(incident_id, binding)
        stored = self._incidents.get(incident_id)
        if stored is None:
            return no_such_incident()
        conversation = ConversationReference(
            system=binding.system, tenant=binding.tenant, vendor_id=binding.vendor_id, url=binding.url
        )
        current = stored.conversation
        if (
            binding.primary
            and current is not None
            and (current.system, current.tenant, current.vendor_id)
            != (
                conversation.system,
                conversation.tenant,
                conversation.vendor_id,
            )
        ):
            return record_conflict()
        self.bind(binding)
        if binding.primary and current is None:
            stored = replace(stored, conversation=conversation)
            self._incidents[incident_id] = stored
        return OperationResult.success(data=stored)

    async def set_reference(
        self, incident_id: str, kind: ReferenceKind, reference: ResourceReference
    ) -> OperationResult[Incident]:
        """Replace the incident's reference of ``kind``.

        Raises:
            ValueError: see ``IncidentStore.set_reference``.
        """
        validate_reference(kind, reference)
        stored = self._incidents.get(incident_id)
        if stored is None:
            return no_such_incident()
        # The field is chosen at runtime; validate_reference has checked its type.
        changes: dict[str, Any] = {kind.value: reference}
        updated = replace(stored, **changes)
        self._incidents[incident_id] = updated
        return OperationResult.success(data=updated)

    async def update_fields(
        self, incident_id: str, changes: IncidentChanges, *, by: str, at: datetime
    ) -> OperationResult[Incident]:
        """Write the named fields; a severity change appends its entry to ``timeline``.

        Raises:
            ValueError: see ``IncidentStore.update_fields``.
        """
        validate_field_update(by, at)
        stored = self._incidents.get(incident_id)
        if stored is None:
            return no_such_incident()
        updated = self._write(stored, apply_changes(stored, changes))
        entry = severity_entry(stored, updated, by=by, at=at)
        if entry is not None:
            self.timeline.append(entry)
        return OperationResult.success(data=updated)

    async def set_roles(self, incident_id: str, roles: Mapping[IncidentRole, str | None]) -> OperationResult[Incident]:
        """Give each named role its holder.

        Raises:
            ValueError: see ``IncidentStore.set_roles``.
        """
        validate_roles(roles)
        return self._apply(incident_id, lambda stored: apply_roles(stored, roles))

    async def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
        """Set the status; closing leaves the open list and reopening rejoins it.

        Raises:
            ValueError: see ``IncidentStore.set_status``.
        """
        validate_status_change(status, at)
        return self._apply(incident_id, lambda stored: replace(stored, status=status))

    def _apply(self, incident_id: str, desire: Callable[[Incident], Incident]) -> OperationResult[Incident]:
        stored = self._incidents.get(incident_id)
        if stored is None:
            return no_such_incident()
        return OperationResult.success(data=self._write(stored, desire(stored)))

    def _write(self, stored: Incident, updated: Incident) -> Incident:
        """Store ``updated`` unless it equals ``stored`` (a replay writes nothing)."""
        if updated != stored:
            self.seed(updated)
        return updated


@dataclass
class _StoredReport:
    title: str
    folder_id: str
    sections: list[DocumentSection] = field(default_factory=list)
    placeholders: dict[str, str] = field(default_factory=dict)
    status: IncidentStatus | None = None
    timeline: dict[tuple[str, str], TimelineEntry] = field(default_factory=dict)


@dataclass(frozen=True)
class DraftCopy:
    """One draft copy the fake was asked to write."""

    report: ReportReference
    drafts: tuple[SectionDraft, ...]
    fields: tuple[DocumentField, ...]
    links: Mapping[str, str]


class InMemoryIncidentReport:
    """Hold incident reports in a dict keyed by document id; every call is recorded for assertions.

    Built with the Google tenant and the [incident_core] document ids it stands in
    for. ``next_ids`` fixes the ids of the reports it creates, in order; past them
    ids are ``report-<n>``. ``seed_sections`` makes an existing report known.
    ``placements`` are the (folder id, label) pairs ``list_placements`` returns,
    sorted by label.
    """

    def __init__(
        self,
        *,
        tenant: str = "C0GOOGLE",
        folder_id: str = "F0INCIDENTS",
        report_template_id: str = "T0TEMPLATE",
        next_ids: Sequence[str] = (),
        placements: Sequence[tuple[str, str]] = (),
    ) -> None:
        self._tenant = tenant
        self._placements = tuple(placements)
        self._folder_id = folder_id
        self._report_template_id = report_template_id
        self._next_ids = list(next_ids)
        self._reports: dict[str, _StoredReport] = {}
        self.read_from: list[ReportReference] = []
        self.draft_copies: list[DraftCopy] = []

    def seed_sections(self, report: ReportReference, sections: Sequence[DocumentSection]) -> None:
        """Make ``report`` known with ``sections``, as if its template had them."""
        stored = self._reports.setdefault(report.vendor_id, _StoredReport(title="", folder_id=self._folder_id))
        stored.sections = list(sections)

    def filed_in(self, report: ReportReference) -> str:
        """Return the folder a created report was filed in."""
        return self._reports[report.vendor_id].folder_id

    def status_text_of(self, report: ReportReference) -> IncidentStatus | None:
        """Return the status last set on ``report``'s status line, ``None`` before any."""
        return self._reports[report.vendor_id].status

    def placeholders_of(self, report: ReportReference) -> Mapping[str, str]:
        """Return the placeholder values applied to ``report`` so far."""
        return dict(self._reports[report.vendor_id].placeholders)

    def timeline_of(self, report: ReportReference) -> tuple[TimelineEntry, ...]:
        """Return the entries ``report``'s timeline holds, in chronological order."""
        return tuple(sorted(self._reports[report.vendor_id].timeline.values(), key=lambda entry: entry.posted_at))

    async def list_placements(self) -> OperationResult[tuple[ReportPlacement, ...]]:
        """Return the seeded placements sorted by label; no incident folder refuses naming its key."""
        if not self._folder_id:
            return _report_not_configured("incident_core.folder_id")
        placements = (
            ReportPlacement(
                system=WorkplaceSystem.GOOGLE,
                tenant=self._tenant,
                vendor_id=folder_id,
                url=f"https://drive.google.com/drive/folders/{folder_id}",
                label=label,
            )
            for folder_id, label in self._placements
        )
        return OperationResult.success(tuple(sorted(placements, key=lambda placement: placement.label)))

    async def create_from_template(
        self, title: str, placement: ReportPlacement | None = None
    ) -> OperationResult[ReportReference]:
        """Create a known report filed in ``placement`` or the configured folder; an empty document id refuses naming its key."""
        if placement is not None and placement.system is not WorkplaceSystem.GOOGLE:
            return OperationResult.permanent_error(
                f"Google Docs cannot file a report on {placement.system.value}", ErrorCode.UNSUPPORTED_OPERATION
            )
        if not self._folder_id:
            return _report_not_configured("incident_core.folder_id")
        if not self._report_template_id:
            return _report_not_configured("incident_core.report_template_id")
        document_id = self._next_ids.pop(0) if self._next_ids else f"report-{len(self._reports) + 1}"
        folder_id = placement.vendor_id if placement is not None else self._folder_id
        self._reports[document_id] = _StoredReport(title=title, folder_id=folder_id)
        return OperationResult.success(
            data=ReportReference(
                system=WorkplaceSystem.GOOGLE,
                tenant=self._tenant,
                vendor_id=document_id,
                url=f"https://docs.google.com/document/d/{document_id}/edit",
            )
        )

    async def replace_placeholders(self, report: ReportReference, values: Mapping[str, str]) -> OperationResult[None]:
        """Record the values on a known report."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _no_such_report()
        stored.placeholders.update(values)
        return OperationResult.success()

    async def set_status_text(self, report: ReportReference, status: IncidentStatus) -> OperationResult[None]:
        """Record the status on a known report's status line."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _no_such_report()
        stored.status = status
        return OperationResult.success()

    async def read_sections(self, report: ReportReference) -> OperationResult[Sequence[DocumentSection]]:
        """Return a known report's sections in order."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _no_such_report()
        self.read_from.append(report)
        return OperationResult.success(data=tuple(stored.sections))

    async def write_draft_copy(
        self,
        report: ReportReference,
        drafts: Sequence[SectionDraft],
        fields: Sequence[DocumentField],
        links: Mapping[str, str],
    ) -> OperationResult[DraftWriteResult]:
        """Record a draft copy of a known report; nothing to write is a transient failure, as the writer returns."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _no_such_report()
        if not drafts and not fields:
            return OperationResult.transient_error(message="The draft copy could not be written")
        self.draft_copies.append(DraftCopy(report, tuple(drafts), tuple(fields), dict(links)))
        return OperationResult.success(
            data=DraftWriteResult(document_id=f"{report.vendor_id}-draft-{len(self.draft_copies)}", created=True)
        )

    async def append_timeline_entry(self, report: ReportReference, entry: TimelineEntry) -> OperationResult[None]:
        """Hold ``entry`` once per message link on a known report; an unknown report is unreadable, as the adapter says."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        url = timeline_entry_url(entry)
        if url is None:
            return _unholdable_timeline_entry()
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _unreadable_report()
        stored.timeline.setdefault(timeline_message_key(url), entry)
        return OperationResult.success()

    async def remove_timeline_entry(self, report: ReportReference, message: MessageReference) -> OperationResult[None]:
        """Drop the entry of ``message`` from a known report; an absent one is a success."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        if not message.url:
            return _unholdable_timeline_entry()
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _unreadable_report()
        stored.timeline.pop(timeline_message_key(message.url), None)
        return OperationResult.success()

    def link(self, report: ReportReference) -> str | None:
        """Return the stored link of the report."""
        return report.url


def _unholdable_timeline_entry[T]() -> OperationResult[T]:
    return OperationResult.permanent_error(
        "The report timeline holds captured messages identified by their link", ErrorCode.UNSUPPORTED_OPERATION
    )


def _unreadable_report[T]() -> OperationResult[T]:
    return OperationResult.transient_error("Document could not be read", error_code=ErrorCode.DOCUMENT_UNREADABLE)


def _report_unsupported[T](report: ReportReference) -> OperationResult[T]:
    return OperationResult.permanent_error(
        f"Google Docs cannot reach a report on {report.system.value}", ErrorCode.UNSUPPORTED_OPERATION
    )


def _no_such_report[T]() -> OperationResult[T]:
    return OperationResult.error(OperationStatus.NOT_FOUND, message="No such report")


def _report_not_configured[T](key: str) -> OperationResult[T]:
    return OperationResult.permanent_error(f"{key} is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)


@dataclass(frozen=True)
class SeededAccount:
    """A person ``InMemoryIncidentConversation`` knows: an email (or none), and whether a human and active.

    A bot or app user is ``human=False``; a deactivated account is ``active=False``.
    """

    email: str | None
    human: bool = True
    active: bool = True


@dataclass
class _StoredConversation:
    archived: bool
    member: bool
    purpose: str | None = None
    posts: list[str] = field(default_factory=list)
    bookmarks: list[tuple[str, str]] = field(default_factory=list)
    invited: list[str] = field(default_factory=list)
    topic: str | None = None
    canvas: str | None = None
    private: bool = False
    blocks: list[tuple[Mapping[str, object], ...]] = field(default_factory=list)


class InMemoryIncidentConversation:
    """Hold Slack conversations in a dict keyed by channel id; every write is recorded for assertions.

    Built with the Slack tenant it stands in for and the ids of open, archived and
    non-member conversations, and private ones the bot left (``private_non_member_ids``,
    whose join is refused); any other id is not found. ``joined`` lists the
    conversations a join made the bot a member of. Posts get ``ts`` values
    ``1700000000.00000<n>`` in order. ``checked`` lists the conversations whose
    writability was asked.

    ``names`` names some of those conversations (Slack channel name to id) and
    ``foreign_names`` are names the bot cannot see; creating under any of them is
    ``CONVERSATION_NAME_TAKEN``. A ``ConversationName`` is rendered with the Slack
    adapter's ``slack_channel_name``, the platform this fake stands in for. A created conversation is open, the bot a member,
    with id ``C0NEW<n>``. ``find_own`` finds named conversations that are open and
    where the bot is a member. ``groups`` maps a user group id to its members and
    ``accounts`` an email to its account id. ``members`` maps a conversation id to its
    account ids and ``people`` an account id to its ``SeededAccount``: ``members`` answers the
    human, active ones, ``account_emails`` their emails (``None`` for no email or no account).
    """

    def __init__(
        self,
        *,
        tenant: str = "T0SLACK",
        open_ids: Sequence[str] = (),
        archived_ids: Sequence[str] = (),
        non_member_ids: Sequence[str] = (),
        private_non_member_ids: Sequence[str] = (),
        names: Mapping[str, str] | None = None,
        foreign_names: Sequence[str] = (),
        groups: Mapping[str, Sequence[str]] | None = None,
        accounts: Mapping[str, str] | None = None,
        members: Mapping[str, Sequence[str]] | None = None,
        people: Mapping[str, SeededAccount] | None = None,
    ) -> None:
        self._tenant = tenant
        self._accounts = dict(accounts or {})
        self._members = {vendor_id: tuple(ids) for vendor_id, ids in (members or {}).items()}
        self._people = dict(people or {})
        self._conversations: dict[str, _StoredConversation] = {}
        for vendor_id in open_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=False, member=True)
        for vendor_id in archived_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=True, member=True)
        for vendor_id in non_member_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=False, member=False)
        for vendor_id in private_non_member_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=False, member=False, private=True)
        self._posted = 0
        self._created = 0
        self._names = dict(names or {})
        self._foreign_names = frozenset(foreign_names)
        self._groups = {group_id: tuple(members) for group_id, members in (groups or {}).items()}
        self.checked: list[ConversationReference] = []
        self.joined: list[ConversationReference] = []

    def topic_of(self, conversation: ConversationReference) -> str | None:
        """Return the topic last set on ``conversation``."""
        return self._conversations[conversation.vendor_id].topic

    def canvas_of(self, conversation: ConversationReference) -> str | None:
        """Return the markdown ``conversation``'s canvas was created from."""
        return self._conversations[conversation.vendor_id].canvas

    def is_private(self, conversation: ConversationReference) -> bool:
        """Say whether ``conversation`` was created private."""
        return self._conversations[conversation.vendor_id].private

    def blocks_in(self, conversation: ConversationReference) -> Sequence[tuple[Mapping[str, object], ...]]:
        """Return the blocks of each post to ``conversation``, in order (empty for a text-only post)."""
        return tuple(self._conversations[conversation.vendor_id].blocks)

    async def create(self, name: ConversationName, *, private: bool) -> OperationResult[ConversationReference]:
        """Create an open conversation the bot belongs to; a name in use is ``CONVERSATION_NAME_TAKEN``."""
        channel_name = slack_channel_name(name)
        if channel_name in self._names or channel_name in self._foreign_names:
            return OperationResult.permanent_error(f"Slack channel name taken: {channel_name}", ErrorCode.CONVERSATION_NAME_TAKEN)
        self._created += 1
        vendor_id = f"C0NEW{self._created}"
        self._conversations[vendor_id] = _StoredConversation(archived=False, member=True, private=private)
        self._names[channel_name] = vendor_id
        return OperationResult.success(
            ConversationReference(system=WorkplaceSystem.SLACK, tenant=self._tenant, vendor_id=vendor_id)
        )

    async def find_own(self, name: ConversationName) -> OperationResult[ConversationReference | None]:
        """Return the open conversation named as ``name`` renders where the bot is a member, or ``None``."""
        vendor_id = self._names.get(slack_channel_name(name))
        stored = self._conversations.get(vendor_id) if vendor_id is not None else None
        if vendor_id is None or stored is None or stored.archived or not stored.member:
            return OperationResult.success(None)
        return OperationResult.success(
            ConversationReference(system=WorkplaceSystem.SLACK, tenant=self._tenant, vendor_id=vendor_id)
        )

    def posts_in(self, conversation: ConversationReference) -> Sequence[str]:
        """Return the texts posted to ``conversation``, in order."""
        return tuple(self._conversations[conversation.vendor_id].posts)

    def purpose_of(self, conversation: ConversationReference) -> str | None:
        """Return the purpose last set on ``conversation``."""
        return self._conversations[conversation.vendor_id].purpose

    def bookmarks_of(self, conversation: ConversationReference) -> Sequence[tuple[str, str]]:
        """Return the (title, link) bookmarks added to ``conversation``."""
        return tuple(self._conversations[conversation.vendor_id].bookmarks)

    def invited_to(self, conversation: ConversationReference) -> Sequence[str]:
        """Return the account ids invited to ``conversation``, in order."""
        return tuple(self._conversations[conversation.vendor_id].invited)

    async def post(
        self,
        conversation: ConversationReference,
        text: str | MultilingualText,
        *,
        blocks: Sequence[Mapping[str, object]] = (),
    ) -> OperationResult[MessageReference]:
        """Record ``text`` as the Slack adapter lays it out, and its blocks; refused where the bot cannot write."""
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        self._posted += 1
        stored.posts.append(text.plain_text() if isinstance(text, MultilingualText) else text)
        stored.blocks.append(tuple(blocks))
        return OperationResult.success(
            MessageReference(
                system=WorkplaceSystem.SLACK,
                tenant=conversation.tenant,
                conversation_id=conversation.vendor_id,
                message_id=f"1700000000.{self._posted:06d}",
            )
        )

    async def account_ids_for(
        self, conversation: ConversationReference, emails: Sequence[str]
    ) -> OperationResult[tuple[str, ...]]:
        """Return the known emails' account ids in order, skipping unknown emails."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        return OperationResult.success(tuple(self._accounts[email] for email in emails if email in self._accounts))

    async def members(self, conversation: ConversationReference) -> OperationResult[tuple[str, ...]]:
        """Return the seeded members that are known, human and active, in order; an unknown conversation is not found."""
        stored = self._known(conversation)
        if isinstance(stored, OperationResult):
            return stored
        return OperationResult.success(
            tuple(
                account_id
                for account_id in self._members.get(conversation.vendor_id, ())
                if (person := self._people.get(account_id)) is not None and person.human and person.active
            )
        )

    async def account_emails(
        self, conversation: ConversationReference, account_ids: Sequence[str]
    ) -> OperationResult[Mapping[str, str | None]]:
        """Return each asked account's seeded email; an account without one, or unknown, is ``None``."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        return OperationResult.success(
            {account_id: person.email if (person := self._people.get(account_id)) else None for account_id in account_ids}
        )

    async def set_purpose(self, conversation: ConversationReference, text: str) -> OperationResult[None]:
        """Record the purpose; refused where the bot cannot write."""
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        stored.purpose = text
        return OperationResult.success()

    async def set_topic(self, conversation: ConversationReference, text: str) -> OperationResult[None]:
        """Record the topic; refused where the bot cannot write."""
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        stored.topic = text
        return OperationResult.success()

    async def create_canvas(self, conversation: ConversationReference, markdown: str) -> OperationResult[None]:
        """Record the canvas once; a conversation that has one keeps it and succeeds."""
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        if stored.canvas is None:
            stored.canvas = markdown
        return OperationResult.success()

    async def group_members(self, conversation: ConversationReference, group_id: str) -> OperationResult[tuple[str, ...]]:
        """Return the seeded members of ``group_id``; an unknown group is not found."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        members = self._groups.get(group_id)
        if members is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND, "Slack user group not found: no_such_subteam", "no_such_subteam"
            )
        return OperationResult.success(members)

    async def add_bookmark(self, conversation: ConversationReference, title: str, link: str) -> OperationResult[None]:
        """Record the bookmark; refused where the bot cannot write."""
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        stored.bookmarks.append((title, link))
        return OperationResult.success()

    async def invite(self, conversation: ConversationReference, account_ids: Sequence[str]) -> OperationResult[None]:
        """Record the accounts not yet invited; no accounts succeeds without touching the conversation."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        if not account_ids:
            return OperationResult.success()
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        stored.invited.extend(account for account in account_ids if account not in stored.invited)
        return OperationResult.success()

    async def archive(self, conversation: ConversationReference) -> OperationResult[None]:
        """Archive the conversation; an archived one stays archived and succeeds."""
        stored = self._known(conversation)
        if isinstance(stored, OperationResult):
            return stored
        if stored.archived:
            return OperationResult.success()
        if not stored.member:
            return _not_writable("not_in_channel")
        stored.archived = True
        return OperationResult.success()

    async def join(self, conversation: ConversationReference) -> OperationResult[None]:
        """Make the bot a member; an archived conversation, or a private one it is not in, is not writable."""
        stored = self._known(conversation)
        if isinstance(stored, OperationResult):
            return stored
        if stored.archived:
            return _not_writable("is_archived")
        if not stored.member and stored.private:
            return _not_writable("method_not_supported_for_channel_type")
        if not stored.member:
            self.joined.append(conversation)
        stored.member = True
        return OperationResult.success()

    def is_archived(self, conversation: ConversationReference) -> bool:
        """Say whether ``conversation`` is archived."""
        return self._conversations[conversation.vendor_id].archived

    async def purpose(self, conversation: ConversationReference) -> OperationResult[str]:
        """Return the purpose last set (or seeded) on the conversation; an empty string when none."""
        stored = self._known(conversation)
        if isinstance(stored, OperationResult):
            return stored
        return OperationResult.success(stored.purpose or "")

    def seed_purpose(self, conversation: ConversationReference, text: str) -> None:
        """Give ``conversation`` the purpose ``text`` without a write, as a channel created before the bot's writes has one."""
        self._conversations[conversation.vendor_id].purpose = text

    async def is_writable(self, conversation: ConversationReference) -> OperationResult[bool]:
        """Answer whether the conversation is open and the bot a member."""
        stored = self._known(conversation)
        if isinstance(stored, OperationResult):
            return stored
        self.checked.append(conversation)
        return OperationResult.success(not stored.archived and stored.member)

    def _known(self, conversation: ConversationReference) -> _StoredConversation | OperationResult[Any]:
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        stored = self._conversations.get(conversation.vendor_id)
        if stored is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND, "Slack conversation not found: channel_not_found", "channel_not_found"
            )
        return stored

    def _writable(self, conversation: ConversationReference) -> _StoredConversation | OperationResult[Any]:
        stored = self._known(conversation)
        if isinstance(stored, OperationResult):
            return stored
        if stored.archived:
            return _not_writable("is_archived")
        if not stored.member:
            return _not_writable("not_in_channel")
        return stored


def _conversation_unsupported[T](conversation: ConversationReference) -> OperationResult[T]:
    return OperationResult.permanent_error(
        f"Slack cannot reach a conversation on {conversation.system.value}", ErrorCode.UNSUPPORTED_OPERATION
    )


def _not_writable[T](slack_code: str) -> OperationResult[T]:
    return OperationResult.permanent_error(f"Slack write failed: {slack_code}", ErrorCode.CONVERSATION_NOT_WRITABLE)


class InMemoryVideoCall:
    """Create video calls under the Google tenant it is built with; every created call is recorded.

    Calls are ``spaces/call-<n>`` with a meet.google.com link. ``fail_with`` makes
    every create return that error result instead.
    """

    def __init__(self, *, tenant: str = "C0GOOGLE", fail_with: OperationResult[VideoCallReference] | None = None) -> None:
        self._tenant = tenant
        self._fail_with = fail_with
        self.created: list[VideoCallReference] = []

    async def create(self) -> OperationResult[VideoCallReference]:
        """Return a new Google call reference, or the configured failure."""
        if self._fail_with is not None:
            return self._fail_with
        n = len(self.created) + 1
        call = VideoCallReference(
            system=WorkplaceSystem.GOOGLE,
            tenant=self._tenant,
            vendor_id=f"spaces/call-{n}",
            url=f"https://meet.google.com/call-{n}",
        )
        self.created.append(call)
        return OperationResult.success(call)

    def link(self, call: VideoCallReference) -> str | None:
        """Return the stored link of a Google call; a call of another system has none here."""
        return call.url if call.system is WorkplaceSystem.GOOGLE else None


def _meeting_not_found[T](meeting_id: str) -> OperationResult[T]:
    return OperationResult.error(
        status=OperationStatus.NOT_FOUND, message=f"meeting {meeting_id} is not on the calendar", error_code=ErrorCode.NOT_FOUND
    )


class InMemoryMeetingScheduler(MeetingScheduler):
    """Hold one calendar's meetings in memory with the Google Calendar scheduler's observable rules.

    ``requests`` records each booked request, ``changes`` each applied patch and ``deletions``
    each deleted id. ``fail_with`` makes every call return that error result; ``fail_on``
    maps an operation name (``create``, ``get``, ``patch``, ``delete``) to the error result it
    returns. ``edit_by_hand`` changes a stored meeting as a person editing the shared calendar
    would, so a test can show the calendar owning the time.
    """

    def __init__(self, *, fail_with: OperationResult[Any] | None = None) -> None:
        self.meetings: dict[str, ScheduledMeeting] = {}
        self.deleted: set[str] = set()
        self.requests: list[MeetingRequest] = []
        self.changes: list[tuple[str, MeetingChange]] = []
        self.deletions: list[str] = []
        self.fail_with = fail_with
        self.fail_on: dict[str, OperationResult[Any]] = {}

    def _failure(self, operation: str) -> OperationResult[Any] | None:
        return self.fail_with if self.fail_with is not None else self.fail_on.get(operation)

    def edit_by_hand(self, meeting_id: str, **fields: Any) -> None:
        """Replace fields of a stored meeting, as a hand edit on the calendar does."""
        self.meetings[meeting_id] = replace(self.meetings[meeting_id], **fields)

    async def create(self, request: MeetingRequest) -> OperationResult[ScheduledMeeting]:
        """Book the meeting under the id its key derives; a replay returns it, a deleted one's key is a 409."""
        if (failure := self._failure("create")) is not None:
            return failure
        meeting_id = meeting_event_id(request.idempotency_key)
        if meeting_id in self.deleted:
            return OperationResult.permanent_error(f"meeting {meeting_id} was deleted; a new booking needs a new key", "409")
        if meeting_id in self.meetings:
            return OperationResult.success(self.meetings[meeting_id])
        meeting = ScheduledMeeting(
            id=meeting_id,
            title=meeting_summary(request),
            start=request.start,
            end=request.end,
            status=MeetingStatus.CONFIRMED,
            url=f"https://calendar.google.com/calendar/event?eid={meeting_id}",
            video_url=f"https://meet.google.com/{meeting_id[:3]}-{meeting_id[3:7]}-{meeting_id[7:10]}",
            attendees=request.attendees,
        )
        self.meetings[meeting_id] = meeting
        self.requests.append(request)
        return OperationResult.success(meeting)

    async def get(self, meeting_id: str) -> OperationResult[ScheduledMeeting]:
        """Return the stored meeting; a deleted or unknown one is not found."""
        if (failure := self._failure("get")) is not None:
            return failure
        if meeting_id in self.deleted or meeting_id not in self.meetings:
            return _meeting_not_found(meeting_id)
        return OperationResult.success(self.meetings[meeting_id])

    async def patch(self, meeting_id: str, change: MeetingChange) -> OperationResult[ScheduledMeeting]:
        """Apply only the fields the change sets; a deleted or unknown meeting is not found."""
        if (failure := self._failure("patch")) is not None:
            return failure
        if meeting_id in self.deleted or meeting_id not in self.meetings:
            return _meeting_not_found(meeting_id)
        meeting = self.meetings[meeting_id]
        updated = replace(
            meeting,
            title=change.title if change.title is not None else meeting.title,
            start=change.start if change.start is not None else meeting.start,
            end=change.end if change.end is not None else meeting.end,
            attendees=change.attendees if change.attendees is not None else meeting.attendees,
        )
        self.meetings[meeting_id] = updated
        self.changes.append((meeting_id, change))
        return OperationResult.success(updated)

    async def delete(self, meeting_id: str) -> OperationResult[None]:
        """Delete the meeting; a repeated delete succeeds and an unknown meeting is not found."""
        if (failure := self._failure("delete")) is not None:
            return failure
        if meeting_id in self.deleted:
            return OperationResult.success()
        if meeting_id not in self.meetings:
            return _meeting_not_found(meeting_id)
        del self.meetings[meeting_id]
        self.deleted.add(meeting_id)
        self.deletions.append(meeting_id)
        return OperationResult.success()


class InMemoryCalendarAvailability(CalendarAvailability):
    """Answer free/busy from configured intervals with the Google Calendar availability's observable rules.

    ``busy`` maps an address to its busy intervals; an address in ``unknown`` answers
    ``busy=None``; any other address is free. ``fail_with`` makes every read return that
    error result. ``queries`` records each requested window and its addresses.
    """

    def __init__(
        self,
        *,
        busy: Mapping[str, Sequence[BusyInterval]] | None = None,
        unknown: Collection[str] = (),
        fail_with: OperationResult[Any] | None = None,
    ) -> None:
        self._busy = {email.casefold(): tuple(intervals) for email, intervals in (busy or {}).items()}
        self._unknown = {email.casefold() for email in unknown}
        self.fail_with = fail_with
        self.queries: list[tuple[tuple[str, ...], datetime, datetime]] = []

    async def busy_periods(
        self, emails: Sequence[str], start: datetime, end: datetime
    ) -> OperationResult[Mapping[str, AttendeeBusy]]:
        """Return one answer per case-folded address, the intervals clipped to the window."""
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("start and end must be timezone-aware")
        if end <= start:
            raise ValueError("end must be after start")
        keys = tuple(dict.fromkeys(email.strip().casefold() for email in emails if email.strip()))
        self.queries.append((keys, start, end))
        if self.fail_with is not None:
            return self.fail_with
        answers: dict[str, AttendeeBusy] = {}
        for key in keys:
            if key in self._unknown:
                answers[key] = AttendeeBusy(email=key, busy=None)
                continue
            clipped = tuple(
                BusyInterval(start=max(interval.start, start), end=min(interval.end, end))
                for interval in self._busy.get(key, ())
                if interval.start < end and interval.end > start
            )
            answers[key] = AttendeeBusy(email=key, busy=clipped)
        return OperationResult.success(answers)


class InMemoryIncidentListProjection:
    """Hold the incident list rows in memory, one per incident id, built as the Sheets adapter builds them.

    Both methods upsert on the incident id. A conversation of another chat system
    is refused as the adapter refuses it. ``fail_with`` makes every call return
    that error result instead.
    """

    def __init__(self, *, fail_with: OperationResult[None] | None = None) -> None:
        self._fail_with = fail_with
        self.rows: list[list[str]] = []

    async def append_row(self, incident: Incident) -> OperationResult[None]:
        """Write the incident's full row, in place when it has one, or return the configured failure."""
        return self._upsert(incident, status_only=False)

    async def update_status(self, incident: Incident, status: IncidentStatus) -> OperationResult[None]:
        """Set the status of the incident's row, or write its full row with ``status``, or return the configured failure."""
        return self._upsert(replace(incident, status=status), status_only=True)

    def _upsert(self, incident: Incident, *, status_only: bool) -> OperationResult[None]:
        if self._fail_with is not None:
            return self._fail_with
        conversation = incident.conversation
        if conversation is not None and conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        row = list_row(
            incident,
            channel_link=slack_conversation_link(conversation) if conversation is not None else None,
            channel_label=slack_conversation_label(incident) if conversation is not None else None,
        )
        index = next((i for i, existing in enumerate(self.rows) if existing[5] == incident.id), None)
        if index is None:
            self.rows.append(row)
        elif status_only:
            self.rows[index][3] = row[3]
        else:
            self.rows[index] = row
        return OperationResult.success(None)


class InMemoryLegacyRolesReader:
    """Hold legacy report roles by report vendor id; reads never write.

    ``seed`` gives a report its commander and lead as the legacy ``roles manage`` left them in Drive. A report
    with none seeded is NOT_FOUND, as a missing Drive file is; ``fail_with`` makes every read return that error
    result instead. ``reads`` lists the reports read, in order.

    TODO(TASK-145.13): delete with ``LegacyRolesReader``.
    """

    def __init__(self, *, fail_with: OperationResult[Any] | None = None) -> None:
        self._roles: dict[str, dict[IncidentRole, str]] = {}
        self._fail_with = fail_with
        self.reads: list[ReportReference] = []

    def seed(self, report: ReportReference, roles: Mapping[IncidentRole, str]) -> None:
        """Give ``report`` these roles."""
        self._roles[report.vendor_id] = dict(roles)

    async def read(self, report: ReportReference) -> OperationResult[Mapping[IncidentRole, str]]:
        """Return the seeded roles of a Google report; another system is unsupported, an unseeded report not found."""
        self.reads.append(report)
        if self._fail_with is not None:
            return OperationResult.error(self._fail_with.status, self._fail_with.message or "", self._fail_with.error_code)
        if report.system is not WorkplaceSystem.GOOGLE:
            return OperationResult.permanent_error(
                f"Google Drive cannot reach a report on {report.system.value}", ErrorCode.UNSUPPORTED_OPERATION
            )
        roles = self._roles.get(report.vendor_id)
        if roles is None:
            return OperationResult.error(OperationStatus.NOT_FOUND, "No such report")
        return OperationResult.success(dict(roles))


class InMemoryPlacementScheduleLookup:
    """Answer seeded schedules by placement folder id; any other placement has none. ``asked`` records each placement."""

    def __init__(self, schedules: Mapping[str, ScheduleReference] | None = None) -> None:
        self._schedules = dict(schedules or {})
        self.asked: list[ReportPlacement] = []

    async def schedule_for(self, placement: ReportPlacement) -> OperationResult[ScheduleReference | None]:
        """Return the seeded schedule of the placement's folder, or ``None``."""
        self.asked.append(placement)
        return OperationResult.success(self._schedules.get(placement.vendor_id))
