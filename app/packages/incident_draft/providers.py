"""Feature-local dependency wiring for the incident_draft package.

Resolves the default implementations of the Protocols the service and handlers
depend on, keeping ``service.py`` and ``platforms/`` free of adapter (and
therefore ``integrations``) imports.
"""

from functools import lru_cache

from packages.incident_draft.adapters.google_docs import GoogleDocsIncidentDocument
from packages.incident_draft.adapters.slack import build_incident_channel
from packages.incident_draft.service import IncidentChannelPort


@lru_cache(maxsize=1)
def get_incident_document_store() -> GoogleDocsIncidentDocument:
    """Return the process-wide Google-Docs-backed ``IncidentDocumentStore``."""
    return GoogleDocsIncidentDocument()


@lru_cache(maxsize=1)
def get_incident_channel_port() -> IncidentChannelPort:
    """Return the process-wide Slack-backed ``IncidentChannelPort``."""
    return build_incident_channel()
