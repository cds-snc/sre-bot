"""Domain values for the incident_draft feature.

Frozen, platform-neutral dataclasses shared by the service, the document
adapter, and the platform adapters. This module depends only on the stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass

# Written under a retrospective sub-heading the transcript says nothing about,
# so a reader sees the question was considered rather than an empty bullet.
NOT_INDICATED = "This was not indicated in the report"

# Written into Author(s). The responders who spoke in the channel did not author
# this document, and a reader needs to know it was machine-written.
AI_AUTHOR = "SRE Bot (AI Generated)"


@dataclass(frozen=True)
class TranscriptMessage:
    """A single platform-neutral chat message used as drafting evidence.

    ``timestamp`` is a short pre-formatted clock time (e.g. ``"14:09"``) shown
    to the model so it can build a timeline; it is empty when the platform
    adapter could not resolve one.
    """

    author: str
    text: str
    timestamp: str = ""


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

    ``is_question_chain`` marks a five-whys section, whose written content must
    be the only chain in that section.
    """

    heading: str
    content: str
    is_drafted: bool
    as_list: bool = False
    is_question_chain: bool = False


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
        timeline_updated: True when the AI timeline was written into the
            original incident report's timeline section.
    """

    document_id: str
    created: bool
    drafted_headings: tuple[str, ...]
    unanswered_headings: tuple[str, ...]
    timeline_updated: bool = False
