"""Module to manage the incident document used to track the details."""

import datetime
import re
from collections.abc import Callable
from itertools import groupby
from typing import Any
from urllib.parse import urlsplit

from structlog import get_logger

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters import google_docs as incident_drive
from features.incident.core.adapters.google_docs import (
    apply_document_edits,
    fetch_document_snapshot,
    replace_placeholders,
)

START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"
# Writes per timeline update; each is preceded by a fresh read (optimistic-concurrency recompute, no sleep).
TIMELINE_UPDATE_ATTEMPTS = 3
TIMELINE_ENTRY_PATTERN = re.compile(
    r"^[ \t]*➡️[ \t]*\[(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ET\]\((?P<url>https?://[^\s)]+)\)",
    re.MULTILINE,
)

logger = get_logger()


def create_incident_document(title, folder):
    """Create a new incident document in Google Docs.

    Args:
        title (str): The title of the new document.

    Returns:
        str: The ID of the new document.
    """
    document_id = ""
    response = incident_drive.create_document_from_template(title, folder, get_incident_core_settings().report_template_id)
    if response:
        document_id = str(response.get("id") or "")

    return document_id


def update_boilerplate_text(document_id, name, product, slack_channel, on_call_names):
    replacements = {
        "{{date}}": datetime.datetime.now().strftime("%Y-%m-%d"),
        "{{name}}": str(name),
        "{{on-call-names}}": str(on_call_names),
        "{{team}}": str(product),
        "{{slack-channel}}": str(slack_channel),
        "{{status}}": "In Progress",
    }

    replace_placeholders(document_id, replacements, match_case=True)


def update_incident_document_status(document_id, new_status="Closed"):
    """Update the status of the incident document.

    Args:
        document_id (str): The ID of the document to update.
        new_status (str, optional): The new status to set. Defaults to "Closed".

    Returns:
        bool: True if the status was updated, False otherwise.
    """
    # List of possible statuses to be replaced
    possible_statuses = [
        "In Progress",
        "Open",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]

    if new_status not in possible_statuses:
        raise ValueError(f"Invalid status: {new_status}")

    # Replace all possible statuses with the new status
    replacements = {f"Status: {status}": f"Status: {new_status}" for status in possible_statuses if status != new_status}
    return replace_placeholders(document_id, replacements, match_case=False)


def timeline_message_key(url: str) -> tuple[str, str]:
    """Identify a Slack message independently of permalink query parameters."""
    match = re.fullmatch(r"/archives/([^/]+)/p(\d{16,})/?", urlsplit(url).path)
    return (match[1], match[2]) if match else ("", url)


def update_timeline_section(document_id: str, rewrite: Callable[[str], str | None]) -> OperationResult[None]:
    """Rewrite the timeline section from a single document snapshot.

    rewrite receives the current timeline text and returns the new text, or None when
    nothing needs to change. The edit only applies while the document is still at the
    revision it was read at, so an edit built from a stale read is refused instead of
    written over newer content.

    A refused edit whose re-read shows the document moved on (a lost revision guard) and an
    unconfirmed edit (a timeout) are re-read and recomputed, at most TIMELINE_UPDATE_ATTEMPTS
    writes and without sleeping. This is optimistic-concurrency recompute, not a retry of the
    same request: transport retries belong to the SDK (decisions/outbound-clients.md). A
    final read reconciles the last unconfirmed write, so an edit that landed is a success.
    Any other failure, or a refused edit on a document that did not move, stops at once.
    """
    result: OperationResult[None] = OperationResult.transient_error(
        "Document could not be read", error_code=ErrorCode.DOCUMENT_UNREADABLE
    )
    sent_revision: str | None = None
    for attempt in range(1, TIMELINE_UPDATE_ATTEMPTS + 2):
        snapshot = fetch_document_snapshot(document_id)
        if snapshot is None:
            logger.error("incident_timeline_update_failed", document_id=document_id, error="Document unreadable", attempt=attempt)
            return result
        if result.status is OperationStatus.PERMANENT_ERROR and snapshot.revision_id == sent_revision:
            logger.error(
                "incident_timeline_update_failed", document_id=document_id, attempt=attempt, error_code=result.error_code
            )
            return result

        timeline_content = extract_timeline_section(snapshot.content)
        if timeline_content is None:
            logger.warning(
                "incident_timeline_update_failed",
                document_id=document_id,
                error="Headings not found",
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR, "Timeline unavailable", error_code=ErrorCode.RANGE_NOT_FOUND
            )

        new_content = rewrite(timeline_content)
        if new_content is None:
            return OperationResult.success()
        if attempt > TIMELINE_UPDATE_ATTEMPTS:
            break

        requests = build_timeline_replacement(snapshot.content, new_content, START_HEADING, END_HEADING)
        if requests is None:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR, "Timeline boundaries unavailable", error_code=ErrorCode.RANGE_NOT_FOUND
            )

        sent_revision = snapshot.revision_id
        result = apply_document_edits(document_id, requests, sent_revision)
        if result.is_success:
            return result
        if not _recompute_after(result):
            logger.error(
                "incident_timeline_update_failed", document_id=document_id, attempt=attempt, error_code=result.error_code
            )
            return result
        logger.warning(
            "incident_timeline_update_not_applied",
            document_id=document_id,
            attempt=attempt,
            error_code=result.error_code,
        )

    logger.error(
        "incident_timeline_update_failed",
        document_id=document_id,
        error="Edit not confirmed",
        attempts=TIMELINE_UPDATE_ATTEMPTS,
        error_code=result.error_code,
    )
    return result


