"""Domain types every incident subdomain works on."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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


class IncidentSecurityFlag(StrEnum):
    """Whether an incident was declared as a security incident.

    UNKNOWN means the answer was never stored (older incidents, the recreate
    path or an unexpected value); callers treat it as unconfirmed, not as NO.
    """

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class StatusUpdateStage(StrEnum):
    """Public stage of an incident, declared in its only (forward) order.

    A public vocabulary, distinct from the incident's internal lifecycle
    status. The values are the stored strings; labels belong to the comms
    profile that renders them.
    """

    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


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

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise ValueError("incident_id must name an incident")
        if self.sequence < 1:
            raise ValueError(f"sequence must be 1 or more, got {self.sequence}")
        for name in ("next_update_at", "transcript_cutoff", "created_at", "approved_at", "published_at"):
            value: datetime | None = getattr(self, name)
            if value is not None and value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
