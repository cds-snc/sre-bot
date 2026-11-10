"""Domain types every incident subdomain works on."""

from dataclasses import dataclass, field, fields
from datetime import date, datetime
from enum import Enum, StrEnum
from typing import Any

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity, StatusUpdateStage


@dataclass(frozen=True)
class TranscriptMessage:
    """One message of an incident conversation, as a person would read it.

    Attributes:
        author: Display name of the person or bot that posted the message.
        text: Message text, stripped of surrounding whitespace.
        posted_at: When the message was posted, timezone-aware UTC. ``None``
            when the platform gave no usable time. Formatting it for display is
            the consumer's job.
        is_bot: Whether a bot or an integration posted the message rather than
            a person.
    """

    author: str
    text: str
    posted_at: datetime | None = None
    is_bot: bool = False


class StatusUpdateState(StrEnum):
    """Where a status update is in its draft, approve, publish life."""

    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"

    def can_move_to(self, target: StatusUpdateState) -> bool:
        """Return whether a store may change a record from this state to ``target``.

        Draft to approved, approved to published and, as a deliberate
        reversal, published back to approved (an update marked published by
        mistake can be marked not published). Nothing is published unapproved
        and nothing goes back to draft.
        """
        return (self, target) in _STATE_MOVES


_STATE_MOVES = frozenset(
    {
        (StatusUpdateState.DRAFT, StatusUpdateState.APPROVED),
        (StatusUpdateState.APPROVED, StatusUpdateState.PUBLISHED),
        (StatusUpdateState.PUBLISHED, StatusUpdateState.APPROVED),
    }
)


class StatusUpdateOrigin(StrEnum):
    """How a draft's text came to be; approval does not change it.

    HAND: a responder wrote or saved it. MODEL: one model call drafted it from
    the conversation. MODEL_INSTRUCTED: the model drafted it following a
    responder's instructions. CARRIED_FORWARD: nothing new was said, so the
    prior text was repeated with the no-new-information wording, by code.
    """

    HAND = "hand"
    MODEL = "model"
    MODEL_INSTRUCTED = "model_instructed"
    CARRIED_FORWARD = "carried_forward"


@dataclass(frozen=True)
class StatusUpdateText:
    """The language-specific fields of a status update, in one language.

    Attributes:
        affected_service: The affected service by its public name.
        impact: What users can observe.
        current_action: What the team is doing, without root-cause speculation.
        workaround: The workaround, or the wording that no action is needed.
    """

    affected_service: str
    impact: str
    current_action: str
    workaround: str


@dataclass(frozen=True)
class StatusUpdate:
    """One public status update of an incident, stored as its own record.

    Attributes:
        incident_id: The incident's id (the legacy incidents table UUID).
        sequence: Position among the incident's updates, from 1.
        state: Draft, approved or published.
        stage: Public stage the update announces.
        en: English fields.
        fr: French fields.
        next_update_at: When the next update is due.
        author: Platform user id of the responder who drafted it.
        transcript_cutoff: Time of the last conversation message the draft read.
        transcript_fingerprint: Opaque digest of the messages the draft read.
        created_at: When the draft was created.
        approver: Platform user id of the responder who approved it.
        approved_at: When it was approved.
        published_at: When it was marked published.
        published_by: Platform user id of the person who marked it published.
        origin: How the text came to be; ``None`` for records written before
            origins existed.

    Every time is timezone-aware.
    """

    incident_id: str
    sequence: int
    state: StatusUpdateState
    stage: StatusUpdateStage
    en: StatusUpdateText
    fr: StatusUpdateText
    next_update_at: datetime
    author: str
    transcript_cutoff: datetime
    transcript_fingerprint: str
    created_at: datetime
    approver: str | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    published_by: str | None = None
    origin: StatusUpdateOrigin | None = None

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise ValueError("incident_id must name an incident")
        if self.sequence < 1:
            raise ValueError(f"sequence must be 1 or more, got {self.sequence}")
        _require_aware(self, "next_update_at", "transcript_cutoff", "created_at", "approved_at", "published_at")


def _require_text(record: object, *names: str) -> None:
    for name in names:
        if not getattr(record, name).strip():
            raise ValueError(f"{name} must not be blank")


def _require_aware(record: object, *names: str) -> None:
    for name in names:
        value: datetime | None = getattr(record, name)
        if value is not None and value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")


def _require_system(system: object) -> None:
    if not isinstance(system, WorkplaceSystem):
        raise ValueError(f"system must be a WorkplaceSystem member, got {system!r}")


