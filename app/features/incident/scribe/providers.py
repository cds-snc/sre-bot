"""Feature-local dependency wiring for the incident scribe subdomain.

Resolves the default implementations of the Protocols the service depends on,
keeping ``service.py`` and ``entrypoints/`` free of adapter (and therefore
``integrations``) imports.
"""

from functools import lru_cache

from features.incident.scribe.adapters.google_docs import GoogleDocsIncidentDocument
from features.incident.scribe.adapters.slack import build_incident_report_link_lookup
from features.incident.scribe.ports import IncidentReportLinkLookup


@lru_cache(maxsize=1)
def get_incident_document_store() -> GoogleDocsIncidentDocument:
    """Return the process-wide Google-Docs-backed ``IncidentDocumentStore``."""
    return GoogleDocsIncidentDocument()


@lru_cache(maxsize=1)
def get_incident_report_link_lookup() -> IncidentReportLinkLookup:
    """Return the process-wide Slack-backed ``IncidentReportLinkLookup``."""
    return build_incident_report_link_lookup()
