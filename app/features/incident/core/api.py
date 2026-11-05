"""Public surface of the incident core package.

Subdomains of the incident feature import this module and nothing else from
``core``: the interfaces every subdomain works on, their domain types, the
functions that build or provide their implementations, and
``find_incident_for_conversation``, the command check every incident command
applies first. ``IncidentStore`` reads the incident record and
``StatusUpdateStore`` keeps each public status update as its own record under
the incident id; entry points build both per service scope with
``build_incident_store`` and ``build_status_update_store`` and pass them, with
the conversation reference they build, to the subdomain services.
``build_legacy_upgrade`` builds the incident legacy upgrade (``LegacyUpgrade``,
reporting an ``UpgradeReport``) from the services its job resolves per run.
``IncidentReport`` works on the incident report the record references
(``ReportReference``); ``get_incident_report`` provides the Google Docs one.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from typing import Protocol, runtime_checkable

from contracts.operations.result import OperationResult
from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems, TenantVerifier
from features.incident.common.settings import IncidentCoreSettings
from features.incident.common.vocabulary import StatusUpdateStage
from features.incident.core.adapters.google_docs import GoogleDocsIncidentReport
from features.incident.core.adapters.i18n import translate
from features.incident.core.adapters.slack import build_incident_transcript_reader
from features.incident.core.domain import (
    ConversationReference,
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    ExternalCaseReference,
    Incident,
    MessageReference,
    PostmortemMeetingReference,
    ReportReference,
    SectionDraft,
    SourceAlertReference,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateState,
    StatusUpdateText,
    TimelineEntry,
    TranscriptMessage,
    VideoCallReference,
)
from features.incident.core.legacy_upgrade import LegacyUpgrade, UpgradeReport
from features.incident.core.store import (
    IncidentStore,
    RecordIncidentStore,
    RecordStatusUpdateStore,
    StatusUpdateStore,
    incidents_table,
    status_updates_table,
)

__all__ = [
    "ConversationReference",
    "DocumentField",
    "DocumentSection",
    "DraftWriteResult",
    "ExternalCaseReference",
    "Incident",
    "IncidentReport",
    "IncidentStore",
    "IncidentTranscriptReader",
    "LegacyUpgrade",
    "MessageReference",
    "PostmortemMeetingReference",
    "ReportReference",
    "SectionDraft",
    "SourceAlertReference",
    "StatusUpdate",
    "StatusUpdateOrigin",
    "StatusUpdateStage",
    "StatusUpdateState",
    "StatusUpdateStore",
    "StatusUpdateText",
    "TimelineEntry",
    "TranscriptMessage",
    "UpgradeReport",
    "VideoCallReference",
    "build_incident_store",
    "build_legacy_upgrade",
    "build_status_update_store",
    "find_incident_for_conversation",
    "get_incident_report",
    "get_incident_transcript_reader",
    "translate",
]


@runtime_checkable
class IncidentTranscriptReader(Protocol):
    """Interface reading what was said in an incident's conversation.

    Name resolution, ordering, time conversion and filtering happen behind the
    interface. Implementations never raise for a platform failure: they log it
    and return the documented empty value.
    """

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        """Return when the conversation started, timezone-aware UTC.

        Returns ``None`` when the platform cannot say (the lookup failed or the
        conversation carries no creation time); the caller applies its own
        fallback window.
        """
        ...

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        """Return the conversation's messages posted since ``since``, oldest first.

        Thread replies are included, interleaved by time, each message once.

        Args:
            conversation_id: The conversation to read.
            since: Timezone-aware start of the window.
            limit: Maximum number of messages in the transcript, replies
                included; the newest are kept.
            exclude_own_and_system_messages: Drop this bot's own posts and the
                platform's system events (joins, topic changes and the like).

        Returns:
            The messages in chronological order; empty on a platform failure.
        """
        ...


@runtime_checkable
class IncidentReport(Protocol):
    """Interface working on an incident's report document, named by the record's ``ReportReference``.

    Who the calls run as and how the vendor is reached stay behind the interface;
    no method takes a delegation subject or credentials. A reference of a system
    the implementation does not serve is a PERMANENT_ERROR with
    ``UNSUPPORTED_OPERATION``. Platform failures are classified results, never
    exceptions.
    """

    def create_from_template(self, title: str) -> OperationResult[ReportReference]:
        """Create a new report titled ``title`` from the configured template, filed in the configured folder.

        Returns the new report's reference, link included. An empty
        [incident_core] ``folder_id`` or ``report_template_id``, or no tenant to
        name the reference with, is a PERMANENT_ERROR with ``CONFIG_NOT_CONFIGURED``
        whose message names the key.
        """
        ...

    def replace_placeholders(self, report: ReportReference, values: Mapping[str, str]) -> OperationResult[None]:
        """Replace every occurrence of each key in the report with its value (case-sensitive).

        Success whether or not a key occurred; a report that cannot be found is NOT_FOUND.
        """
        ...

    def read_sections(self, report: ReportReference) -> OperationResult[Sequence[DocumentSection]]:
        """Return the report's heading-delimited sections in document order; the report is only read."""
        ...

    def write_draft_copy(
        self,
        report: ReportReference,
        drafts: Sequence[SectionDraft],
        fields: Sequence[DocumentField],
        links: Mapping[str, str],
    ) -> OperationResult[DraftWriteResult]:
        """Write a new copy of the report filled in with the drafted sections, fields and pull-request links.

        Each call creates a new copy beside the report; the report itself is never
        written to. Nothing to write (no drafts and no fields) is a failure.
        """
        ...

    def link(self, report: ReportReference) -> str | None:
        """Return the report's stored link, unformatted; ``None`` when the reference holds none."""
        ...