@dataclass(frozen=True)
class ResourceReference:
    """A workplace artifact an incident points at, never a bare vendor id.

    Attributes:
        system: The workplace system that holds the artifact.
        tenant: The vendor's own tenant id (Slack team id, Google customer id).
        vendor_id: The artifact's id in that system.
        url: The vendor link to the artifact, when one exists.
    """

    system: WorkplaceSystem
    tenant: str
    vendor_id: str
    url: str | None = None

    def __post_init__(self) -> None:
        _require_system(self.system)
        _require_text(self, "tenant", "vendor_id")


@dataclass(frozen=True)
class ConversationReference(ResourceReference):
    """The incident's conversation (a Slack channel)."""


@dataclass(frozen=True)
class ReportReference(ResourceReference):
    """The incident report document."""


@dataclass(frozen=True)
class ReportPlacement(ResourceReference):
    """A labelled folder a new incident report can be filed in (a Drive folder for Google).

    Read live from the report system, never stored on the record: the record
    keeps only the created report's ``ReportReference``.

    Attributes:
        label: The folder's name as people choose it.
    """

    label: str = field(kw_only=True)

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text(self, "label")


@dataclass(frozen=True)
class VideoCallReference(ResourceReference):
    """The incident video call."""


@dataclass(frozen=True)
class PostmortemMeetingReference(ResourceReference):
    """The postmortem (retrospective) meeting."""


@dataclass(frozen=True)
class ExternalCaseReference(ResourceReference):
    """The case opened for the incident in an external case system."""


@dataclass(frozen=True)
class MessageReference:
    """A message in a conversation: the alert an incident was declared from, or a captured timeline message.

    Attributes:
        system: The workplace system that holds the message.
        tenant: The vendor's own tenant id.
        conversation_id: The conversation the message was posted in.
        message_id: The message's id in that conversation (a Slack ``ts``).
        url: The vendor link to the message, a hint only.
    """

    system: WorkplaceSystem
    tenant: str
    conversation_id: str
    message_id: str
    url: str | None = None

    def __post_init__(self) -> None:
        _require_system(self.system)
        _require_text(self, "tenant", "conversation_id", "message_id")


@dataclass(frozen=True)
class Incident:
    """The incident record: what was declared, its timings, roles and resources.

    Attributes:
        id: The incident's id (the legacy incidents table UUID).
        title: Short name of the incident.
        status: Internal lifecycle status.
        declared_by: Platform user id of the person who declared it.
        declared_at: When it was declared.
        security_incident: Whether it was declared as a security incident;
            always answered, never a third state.
        product: The affected product, ``None`` while not recorded.
        severity: Severity level; ``None`` while not rated.
        detected_at: When the problem was detected.
        impact_started_at: When user impact started.
        impact_ended_at: When user impact ended.
        incident_commander: Platform user id holding the role, or ``None``.
        operations_lead: Platform user id holding the role, or ``None``.
        communications_lead: Platform user id holding the role, or ``None``.
        policy_lead: Platform user id holding the role, or ``None``.
        postmortem_owner: Platform user id holding the role, or ``None``.
        conversation: The incident conversation.
        report: The incident report document.
        video_call: The incident video call.
        postmortem_meeting: The postmortem meeting.
        external_case: The external case.
        source_alert: The alert message it was declared from.

    Role fields are named by ``IncidentRole`` values. Every time is
    timezone-aware.
    """

    id: str
    title: str
    status: IncidentStatus
    declared_by: str
    declared_at: datetime
    security_incident: bool
    product: str | None = None
    severity: Severity | None = None
    detected_at: datetime | None = None
    impact_started_at: datetime | None = None
    impact_ended_at: datetime | None = None
    incident_commander: str | None = None
    operations_lead: str | None = None
    communications_lead: str | None = None
    policy_lead: str | None = None
    postmortem_owner: str | None = None
    conversation: ConversationReference | None = None
    report: ReportReference | None = None
    video_call: VideoCallReference | None = None
    postmortem_meeting: PostmortemMeetingReference | None = None
    external_case: ExternalCaseReference | None = None
    source_alert: MessageReference | None = None

    def __post_init__(self) -> None:
        _require_text(self, "id", "title")
        if not isinstance(self.status, IncidentStatus):
            raise ValueError(f"status must be an IncidentStatus member, got {self.status!r}")
        if self.severity is not None and not isinstance(self.severity, Severity):
            raise ValueError(f"severity must be a Severity member or None, got {self.severity!r}")
        if not isinstance(self.security_incident, bool):
            raise ValueError(f"security_incident must be a bool, got {self.security_incident!r}")
        _require_aware(self, *(field.name for field in fields(self) if field.name.endswith("_at")))


