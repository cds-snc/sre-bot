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
``IncidentConversation`` writes to the incident's conversation
(``ConversationReference``); ``get_incident_conversation`` provides the Slack one,
and ``conversation_is_writable`` is the check every caller applies before a write.
``IncidentTranscriptReader`` reads what was said in a conversation.
``VideoCall`` creates the incident's video call (``VideoCallReference``);
``get_video_call`` provides the Google Meet one.
``resolve_new_incident_system`` resolves the new-incident policy against the
configured systems; the declare path's plugin calls it at startup.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from typing import Protocol, runtime_checkable

from contracts.configuration import SettingError
from contracts.operations.result import OperationResult
from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems, TenantVerifier, WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.common.vocabulary import StatusUpdateStage
from features.incident.core.adapters.google_docs import GoogleDocsIncidentReport
from features.incident.core.adapters.google_meet import GoogleMeetVideoCall
from features.incident.core.adapters.i18n import translate
from features.incident.core.adapters.slack import build_incident_conversation, build_incident_transcript_reader
from features.incident.core.domain import (
    CONVERSATION_NAME_ATTEMPTS,
    BindingKind,
    ConversationName,
    ConversationReference,
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    ExternalCaseReference,
    Incident,
    IncidentBinding,
    IncidentChanges,
    Keep,
    MessageReference,
    PostmortemMeetingReference,
    ReferenceKind,
    ReportPlacement,
    ReportReference,
    SectionDraft,
    SeverityChange,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateState,
    StatusUpdateText,
    TimelineEntry,
    TimelineEntryKind,
    TranscriptMessage,
    VideoCallReference,
    incident_conversation_names,
)
from features.incident.core.legacy_upgrade import LegacyUpgrade, UpgradeReport
from features.incident.core.store import (
    IncidentStore,
    RecordIncidentStore,
    RecordStatusUpdateStore,
    RecordTimelineStore,
    StatusUpdateStore,
    TimelineStore,
    bindings_table,
    incidents_table,
    status_updates_table,
    timeline_table,
)

__all__ = [
    "CONVERSATION_NAME_ATTEMPTS",
    "BindingKind",
    "ConversationName",
    "ConversationReference",
    "DocumentField",
    "DocumentSection",
    "DraftWriteResult",
    "ExternalCaseReference",
    "Incident",
    "IncidentBinding",
    "IncidentChanges",
    "IncidentConversation",
    "IncidentReport",
    "IncidentStore",
    "IncidentTranscriptReader",
    "Keep",
    "LegacyUpgrade",
    "MessageReference",
    "PostmortemMeetingReference",
    "ReferenceKind",
    "ReportPlacement",
    "ReportReference",
    "SectionDraft",
    "SeverityChange",
    "StatusUpdate",
    "StatusUpdateOrigin",
    "StatusUpdateStage",
    "StatusUpdateState",
    "StatusUpdateStore",
    "StatusUpdateText",
    "TimelineEntry",
    "TimelineEntryKind",
    "TimelineStore",
    "TranscriptMessage",
    "UpgradeReport",
    "VideoCall",
    "VideoCallReference",
    "build_incident_store",
    "build_legacy_upgrade",
    "build_status_update_store",
    "conversation_is_writable",
    "find_incident_for_conversation",
    "get_incident_conversation",
    "get_incident_report",
    "get_incident_transcript_reader",
    "get_video_call",
    "incident_conversation_names",
    "resolve_new_incident_system",
    "translate",
]


