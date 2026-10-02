"""Tests for the incident scribe document-store default wiring."""

from collections.abc import Iterator

import pytest

from contracts.operations import OperationStatus
from packages.incident.core.api import TranscriptMessage
from packages.incident.scribe import providers
from packages.incident.scribe.adapters.google_docs import GoogleDocsIncidentDocument
from packages.incident.scribe.domain import DocumentSection, DraftWriteResult
from packages.incident.scribe.service import (
    DOCUMENT_UNREADABLE_CODE,
    IncidentDocumentStore,
    draft_incident_document,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_document_store_cache() -> Iterator[None]:
    """Drop the cached singleton so no instance leaks between tests."""
    yield
    providers.get_incident_document_store.cache_clear()


class _UnreadableDocumentStore:
    """``IncidentDocumentStore`` stub that yields no sections and records the read."""

    def __init__(self) -> None:
        self.read_document_ids: list[str] = []

    def read_sections(self, document_id: str) -> list[DocumentSection]:
        self.read_document_ids.append(document_id)
        return []

    def write_draft_document(self, source_document_id: str, drafts, fields=(), links=None) -> DraftWriteResult | None:
        raise AssertionError("no draft is written when the source has no sections")


def test_default_document_store_is_the_cached_google_docs_adapter() -> None:
    """The default factory returns one cached Google Docs adapter that satisfies the Protocol.

    No stubs: constructing the adapter opens no Google client (clients are
    resolved per call), so the real factory runs. The ``isinstance`` check
    against the runtime-checkable Protocol guards the adapter's method surface.
    """
    documents = providers.get_incident_document_store()

    assert isinstance(documents, GoogleDocsIncidentDocument)
    assert isinstance(documents, IncidentDocumentStore)
    assert providers.get_incident_document_store() is documents


@pytest.mark.asyncio
async def test_service_reads_through_the_provider_store_when_none_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no ``documents`` argument the service reads through the provider's store.

    The provider function is replaced on the providers module, which the
    service imports from at call time, so no Google call is made. The recorded
    read proves the service resolved its default from the provider, and the
    ``DOCUMENT_UNREADABLE`` result is what an empty section list maps to.
    """
    store = _UnreadableDocumentStore()
    monkeypatch.setattr(providers, "get_incident_document_store", lambda: store, raising=True)

    result = await draft_incident_document("DOC1", [TranscriptMessage(author="Ada", text="prod is down")])

    assert store.read_document_ids == ["DOC1"]
    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == DOCUMENT_UNREADABLE_CODE