class ReferenceKind(StrEnum):
    """A resource reference ``set_reference`` replaces after declare; the value is the record field and stored attribute.

    The conversation and the source alert are set only when the incident is
    created: a recreated channel never moves the record's conversation.
    """

    REPORT = "report"
    VIDEO_CALL = "video_call"
    POSTMORTEM_MEETING = "postmortem_meeting"
    EXTERNAL_CASE = "external_case"


class BindingKind(StrEnum):
    """The kind of place an incident is bound to; the stored form is the value."""

    CHAT_CONVERSATION = "chat_conversation"


@dataclass(frozen=True)
class IncidentBinding:
    """One place responders work an incident, a child record of the incident.

    Stored under (``incident_id``, binding key) and never deleted: a replaced
    place gets ``archived_at``. Visibility is the incident's.

    Attributes:
        incident_id: The incident this place belongs to.
        kind: The kind of place.
        system: The workplace system that holds the place.
        tenant: The vendor's own tenant id.
        vendor_id: The place's id in that system (a conversation id for a chat kind).
        primary: Whether this is the incident's primary place.
        bound_by: Who bound it.
        bound_at: When it was bound, timezone-aware.
        url: A link to the place, a hint only.
        archived_at: When the place was replaced, timezone-aware; ``None`` while active.
    """

    incident_id: str
    kind: BindingKind
    system: WorkplaceSystem
    tenant: str
    vendor_id: str
    primary: bool
    bound_by: str
    bound_at: datetime
    url: str | None = None
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BindingKind):
            raise ValueError(f"kind must be a BindingKind member, got {self.kind!r}")
        _require_system(self.system)
        _require_text(self, "incident_id", "tenant", "vendor_id", "bound_by")
        for name in ("tenant", "vendor_id"):
            if "#" in getattr(self, name):
                raise ValueError(f"{name} must not contain '#', which separates the parts of the binding key")
        _require_aware(self, "bound_at", "archived_at")


class TimelineEntryKind(StrEnum):
    """What a timeline entry records; the stored form is the value.

    MESSAGE: text a person wrote or captured. SEVERITY_CHANGED: a system entry
    holding a ``SeverityChange``, rendered per locale when read. A reader meeting
    a kind it does not know renders a labelled fallback; no command acts on entries.
    """

    MESSAGE = "message"
    SEVERITY_CHANGED = "severity_changed"


@dataclass(frozen=True)
class SeverityChange:
    """A change of an incident's severity; ``None`` is unrated.

    Attributes:
        previous: The severity before the change.
        current: The severity after it; never equal to ``previous``.
    """

    previous: Severity | None
    current: Severity | None

    def __post_init__(self) -> None:
        for name in ("previous", "current"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Severity):
                raise ValueError(f"{name} must be a Severity member or None, got {value!r}")
        if self.previous == self.current:
            raise ValueError("a severity change must differ from the previous severity")


@dataclass(frozen=True)
class TimelineEntry:
    """One entry of an incident's timeline, stored as its own record.

    Attributes:
        incident_id: The incident's id.
        entry_id: The entry's id, unique within the incident.
        posted_at: When the entry was posted, timezone-aware.
        author: Platform user id or display name of who wrote it.
        text: The entry text; required for a message, empty for a system kind.
        source_message: The captured message, ``None`` for a manual entry.
        kind: What the entry records.
        severity_change: The change a ``SEVERITY_CHANGED`` entry records; ``None`` for any other kind.
    """

    incident_id: str
    entry_id: str
    posted_at: datetime
    author: str
    text: str
    source_message: MessageReference | None = None
    kind: TimelineEntryKind = TimelineEntryKind.MESSAGE
    severity_change: SeverityChange | None = None

    def __post_init__(self) -> None:
        _require_text(self, "incident_id", "entry_id")
        _require_aware(self, "posted_at")
        if not isinstance(self.kind, TimelineEntryKind):
            raise ValueError(f"kind must be a TimelineEntryKind member, got {self.kind!r}")
        if self.kind is TimelineEntryKind.MESSAGE:
            _require_text(self, "text")
            if self.severity_change is not None:
                raise ValueError("severity_change belongs to a severity_changed entry only")
            return
        if self.text:
            raise ValueError("text must be empty for a system entry: it is rendered at read time")
        if (self.kind is TimelineEntryKind.SEVERITY_CHANGED) != (self.severity_change is not None):
            raise ValueError("severity_change is required on a severity_changed entry")


class Keep(Enum):
    """The typed "leave as stored" value of an ``IncidentChanges`` field."""

    KEEP = "keep"


