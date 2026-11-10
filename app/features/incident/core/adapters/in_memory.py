"""In-memory incident core stores and report with the real implementations' observable rules.

For tests and local runs. ``InMemoryStatusUpdateStore``: appends only where
nothing is stored, state changes only from the expected state, a repeat of a
write that landed is a conflict, newest first. ``InMemoryIncidentStore``: the incident reads
with the same classifications as ``RecordIncidentStore``. ``InMemoryIncidentReport``:
the ``GoogleDocsIncidentReport`` rules (Google references only, unknown reports not
found, empty document ids refused naming the key, no draft copy without content).
``InMemoryIncidentConversation``: the ``SlackIncidentConversation`` rules (Slack
references only, unknown conversations not found, archived or non-member
conversations not writable and refusing writes, repeated archives and empty
invites succeeding).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.slack import slack_channel_name
from features.incident.core.domain import (
    BindingKind,
    ConversationName,
    ConversationReference,
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    Incident,
    IncidentBinding,
    MessageReference,
    ReferenceKind,
    ReportPlacement,
    ReportReference,
    ResourceReference,
    SectionDraft,
    StatusUpdate,
    StatusUpdateState,
)
from features.incident.core.store import (
    IncidentStore,
    StatusUpdateStore,
    ambiguous_conversation,
    no_such_incident,
    not_an_incident,
    record_conflict,
    select_active_bindings,
    validate_attachment,
    validate_new_incident,
    validate_reference,
)


class InMemoryStatusUpdateStore(StatusUpdateStore):
    """Hold status updates in a dict keyed by incident id and sequence."""

    def __init__(self) -> None:
        self._updates: dict[tuple[str, int], StatusUpdate] = {}

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence; any record already there is a conflict."""
        if (update.incident_id, update.sequence) in self._updates:
            return _conflict()
        self._updates[(update.incident_id, update.sequence)] = update
        return OperationResult.success(data=update)

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
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

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update, or success with ``None`` when it has none."""
        updates = self._newest_first(incident_id)
        return OperationResult.success(data=updates[0] if updates else None)

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
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
    ``create``, ``attach_conversation`` and ``set_reference`` share the real store's
    validation; the fake holds no record version, so only a different conversation conflicts.
    """

    def __init__(self) -> None:
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

    def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the seeded incident with this id."""
        incident = self._incidents.get(incident_id)
        return OperationResult.success(data=incident) if incident is not None else no_such_incident()

    def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
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

    def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return the incidents seeded open, oldest declaration first."""
        incidents = (self._incidents[incident_id] for incident_id in self._open)
        return OperationResult.success(data=sorted(incidents, key=lambda incident: incident.declared_at))

    def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return the seeded incident's security flag."""
        incident = self._incidents.get(incident_id)
        return OperationResult.success(data=incident.security_incident) if incident is not None else no_such_incident()

    def create(self, incident: Incident) -> OperationResult[Incident]:
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

    def attach_conversation(self, incident_id: str, binding: IncidentBinding) -> OperationResult[Incident]:
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

    def set_reference(self, incident_id: str, kind: ReferenceKind, reference: ResourceReference) -> OperationResult[Incident]:
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


@dataclass
class _StoredReport:
    title: str
    folder_id: str
    sections: list[DocumentSection] = field(default_factory=list)
    placeholders: dict[str, str] = field(default_factory=dict)


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

    def placeholders_of(self, report: ReportReference) -> Mapping[str, str]:
        """Return the placeholder values applied to ``report`` so far."""
        return dict(self._reports[report.vendor_id].placeholders)

    def list_placements(self) -> OperationResult[tuple[ReportPlacement, ...]]:
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

    def create_from_template(self, title: str, placement: ReportPlacement | None = None) -> OperationResult[ReportReference]:
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

    def replace_placeholders(self, report: ReportReference, values: Mapping[str, str]) -> OperationResult[None]:
        """Record the values on a known report."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _no_such_report()
        stored.placeholders.update(values)
        return OperationResult.success()

    def read_sections(self, report: ReportReference) -> OperationResult[Sequence[DocumentSection]]:
        """Return a known report's sections in order."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _report_unsupported(report)
        stored = self._reports.get(report.vendor_id)
        if stored is None:
            return _no_such_report()
        self.read_from.append(report)
        return OperationResult.success(data=tuple(stored.sections))

    def write_draft_copy(
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

    def link(self, report: ReportReference) -> str | None:
        """Return the stored link of the report."""
        return report.url


def _report_unsupported[T](report: ReportReference) -> OperationResult[T]:
    return OperationResult.permanent_error(
        f"Google Docs cannot reach a report on {report.system.value}", ErrorCode.UNSUPPORTED_OPERATION
    )


def _no_such_report[T]() -> OperationResult[T]:
    return OperationResult.error(OperationStatus.NOT_FOUND, message="No such report")


def _report_not_configured[T](key: str) -> OperationResult[T]:
    return OperationResult.permanent_error(f"{key} is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)


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
    non-member conversations; any other id is not found. Posts get ``ts`` values
    ``1700000000.00000<n>`` in order. ``checked`` lists the conversations whose
    writability was asked.

    ``names`` names some of those conversations (Slack channel name to id) and
    ``foreign_names`` are names the bot cannot see; creating under any of them is
    ``CONVERSATION_NAME_TAKEN``. A ``ConversationName`` is rendered with the Slack
    adapter's ``slack_channel_name``, the platform this fake stands in for. A created conversation is open, the bot a member,
    with id ``C0NEW<n>``. ``find_own`` finds named conversations that are open and
    where the bot is a member. ``groups`` maps a user group id to its members.
    """

    def __init__(
        self,
        *,
        tenant: str = "T0SLACK",
        open_ids: Sequence[str] = (),
        archived_ids: Sequence[str] = (),
        non_member_ids: Sequence[str] = (),
        names: Mapping[str, str] | None = None,
        foreign_names: Sequence[str] = (),
        groups: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._tenant = tenant
        self._conversations: dict[str, _StoredConversation] = {}
        for vendor_id in open_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=False, member=True)
        for vendor_id in archived_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=True, member=True)
        for vendor_id in non_member_ids:
            self._conversations[vendor_id] = _StoredConversation(archived=False, member=False)
        self._posted = 0
        self._created = 0
        self._names = dict(names or {})
        self._foreign_names = frozenset(foreign_names)
        self._groups = {group_id: tuple(members) for group_id, members in (groups or {}).items()}
        self.checked: list[ConversationReference] = []

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
        self, conversation: ConversationReference, text: str, *, blocks: Sequence[Mapping[str, object]] = ()
    ) -> OperationResult[MessageReference]:
        """Record ``text`` and its blocks and return its reference; refused where the bot cannot write."""
        stored = self._writable(conversation)
        if isinstance(stored, OperationResult):
            return stored
        self._posted += 1
        stored.posts.append(text)
        stored.blocks.append(tuple(blocks))
        return OperationResult.success(
            MessageReference(
                system=WorkplaceSystem.SLACK,
                tenant=conversation.tenant,
                conversation_id=conversation.vendor_id,
                message_id=f"1700000000.{self._posted:06d}",
            )
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
