"""Google-backed adapter for the incident feature's Google Docs boundary.

Per decisions/feature-packages.md this is the only file in
packages/incident/documents/ allowed to import integrations.google_workspace.
Builds a stub-typed DocsResource, owns its own try/except + classify_google_error
around documents().get/.batchUpdate, and exposes incident-domain operations
rather than SDK-shaped passthroughs.
"""

from collections.abc import Mapping
from typing import Any, cast

import structlog
from googleapiclient.errors import HttpError

from integrations.google_workspace.client import classify_google_error, get_docs_service

logger = structlog.get_logger()

_DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]


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


def fetch_document_content(document_id: str) -> list[dict[str, Any]] | None:
    """Return the document body's structural-element list, or None on failure/not-found."""
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
    return cast("list[dict[str, Any]]", content) if content is not None else None


def apply_document_edits(document_id: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply a batchUpdate request list; returns the raw reply dict, or {} on failure."""
    service = get_docs_service(scopes=_DOCS_SCOPES)
    body = cast("Any", {"requests": requests})
    try:
        # Generic passthrough: callers send index-based edits that a replay would apply twice,
        # so retries stay off until a retries-disabled handle exists at construction.
        result = service.documents().batchUpdate(documentId=document_id, body=body).execute(num_retries=0)
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "incident_document_edit_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return {}
    return cast("dict[str, Any]", result) if isinstance(result, dict) else {}