@dataclass(frozen=True)
class IncidentChanges:
    """The record fields a field update writes; every field left at ``Keep.KEEP`` stays as stored.

    ``None`` clears an optional field. The title and the security flag cannot
    be cleared. Times are timezone-aware.
    """

    title: str | Keep = Keep.KEEP
    severity: Severity | None | Keep = Keep.KEEP
    detected_at: datetime | None | Keep = Keep.KEEP
    impact_started_at: datetime | None | Keep = Keep.KEEP
    impact_ended_at: datetime | None | Keep = Keep.KEEP
    security_incident: bool | Keep = Keep.KEEP

    def __post_init__(self) -> None:
        named = self.named()
        if not named:
            raise ValueError("a field update names at least one field")
        if "title" in named:
            _require_text(self, "title")
        if "severity" in named and named["severity"] is not None and not isinstance(named["severity"], Severity):
            raise ValueError(f"severity must be a Severity member or None, got {named['severity']!r}")
        if "security_incident" in named and not isinstance(named["security_incident"], bool):
            raise ValueError(f"security_incident must be a bool, got {named['security_incident']!r}")
        _require_aware(self, *(name for name in named if name.endswith("_at")))

    def named(self) -> dict[str, Any]:
        """Return the fields this update writes, by record field name."""
        return {field.name: value for field in fields(self) if (value := getattr(self, field.name)) is not Keep.KEEP}


@dataclass(frozen=True)
class DocumentSection:
    """A section of the incident document template.

    In the incident template each heading is followed by guidance describing
    what belongs in that section. That guidance is the section's drafting
    instruction: the AI answers it from the incident channel transcript, and
    the answer replaces the guidance in the drafted document.
    """

    heading: str
    instructions: str

    @property
    def has_instructions(self) -> bool:
        """Whether any guidance text is written under this heading."""
        return bool(self.instructions.strip())


@dataclass(frozen=True)
class SectionDraft:
    """A section of the drafted document: a heading and the text beneath it.

    ``content`` is the AI-written answer when ``is_drafted`` is true; otherwise
    it carries the source document's original guidance forward so a human
    still sees what that section is asking for.

    ``as_list`` marks sections that read as lists rather than prose -- action
    items, follow-ups, timelines -- so the renderer bullets every line even
    when the model returned them unmarked.
    """

    heading: str
    content: str
    is_drafted: bool
    as_list: bool = False


@dataclass(frozen=True)
class DocumentField:
    """A ``Label: value`` line in the report's metadata block.

    These sit above the first heading, so they are addressed by label rather
    than by section.
    """

    label: str
    value: str


@dataclass(frozen=True)
class DraftWriteResult:
    """Where a drafting run's output landed.

    ``created`` distinguishes the first run for an incident (a new draft
    document) from a re-run (the same document rewritten in place), so the
    caller can say which happened.
    """

    document_id: str
    created: bool


CONVERSATION_NAME_ATTEMPTS = 5
"""How many names declare and recreate try for one incident's conversation: the first, then attempts 2 to 5."""


@dataclass(frozen=True)
class ConversationName:
    """The name an incident's conversation is created under, before a chat platform renders it.

    The incident's naming policy, platform-neutral: ``incident-`` (``incident-dev-``
    outside production), the opening date, the title, and from the second attempt a
    ``-<attempt>`` suffix. Each conversation adapter renders it under its own
    platform's rules (length, allowed characters, case) in ``core/adapters/``.

    Attributes:
        title: The incident title, as declared.
        opened_on: The day the incident opened.
        production: Whether this instance is production.
        attempt: Which candidate this is, 1 to ``CONVERSATION_NAME_ATTEMPTS``.
    """

    title: str
    opened_on: date
    production: bool
    attempt: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.attempt <= CONVERSATION_NAME_ATTEMPTS:
            raise ValueError(f"attempt must be 1 to {CONVERSATION_NAME_ATTEMPTS}, got {self.attempt}")

    @property
    def prefix(self) -> str:
        """``incident-`` in production, ``incident-dev-`` elsewhere, followed by the opening date."""
        return f"{'incident-' if self.production else 'incident-dev-'}{self.opened_on.isoformat()}"

    @property
    def suffix(self) -> str:
        """Empty for the first attempt, ``-<attempt>`` after it."""
        return "" if self.attempt == 1 else f"-{self.attempt}"


def incident_conversation_names(title: str, opened_on: date, *, production: bool) -> tuple[ConversationName, ...]:
    """Return the names to try, in order, for an incident's conversation.

    Which one an incident ends up with, and when an existing conversation is its
    own, is the caller's decision (decisions/incident-management.md, one
    conversation per incident).
    """
    return tuple(
        ConversationName(title=title, opened_on=opened_on, production=production, attempt=attempt)
        for attempt in range(1, CONVERSATION_NAME_ATTEMPTS + 1)
    )
