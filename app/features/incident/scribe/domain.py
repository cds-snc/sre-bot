"""Domain values for the incident scribe use cases.

Frozen, platform-neutral values of the drafting use case. The document section
types the report adapter reads and writes come from features/incident/core.
This module depends only on the stdlib.
"""

from dataclasses import dataclass

# Written into Author(s). The responders who spoke in the channel did not author
# this document, and a reader needs to know it was machine-written.
AI_AUTHOR = "SRE Bot (AI generated)"


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
