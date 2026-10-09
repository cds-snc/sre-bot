"""Domain values for the incident comms use case: public status updates.

Frozen, platform-neutral dataclasses shared by the services, the publisher and
the platform adapters. This module depends only on the stdlib and the incident
core's public types.
"""

from dataclasses import dataclass
from enum import StrEnum

from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateText

_TEXT_FIELDS = ("affected_service", "impact", "current_action", "workaround")


class StatusUpdateOutcomeKind(StrEnum):
    """How a status-update run produced the draft it returns."""

    DRAFTED = "drafted"
    CARRIED_FORWARD = "carried_forward"
    PENDING = "pending"
    MANUAL = "manual"


@dataclass(frozen=True)
class StatusUpdateDraftOutcome:
    """The draft a status-update run returns, and how it came to be.

    Attributes:
        update: The draft record, as stored.
        kind: ``DRAFTED`` from new activity by one model call,
            ``CARRIED_FORWARD`` from the prior update with nothing new,
            ``PENDING`` when an existing draft already covers everything, or
            ``MANUAL`` for the responder to write, prefilled from the latest
            approved update, when they chose to or the model call failed.
    """

    update: StatusUpdate
    kind: StatusUpdateOutcomeKind


@dataclass(frozen=True)
class DraftedFields:
    """The stage and the language-specific fields the model filled."""

    stage: StatusUpdateStage
    en: StatusUpdateText
    fr: StatusUpdateText


@dataclass(frozen=True)
class NoNewInformationWording:
    """The current-action wording of a carried-forward update, per language.

    Supplied by the platform layer from the catalogues, so the service stays
    free of translation lookups.
    """

    en: str
    fr: str


@dataclass(frozen=True)
class StatusUpdateEdit:
    """The stage and both languages' fields a responder submits, saves or hands to the model as its base."""

    stage: StatusUpdateStage
    en: StatusUpdateText
    fr: StatusUpdateText

    def blank_fields(self) -> tuple[str, ...]:
        """Return the names (``en.impact``, ``fr.workaround``, ...) of the fields blank after trimming."""
        return tuple(
            f"{language}.{name}"
            for language, text in (("en", self.en), ("fr", self.fr))
            for name in _TEXT_FIELDS
            if not getattr(text, name).strip()
        )


@dataclass(frozen=True)
class CopyReadyText:
    """An approved update rendered as plain text to paste, one string per language."""

    en: str
    fr: str


@dataclass(frozen=True)
class StatusUpdateOverview:
    """An incident's status updates as the modal lists them.

    Attributes:
        pending: The latest record when it is a draft, else ``None``.
        approved: Every approved or published record, newest first.
    """

    pending: StatusUpdate | None
    approved: tuple[StatusUpdate, ...]


@dataclass(frozen=True)
class StatusUpdateFormState:
    """The review form to show after a status-update action.

    Attributes:
        update: The draft whose stage and fields fill the form: the new or
            stored draft, or, when ``kept``, the stored draft overlaid with the
            responder's typed values.
        ai_available: Whether the form offers Draft with AI.
        kind: How a start or fill produced ``update``; ``None`` for a read or a save.
        kept: ``True`` when the action changed nothing and the stored draft was kept.
        failure_code: The classified code that explains a kept draft, when known.
    """

    update: StatusUpdate
    ai_available: bool
    kind: StatusUpdateOutcomeKind | None = None
    kept: bool = False
    failure_code: str | None = None


@dataclass(frozen=True)
class PublishedRecord:
    """An approved status update with its copy-ready text, as the copy-ready view shows it."""

    update: StatusUpdate
    text: CopyReadyText
