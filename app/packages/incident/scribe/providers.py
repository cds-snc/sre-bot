"""Feature-local dependency wiring for the incident scribe subdomain.

Resolves the default implementations of the Protocols the service depends on,
keeping ``service.py`` and ``entrypoints/`` free of adapter (and therefore
``integrations``) imports.
"""

from functools import lru_cache

from packages.incident.scribe.adapters.copy_ready import CopyReadyPublisher
from packages.incident.scribe.adapters.google_docs import GoogleDocsIncidentDocument
from packages.incident.scribe.adapters.slack import build_incident_report_link_lookup
from packages.incident.scribe.adapters.text_generation import UnavailableTextGenerator, build_status_update_text_generator
from packages.incident.scribe.ports import IncidentReportLinkLookup, StatusPagePublisher, TextGenerator


@lru_cache(maxsize=1)
def get_incident_document_store() -> GoogleDocsIncidentDocument:
    """Return the process-wide Google-Docs-backed ``IncidentDocumentStore``."""
    return GoogleDocsIncidentDocument()


@lru_cache(maxsize=1)
def get_incident_report_link_lookup() -> IncidentReportLinkLookup:
    """Return the process-wide Slack-backed ``IncidentReportLinkLookup``."""
    return build_incident_report_link_lookup()


@lru_cache(maxsize=1)
def get_status_update_text_generator() -> TextGenerator:
    """Return the process-wide ``TextGenerator`` that drafts status updates."""
    return build_status_update_text_generator()


def text_generation_available() -> bool:
    """Whether the process ``TextGenerator`` is configured rather than the unavailable stand-in."""
    return not isinstance(get_status_update_text_generator(), UnavailableTextGenerator)


@lru_cache(maxsize=1)
def get_status_page_publisher() -> StatusPagePublisher:
    """Return the process-wide ``StatusPagePublisher`` that renders copy-ready text."""
    return CopyReadyPublisher()
