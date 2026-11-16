"""Module to manage the incident document used to track the details."""

import datetime
import re
from collections.abc import Callable
from itertools import groupby
from random import uniform
from time import sleep
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
from features.incident.response.settings import get_incident_response_settings

START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"
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
    revision it was read at, so an edit built from a stale read is rejected instead of
    written over newer content. After a rejected or unconfirmed write the document is read
    again and rewrite is re-evaluated, which lets it see an edit that already landed.

    A final read reconciles an unconfirmed last write without replaying stale edits.
    """
    settings = get_incident_response_settings()
    write_limit = settings.timeline_update_attempts
    waited = 0.0
    result: OperationResult[None] = OperationResult.transient_error(
        "Document could not be read", error_code=ErrorCode.DOCUMENT_UNREADABLE
    )
    for attempt in range(1, write_limit + 2):
        snapshot = fetch_document_snapshot(document_id)
        if snapshot is None:
            logger.error("incident_timeline_update_failed", document_id=document_id, error="Document unreadable", attempt=attempt)
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
        if attempt > write_limit:
            break

        requests = build_timeline_replacement(snapshot.content, new_content, START_HEADING, END_HEADING)
        if requests is None:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR, "Timeline boundaries unavailable", error_code=ErrorCode.RANGE_NOT_FOUND
            )

        result = apply_document_edits(document_id, requests, snapshot.revision_id)
        if result.is_success:
            return result
        if result.status is not OperationStatus.TRANSIENT_ERROR:
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
        if attempt < write_limit:
            delay = (
                result.retry_after
                if result.retry_after is not None
                else uniform(  # noqa: S311 -- retry jitter
                    0, min(settings.timeline_retry_cap_seconds, settings.timeline_retry_base_seconds * 2 ** (attempt - 1))
                )
            )
            if delay > settings.timeline_retry_wait_seconds - waited:
                write_limit = attempt
            else:
                sleep(delay)
                waited += delay

    logger.error(
        "incident_timeline_update_failed",
        document_id=document_id,
        error="Edit not confirmed",
        attempts=write_limit,
        error_code=result.error_code,
    )
    return result


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
