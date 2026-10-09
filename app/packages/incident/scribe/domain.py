"""Domain values for the incident scribe use cases.

Frozen, platform-neutral dataclasses shared by the services, the document
adapter, and the platform adapters. This module depends only on the stdlib and
the incident core's public types.
"""

from dataclasses import dataclass
from enum import StrEnum

from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateText

# Written into Author(s). The responders who spoke in the channel did not author
# this document, and a reader needs to know it was machine-written.
AI_AUTHOR = "SRE Bot (AI generated)"


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


@dataclass(frozen=True)
class DraftedDocument:
    """Result of a drafting run: the draft document and what it answered.

    Attributes:
        document_id: Google Docs id of the draft document.
        created: True when this run created the draft, False when it rewrote
            the existing one.
        drafted_headings: Headings answered from the transcript, in document
            order.
        unanswered_headings: Headings the transcript could not answer; these
            keep their original guidance text in the draft.
        partial: True when the model's response was cut off, so later sections
            are missing from an otherwise usable draft.
    """

    document_id: str
    created: bool
    drafted_headings: tuple[str, ...]
    unanswered_headings: tuple[str, ...]
    partial: bool = False


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
