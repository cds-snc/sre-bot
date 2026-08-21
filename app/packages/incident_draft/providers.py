"""Feature-local dependency wiring for the incident_draft package.

Resolves the default implementations of the Protocols the service depends on,
keeping ``service.py`` free of adapter (and therefore ``integrations``) imports.
"""

from __future__ import annotations

from functools import lru_cache

from packages.incident_draft.adapters.google_docs import GoogleDocsIncidentDocument


@lru_cache(maxsize=1)
def get_incident_document_port() -> GoogleDocsIncidentDocument:
    """Return the process-wide Google-Docs-backed ``IncidentDocumentPort``."""
    return GoogleDocsIncidentDocument()
