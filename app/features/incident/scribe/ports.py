"""Interfaces the incident scribe use cases depend on.

The services consume these Protocols and ``providers.py`` binds them to the
adapters, so both import them from here rather than from each other.
"""

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from features.incident.scribe.domain import (
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    SectionDraft,
)


@runtime_checkable
class IncidentDocumentStore(Protocol):
    """Behavior contract for reading the incident document and creating the draft."""

    def read_sections(self, document_id: str) -> list[DocumentSection]:
        """Return the document's sections in document order (empty on failure)."""
        ...

    def write_draft_document(
        self,
        source_document_id: str,
        drafts: Sequence[SectionDraft],
        fields: Sequence[DocumentField],
        links: Mapping[str, str],
    ) -> DraftWriteResult | None:
        """Write the draft document (creating or rewriting it); ``None`` on failure."""
        ...


@runtime_checkable
class IncidentReportLinkLookup(Protocol):
    """Interface finding where an incident conversation's report lives.

    Implementations never raise for a platform failure: they log it and return
    no links.
    """

    def find_report_links(self, conversation_id: str) -> Sequence[str]:
        """Return the links the conversation holds to its incident report.

        The links are plain strings in the order the platform lists them; a
        report entry with no link is an empty string. Empty when the
        conversation has no report entry or the platform lookup failed.
        """
        ...
