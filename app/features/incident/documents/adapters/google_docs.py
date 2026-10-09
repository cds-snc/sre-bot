"""Google-backed adapter for the incident feature's Google Docs boundary.

Per decisions/feature-packages.md this is the only file in
features/incident/documents/ allowed to import integrations.google_workspace.
Builds a stub-typed DocsResource, owns its own try/except + classify_google_error
around documents().get/.batchUpdate, and exposes incident-domain operations
rather than SDK-shaped passthroughs.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import structlog
from googleapiclient.errors import HttpError

from integrations.google_workspace.client import classify_google_error, get_docs_service

logger = structlog.get_logger()

_DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]
_STALE_REVISION_STATUS = 400


@dataclass(frozen=True)
class DocumentSnapshot:
    """A document body together with the revision it was read at."""

    content: list[dict[str, Any]]
    revision_id: str


def replace_placeholders(document_id: str, replacements: Mapping[str, str], match_case: bool = True) -> bool:
    """Replace each key with its value via replaceAllText. Returns whether any occurrence changed."""
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": text, "matchCase": match_case},
                "replaceText": replacement,
            }
        }
        for text, replacement in replacements.items()
    ]
    service = get_docs_service(scopes=_DOCS_SCOPES)
    body = cast("Any", {"requests": requests})
    try:
        result = service.documents().batchUpdate(documentId=document_id, body=body).execute()
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "incident_document_placeholder_replace_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return False
    replies = result.get("replies", []) if isinstance(result, dict) else []
    return any(reply.get("replaceAllText", {}).get("occurrencesChanged", 0) > 0 for reply in replies)


def fetch_document_snapshot(document_id: str) -> DocumentSnapshot | None:
    """Return the document body's structural elements and revision, or None on failure/not-found."""
    service = get_docs_service(scopes=_DOCS_SCOPES)
    try:
        document = service.documents().get(documentId=document_id).execute()
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "incident_document_fetch_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return None
    if not isinstance(document, dict):
        return None
    content = document.get("body", {}).get("content")
    revision_id = document.get("revisionId")
    if content is None or not revision_id:
        return None
    return DocumentSnapshot(content=cast("list[dict[str, Any]]", content), revision_id=revision_id)


def apply_document_edits(document_id: str, requests: list[dict[str, Any]], required_revision_id: str) -> bool:
    """Apply a batchUpdate only if the document is still at required_revision_id.

    Callers send index-based edits computed from a snapshot, so applying them to any other
    revision corrupts the document. Returns True once Google confirms the edit. False means
    it was rejected or its outcome is unknown (a timeout can still land later); the caller
    must take a new snapshot before deciding to send anything again.
    """
    service = get_docs_service(scopes=_DOCS_SCOPES)
    body = cast("Any", {"requests": requests, "writeControl": {"requiredRevisionId": required_revision_id}})
    try:
        # The revision guard makes a second send harmless, but retries stay off: a replay of a
        # landed edit would only come back as a stale-revision rejection of a successful write.
        service.documents().batchUpdate(documentId=document_id, body=body).execute(num_retries=0)
    except TimeoutError:
        logger.warning("incident_document_edit_unconfirmed", document_id=document_id)
        return False
    except HttpError as exc:
        if int(exc.resp.status) == _STALE_REVISION_STATUS:
            # Google answers 400 when the document moved past the required revision.
            logger.warning("incident_document_edit_rejected", document_id=document_id, reason=exc.reason)
            return False
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "incident_document_edit_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return False
    return True