def _recompute_after(result: OperationResult[None]) -> bool:
    """A timeout may have landed and a refused edit may have lost its revision guard: both are re-read."""
    if result.status is OperationStatus.TRANSIENT_ERROR:
        return result.error_code == ErrorCode.TIMEOUT
    return result.status is OperationStatus.PERMANENT_ERROR and result.error_code == ErrorCode.HTTP_ERROR


def extract_timeline_section(content):
    """Return the text between the timeline headings of a document body, or None if a heading is missing."""
    timeline_content = ""
    record = False
    found_start = False

    # Iterate through the elements of the document
    for element in content:
        if "paragraph" in element:
            paragraph_elements = element.get("paragraph").get("elements")
            paragraph_text = "".join(elem.get("textRun", {}).get("content", "") for elem in paragraph_elements).strip()
            if paragraph_text == START_HEADING:
                record = found_start = True
                continue
            if paragraph_text == END_HEADING and found_start:
                return timeline_content
            if not record:
                continue
            for link, group in groupby(
                paragraph_elements,
                key=lambda elem: elem.get("textRun", {}).get("textStyle", {}).get("link", {}).get("url"),
            ):
                runs = list(group)
                if any("textRun" not in elem for elem in runs):
                    logger.warning("incident_timeline_unsupported_content")
                    return None
                text = "".join(elem["textRun"]["content"] for elem in runs)
                if link and text.strip():
                    leading = text[: len(text) - len(text.lstrip())]
                    trailing = text[len(text.rstrip()) :]
                    text = f"{leading}[{text.strip()}]({link}){trailing}"
                timeline_content += text
        elif record:
            logger.warning("incident_timeline_unsupported_content")
            return None

    # Return None if either START_HEADING or END_HEADING not found
    return None


def find_heading_indices(content, start_heading, end_heading):
    """Find the start and end indices of content between two headings."""
    start_index, end_index = None, None
    for element in content:
        if "paragraph" in element:
            text_runs = element["paragraph"].get("elements", [])
            text = "".join(run.get("textRun", {}).get("content", "") for run in text_runs).strip()
            if text == start_heading:
                start_index = text_runs[-1].get("endIndex")
            elif text == end_heading and start_index is not None:
                return start_index, text_runs[0].get("startIndex")
    return start_index, end_index


def build_timeline_replacement(content, new_content, start_heading, end_heading):
    """Build the batchUpdate requests replacing the text between two headings, or None if a heading is missing.

    The request indices are only valid against the document body they were computed from.
    """
    # Find the start and end indices
    start_index, end_index = find_heading_indices(content, start_heading, end_heading)

    if start_index is not None and end_index is not None:
        new_content = new_content.strip("\n")
        links: list[dict[str, Any]] = []
        pieces = ["\n"]
        end = 0
        for match in re.finditer(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)", new_content):
            pieces.append(new_content[end : match.start()])
            index = start_index + incident_drive._utf16_len("".join(pieces))
            pieces.append(match[1])
            links.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": index, "endIndex": index + incident_drive._utf16_len(match[1])},
                        "textStyle": {"link": {"url": match[2]}},
                        "fields": "link",
                    }
                }
            )
            end = match.end()
        pieces.extend([new_content[end:], "\n"])
        text = "".join(pieces)
        span = {"startIndex": start_index, "endIndex": start_index + incident_drive._utf16_len(text)}
        requests: list[dict[str, Any]] = []
        if end_index > start_index:
            requests.append({"deleteContentRange": {"range": {"startIndex": start_index, "endIndex": end_index}}})
        requests.extend(
            [
                {"insertText": {"location": {"index": start_index}, "text": text}},
                {"updateTextStyle": {"range": span, "textStyle": {}, "fields": "link"}},
                {
                    "updateParagraphStyle": {
                        "range": span,
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "fields": "namedStyleType",
                    }
                },
                *links,
            ]
        )
        return requests

    logger.warning(
        "build_timeline_replacement_failed",
        error="Headings not found",
    )
    return None