def build_incident_store(records: RecordStore, systems: ConfiguredSystems, settings: IncidentCoreSettings) -> IncidentStore:
    """Return the ``IncidentStore`` over the resolved ``RecordStore``.

    A plain function, called by an entry point inside its service scope with the
    services it resolved there. The table name comes from the incident core
    settings; the tenants the legacy item bridge needs are copied from the
    configured-systems read, so a system not configured has no tenant. The
    new-incident policy is not read: only the declare path resolves it, so
    reading existing incidents never depends on it.
    """
    return RecordIncidentStore(records, incidents_table(settings.incidents_table), dict(systems.tenants()))


def build_status_update_store(records: RecordStore, settings: IncidentCoreSettings) -> StatusUpdateStore:
    """Return the ``StatusUpdateStore`` over the resolved ``RecordStore``.

    A plain function, called by an entry point inside its service scope with the
    records contract it resolved there. The table name comes from the incident
    core settings.
    """
    return RecordStatusUpdateStore(records, status_updates_table(settings.status_updates_table))


def build_legacy_upgrade(
    records: RecordStore, systems: ConfiguredSystems, verifier: TenantVerifier, settings: IncidentCoreSettings
) -> LegacyUpgrade:
    """Return the incident legacy upgrade over the resolved ``RecordStore``.

    A plain function, called by the upgrade job inside its service scope with the
    services it resolved there. The table name and the whole-table read cap come
    from the incident core settings; the tenants are copied from the
    configured-systems read, as for the read path's bridge, and the verifier
    confirms the Slack one before any write.
    """
    return LegacyUpgrade(
        records,
        incidents_table(settings.incidents_table),
        dict(systems.tenants()),
        verifier,
        settings.full_read_max_items,
    )


@lru_cache(maxsize=1)
def get_incident_report() -> IncidentReport:
    """Return the process-wide Google-Docs-backed ``IncidentReport``."""
    return GoogleDocsIncidentReport()


@lru_cache(maxsize=1)
def get_incident_transcript_reader() -> IncidentTranscriptReader:
    """Return the process-wide Slack-backed ``IncidentTranscriptReader``."""
    return build_incident_transcript_reader()


def find_incident_for_conversation(store: IncidentStore, conversation: ConversationReference) -> OperationResult[Incident]:
    """Resolve the command's conversation to its incident, or a classified refusal.

    The command check every incident command applies first. A conversation that
    belongs to no incident is NOT_FOUND with ``NOT_AN_INCIDENT``; one that maps
    to several is PERMANENT_ERROR with ``AMBIGUOUS_INCIDENT_CONVERSATION``; a
    store failure is a classified error result, never an exception.
    """
    return store.find_by_conversation(conversation)