@runtime_checkable
class IncidentTranscriptReader(Protocol):
    """Interface reading what was said in an incident's conversation, named by its ``ConversationReference``.

    Name resolution, ordering, time conversion and filtering happen behind the
    interface. A reference of a system the implementation does not serve is a
    PERMANENT_ERROR with ``UNSUPPORTED_OPERATION``; platform failures are
    classified results, and an error the platform's table does not name raises.
    """

    def conversation_started_at(self, conversation: ConversationReference) -> OperationResult[datetime | None]:
        """Return when the conversation started, timezone-aware UTC.

        The data is ``None`` when the conversation carries no creation time; on a
        non-success the caller applies its own fallback window.
        """
        ...

    def read_transcript(
        self,
        conversation: ConversationReference,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> OperationResult[Sequence[TranscriptMessage]]:
        """Return the conversation's messages posted since ``since``, oldest first.

        Thread replies are included, interleaved by time, each message once.

        Args:
            conversation: The conversation to read.
            since: Timezone-aware start of the window.
            limit: Maximum number of messages in the transcript, replies
                included; the newest are kept.
            exclude_own_and_system_messages: Drop this bot's own posts and the
                platform's system events (joins, topic changes and the like).

        Returns:
            The messages in chronological order, or the classified failure of
            the first read; a failure after it keeps what was read.
        """
        ...


@runtime_checkable
class IncidentConversation(Protocol):
    """Interface writing to an incident's conversation, named by its ``ConversationReference``.

    Callers check ``conversation_is_writable`` before a write. Who the calls run
    as and how the vendor is reached stay behind the interface. A reference of a
    system the implementation does not serve is a PERMANENT_ERROR with
    ``UNSUPPORTED_OPERATION``; a conversation the bot cannot write to (archived,
    not a member, read-only) refuses writes with ``CONVERSATION_NOT_WRITABLE``;
    other platform failures are classified results, and an error the platform's
    table does not name raises. Writes are not replayed after a failure that
    may have been applied.

    ``create`` makes one attempt under the name it is given, rendered under the
    platform's own naming rules, and reports a taken name as an expected
    outcome; ``find_own`` finds the bot's own conversation of a name. Choosing
    the next name, and deciding that an existing
    conversation is the incident's own, belong to the caller
    (decisions/incident-management.md, one conversation per incident).
    """

    async def create(self, name: ConversationName, *, private: bool) -> OperationResult[ConversationReference]:
        """Create a conversation named after ``name``, the bot its first member, private when ``private``.

        A name already in use (by any conversation, archived ones included) is a
        PERMANENT_ERROR with ``CONVERSATION_NAME_TAKEN``, logged at info only: the
        caller tries its next name. Platform refusals to create are
        ``CONVERSATION_NOT_WRITABLE``; no configured tenant is
        ``CONFIG_NOT_CONFIGURED``. The call is never replayed.
        """
        ...

    async def find_own(self, name: ConversationName) -> OperationResult[ConversationReference | None]:
        """Return the bot's own open conversation named exactly as ``name`` renders, or ``None``.

        Run after a create that did not succeed, before trying another name: the
        platform may have created the conversation before the failure.
        """
        ...

    async def post(
        self, conversation: ConversationReference, text: str, *, blocks: Sequence[Mapping[str, object]] = ()
    ) -> OperationResult[MessageReference]:
        """Post ``text`` as the bot and return the posted message's reference.

        ``blocks`` lays the message out; ``text`` stays its notification fallback.
        """
        ...

    async def set_topic(self, conversation: ConversationReference, text: str) -> OperationResult[None]:
        """Set the conversation's topic to ``text``."""
        ...

    async def create_canvas(self, conversation: ConversationReference, markdown: str) -> OperationResult[None]:
        """Give the conversation its canvas, written from ``markdown``; a conversation that has one counts as done."""
        ...

    async def group_members(self, conversation: ConversationReference, group_id: str) -> OperationResult[tuple[str, ...]]:
        """Return the account ids in the user group ``group_id``, in the conversation's system and tenant.

        The ids are ready for ``invite``; an unknown group is NOT_FOUND.
        """
        ...

    async def set_purpose(self, conversation: ConversationReference, text: str) -> OperationResult[None]:
        """Set the conversation's purpose (its description) to ``text``."""
        ...

    async def add_bookmark(self, conversation: ConversationReference, title: str, link: str) -> OperationResult[None]:
        """Add a link titled ``title`` to the conversation's bookmarks."""
        ...

    async def invite(self, conversation: ConversationReference, account_ids: Sequence[str]) -> OperationResult[None]:
        """Invite chat accounts, ids in the conversation's system and tenant.

        Accounts already in the conversation count as invited; no accounts is a
        success without a call.
        """
        ...

    async def archive(self, conversation: ConversationReference) -> OperationResult[None]:
        """Archive the conversation; one already archived is a success."""
        ...

    async def is_writable(self, conversation: ConversationReference) -> OperationResult[bool]:
        """Say whether the bot can write to the conversation (not archived, a member), without changing it."""
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

    def list_placements(self) -> OperationResult[tuple[ReportPlacement, ...]]:
        """Return the places a new report can be filed in, sorted by label.

        For Google, the subfolders of [incident_core] ``folder_id`` other than the
        templates folder, read live. An empty ``folder_id`` is
        ``CONFIG_NOT_CONFIGURED``; a failed read is a classified result.
        """
        ...

    def create_from_template(self, title: str, placement: ReportPlacement | None = None) -> OperationResult[ReportReference]:
        """Create a new report titled ``title`` from the configured template, filed in ``placement``.

        No placement files it in the configured folder. Returns the new report's
        reference, link included. An empty [incident_core] ``folder_id`` or
        ``report_template_id``, or no tenant to name the reference with, is a
        PERMANENT_ERROR with ``CONFIG_NOT_CONFIGURED`` whose message names the key;
        a placement of another system is ``UNSUPPORTED_OPERATION``.
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
    services it resolved there. The table names come from the incident core
    settings (incidents, bindings and timeline); the tenants the legacy item bridge needs are copied from the
    configured-systems read, so a system not configured has no tenant. The
    new-incident policy is not read: only the declare path resolves it, so
    reading existing incidents never depends on it.
    """
    return RecordIncidentStore(
        records,
        incidents_table(settings.incidents_table),
        dict(systems.tenants()),
        bindings=bindings_table(settings.bindings_table),
        timeline=RecordTimelineStore(records, timeline_table(settings.timeline_table)),
    )


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
    services it resolved there. The incidents and bindings table names and the
    whole-table read cap come from the incident core settings; the tenants are copied from the
    configured-systems read, as for the read path's bridge, and the verifier
    confirms the Slack one before any write.
    """
    return LegacyUpgrade(
        records,
        incidents_table(settings.incidents_table),
        dict(systems.tenants()),
        verifier,
        settings.full_read_max_items,
        bindings=bindings_table(settings.bindings_table),
    )


@lru_cache(maxsize=1)
def get_incident_report() -> IncidentReport:
    """Return the process-wide Google-Docs-backed ``IncidentReport``."""
    return GoogleDocsIncidentReport()


@runtime_checkable
class VideoCall(Protocol):
    """Interface creating an incident's video call, named by the record's ``VideoCallReference``.

    Who the calls run as and how the vendor is reached stay behind the interface;
    no method takes a delegation subject or credentials. ``create`` is async: an
    implementation over a blocking SDK offloads inside its own methods, callers
    never do (decisions/outbound-clients.md). Platform failures are classified
    results, never exceptions.
    """

    async def create(self) -> OperationResult[VideoCallReference]:
        """Create a new video call and return its reference, link included.

        One attempt: the vendor offers no idempotency key, so a failed create is
        not retried behind the caller. No tenant to name the reference with is a
        PERMANENT_ERROR with ``CONFIG_NOT_CONFIGURED`` whose message names the key.
        """
        ...

    def link(self, call: VideoCallReference) -> str | None:
        """Return the stored link of the call; a reference of a system the implementation does not serve has none."""
        ...


@lru_cache(maxsize=1)
def get_video_call() -> VideoCall:
    """Return the process-wide Google-Meet-backed ``VideoCall``."""
    return GoogleMeetVideoCall()


@lru_cache(maxsize=1)
def get_incident_conversation() -> IncidentConversation:
    """Return the process-wide Slack-backed ``IncidentConversation``."""
    return build_incident_conversation()


@lru_cache(maxsize=1)
def get_incident_transcript_reader() -> IncidentTranscriptReader:
    """Return the process-wide Slack-backed ``IncidentTranscriptReader``."""
    return build_incident_transcript_reader()


NEW_INCIDENT_SYSTEM_SETTING = "incident_core.new_incident_system"


def resolve_new_incident_system(policy: WorkplaceSystem | None, systems: ConfiguredSystems) -> WorkplaceSystem:
    """Return the system that creates a new incident's report and video call (decisions/incident-management.md).

    A set policy resolves to that system when it is configured; an unset policy
    resolves to the only configured system. No implicit choice is made among
    several configured systems.

    Raises:
        SettingError: The named system is not configured, no system is configured,
            or the policy is unset while several are; it names the policy's setting.
    """
    configured = list(systems.tenants())
    if policy is not None:
        if policy in configured:
            return policy
        raise SettingError(NEW_INCIDENT_SYSTEM_SETTING, f"names {policy.value}, which is not configured")
    if len(configured) == 1:
        return configured[0]
    if not configured:
        raise SettingError(NEW_INCIDENT_SYSTEM_SETTING, "no workplace system is configured")
    names = ", ".join(sorted(system.value for system in configured))
    raise SettingError(NEW_INCIDENT_SYSTEM_SETTING, f"is unset while several systems are configured ({names}); name one")


async def find_incident_for_conversation(store: IncidentStore, conversation: ConversationReference) -> OperationResult[Incident]:
    """Resolve the command's conversation to its incident, or a classified refusal.

    The command check every incident command applies first. A conversation that
    belongs to no incident is NOT_FOUND with ``NOT_AN_INCIDENT``; one that maps
    to several is PERMANENT_ERROR with ``AMBIGUOUS_INCIDENT_CONVERSATION``; a
    store failure is a classified error result, never an exception.
    """
    return await store.find_by_conversation(conversation)


async def conversation_is_writable(
    conversations: IncidentConversation, conversation: ConversationReference | None
) -> OperationResult[bool]:
    """Say whether the bot can write to the incident's conversation; the check before every write.

    ``None`` (an incident without a conversation) is not writable and makes no
    call. A failed check is the classified result, for the caller to skip the
    write or report it.
    """
    if conversation is None:
        return OperationResult.success(False)
    return await conversations.is_writable(conversation)
