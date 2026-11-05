"""In-memory incident core stores and report with the real implementations' observable rules.

For tests and local runs. ``InMemoryStatusUpdateStore``: appends only where
nothing is stored, state changes only from the expected state, a repeat of a
write that landed is a conflict, newest first. ``InMemoryIncidentStore``: the incident reads
with the same classifications as ``RecordIncidentStore``. ``InMemoryIncidentReport``:
the ``GoogleDocsIncidentReport`` rules (Google references only, unknown reports not
found, empty document ids refused naming the key, no draft copy without content).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.domain import (
    ConversationReference,
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    Incident,
    ReportReference,
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
    """

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._open: set[str] = set()

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
        """Return the one seeded incident with the same conversation system, tenant and id."""
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
    """

    def __init__(
        self,
        *,
        tenant: str = "C0GOOGLE",
        folder_id: str = "F0INCIDENTS",
        report_template_id: str = "T0TEMPLATE",
        next_ids: Sequence[str] = (),
    ) -> None:
        self._tenant = tenant
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

    def create_from_template(self, title: str) -> OperationResult[ReportReference]:
        """Create a known report filed in the configured folder; an empty document id refuses naming its key."""
        if not self._folder_id:
            return _report_not_configured("incident_core.folder_id")
        if not self._report_template_id:
            return _report_not_configured("incident_core.report_template_id")
        document_id = self._next_ids.pop(0) if self._next_ids else f"report-{len(self._reports) + 1}"
        self._reports[document_id] = _StoredReport(title=title, folder_id=self._folder_id)
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
