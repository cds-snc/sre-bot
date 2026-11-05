"""Google adapter of the incident umbrella: the incident report in Google Docs and its Drive folder.

The only module in features/incident/ that reaches Google Docs and Drive, under
decisions/feature-packages.md (integrations are imported from adapters/ only).
Sections, in order:

- document ids: Google-Docs-URL id extraction;
- report edits: placeholders, revision-guarded edits and snapshots through
  documents().get/.batchUpdate, each owning its try/except and
  classify_google_error, exposing incident-domain operations rather than
  SDK-shaped passthroughs;
- Drive: file and folder operations and metadata (Drive appProperties) through
  the gateway's Drive service, shared drives included and list results paged
  to the end; the Drive healthcheck;
- section writer: walks the source document body to turn heading-styled
  paragraphs into DocumentSection values (the heading plus the template
  guidance written under it), and writes the draft document -- in the source
  document's Drive folder -- populated with the drafted sections. Each run
  creates a fresh Drive copy of the source document, so repeated invocations
  produce new draft documents rather than rewriting one in place. The source
  incident report is only ever read;
- GoogleDocsIncidentReport: the core ``IncidentReport`` over the functions
  above, for references of the Google system.

Every service is built through the gateway factories with scopes only: no
function passes a delegation subject or builds credentials, so who the calls
run as stays the gateway's decision.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from googleapiclient.errors import HttpError

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.domain import (
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    ReportReference,
    SectionDraft,
)
from integrations.google_workspace import client as google_workspace_client
from integrations.google_workspace.client import classify_google_error, get_docs_service
from integrations.google_workspace.settings import get_google_workspace_settings

if TYPE_CHECKING:
    from googleapiclient._apis.docs.v1 import (  # pyright: ignore[reportMissingModuleSource]
        BatchUpdateDocumentRequest,
        Document,
    )
    from googleapiclient._apis.drive.v3 import DriveResource, File  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()

# --- Document ids ---


def extract_google_doc_id(url):
    """
    Extracts the Google Docs ID from a Google Docs URL.

    Args:
        url (str): The URL of the Google Docs document.

    Returns:
        str: The Google Docs ID extracted from the URL.
    """
    logger.debug(
        "extracting_google_doc_id",
        url=url,
    )
    if not url:
        return None

    # Regular expression pattern to match Google Docs ID
    pattern = r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None


# --- Report edits ---

_DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]
_STALE_REVISION_STATUS = 400


@dataclass(frozen=True)
class DocumentSnapshot:
    """A document body together with the revision it was read at."""

    content: list[dict[str, Any]]
    revision_id: str


def replace_placeholders(document_id: str, replacements: Mapping[str, str], match_case: bool = True) -> bool:
    """Replace each key with its value via replaceAllText. Returns whether any occurrence changed."""
    replaced = _replace_all_text(document_id, replacements, match_case=match_case)
    return bool(replaced.is_success and replaced.data)


def _replace_all_text(document_id: str, replacements: Mapping[str, str], *, match_case: bool) -> OperationResult[bool]:
    """Send one replaceAllText per key; success carries whether any occurrence changed, a refusal is logged and classified."""
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
        return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)
    replies = result.get("replies", []) if isinstance(result, dict) else []
    return OperationResult.success(
        data=any(reply.get("replaceAllText", {}).get("occurrencesChanged", 0) > 0 for reply in replies)
    )


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


# --- Drive ---

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def _drive_service() -> DriveResource:
    return google_workspace_client.get_drive_service(scopes=_DRIVE_SCOPES)


def _file_dict(payload: Mapping[str, Any]) -> dict[str, Any]:
    name = payload.get("name")
    return {"id": str(payload.get("id") or ""), "name": str(name) if name is not None else None}


def _drive_call(operation: str, run: Callable[[], Any]) -> OperationResult[Any]:
    """Run one Drive operation; a classified HttpError is logged by operation and returned, any other error raises."""
    try:
        return OperationResult.success(data=run())
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning("google_drive_operation_failed", operation=operation, status=status.value, error_code=error_code)
        return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)


def _list_all(query: str, operation: str) -> OperationResult[list[dict[str, Any]]]:
    """List every file matching ``query``, page after page, across the user's and shared drives."""

    def run() -> list[dict[str, Any]]:
        files = _drive_service().files()
        request: Any = files.list(q=query, pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="user")
        found: list[dict[str, Any]] = []
        while request is not None:
            response = request.execute()
            found.extend(_file_dict(item) for item in response.get("files", []) if isinstance(item, dict))
            request = files.list_next(request, response)
        return found

    return _drive_call(operation, run)


def _create_from(operation: str, request: Callable[[], Any]) -> OperationResult[dict[str, Any]]:
    return _drive_call(operation, lambda: _file_dict(request().execute()))


def _log_failure(event: str, result: OperationResult[Any]) -> None:
    logger.warning(
        event,
        status=result.status.value,
        error_code=result.error_code,
        retry_after=result.retry_after,
    )


def _log_http_failure(event: str, file_id: str, exc: HttpError) -> None:
    status, error_code, retry_after = google_workspace_client.classify_google_error(exc)
    logger.warning(
        event,
        file_id=file_id,
        status=status.value,
        error_code=error_code,
        retry_after=retry_after,
    )


def list_folder_files(parent_folder_id: str) -> list[dict[str, Any]]:
    result = _list_all(f"parents in '{parent_folder_id}' and mimeType != '{_FOLDER_MIME_TYPE}' and trashed=false", "list_files")
    if not result.is_success:
        _log_failure("incident_drive_list_files_failed", result)
        return []
    return result.data or []


def list_child_folders(parent_folder_id: str) -> list[dict[str, Any]]:
    result = _list_all(f"parents in '{parent_folder_id}' and mimeType = '{_FOLDER_MIME_TYPE}' and trashed=false", "list_folders")
    if not result.is_success:
        _log_failure("incident_drive_list_folders_failed", result)
        return []
    return [file for file in result.data or [] if file["name"] and "Templates" not in file["name"]]


def create_folder(name: str, parent_folder_id: str) -> dict[str, Any] | None:
    result = _create_from(
        "create_folder",
        lambda: (
            _drive_service()
            .files()
            .create(
                body=cast("File", {"name": name, "parents": [parent_folder_id], "mimeType": _FOLDER_MIME_TYPE}),
                supportsAllDrives=True,
            )
        ),
    )
    if not result.is_success:
        _log_failure("incident_drive_create_folder_failed", result)
        return None
    return result.data


def _copy_template(name: str, parent_folder_id: str, template_id: str) -> OperationResult[dict[str, Any]]:
    return _create_from(
        "create_file_from_template",
        lambda: (
            _drive_service()
            .files()
            .copy(fileId=template_id, body=cast("File", {"name": name, "parents": [parent_folder_id]}), supportsAllDrives=True)
        ),
    )


def create_document_from_template(name: str, parent_folder_id: str, template_id: str) -> dict[str, Any] | None:
    result = _copy_template(name, parent_folder_id, template_id)
    if not result.is_success:
        _log_failure("incident_drive_create_document_failed", result)
        return None
    return result.data


def find_document_by_channel_name(channel_name: str) -> dict[str, Any] | None:
    # The name is not escaped, as before: a quote in a channel name fails the query.
    result = _list_all(f"trashed=false and name='{channel_name}'", "find_files_by_name")
    if not result.is_success:
        _log_failure("incident_drive_find_document_failed", result)
        return None

    matches = result.data or []
    if not matches:
        return None

    document_id = matches[0]["id"]
    metadata = get_metadata(document_id, fields="id, name, appProperties")
    return {"id": document_id, "appProperties": metadata.get("appProperties", {})}


def add_metadata(file_id: str, key: str, value: str) -> dict[str, Any]:
    body = cast("File", {"appProperties": {key: value}})
    try:
        file = _drive_service().files().update(fileId=file_id, body=body, supportsAllDrives=True).execute()
    except HttpError as exc:
        _log_http_failure("incident_drive_add_metadata_failed", file_id, exc)
        raise
    return cast("dict[str, Any]", file)


def delete_metadata(file_id: str, key: str) -> dict[str, Any]:
    body = cast("File", {"appProperties": {key: None}})
    try:
        file = _drive_service().files().update(fileId=file_id, body=body, supportsAllDrives=True).execute()
    except HttpError as exc:
        _log_http_failure("incident_drive_delete_metadata_failed", file_id, exc)
        raise
    return cast("dict[str, Any]", file)


def get_metadata(file_id: str, fields: str | None = None) -> dict[str, Any]:
    try:
        file = _drive_service().files().get(fileId=file_id, fields=fields, supportsAllDrives=True).execute()
    except HttpError as exc:
        _log_http_failure("incident_drive_get_metadata_failed", file_id, exc)
        raise
    return cast("dict[str, Any]", file)


def incident_drive_healthcheck() -> bool:
    healthy = False
    try:
        metadata = get_metadata(get_incident_core_settings().report_template_id)
        if metadata is not None:
            healthy = "id" in metadata
        logger.info(
            "google_drive_healthcheck_success",
            status="healthy" if healthy else "unhealthy",
        )
    except Exception as error:
        logger.exception("google_drive_healthcheck_failed", error=str(error))

    return healthy


# --- Section writer ---

_DRAFT_TITLE_SUFFIX = " - AI draft"
_SUBHEADING_STYLE = "HEADING_3"
# The line marking where the SRE bot's generated timeline begins.
# ``modules.incident`` locates the timeline by this exact string to append
# 💾-reacted messages, so it must survive every rewrite of the report.
_SRE_BOT_GENERATED_TIMELINE = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."

# Only these delimit sections; deeper headings are content within one.
_SECTION_HEADING_STYLES = frozenset({"HEADING_1", "HEADING_2"})
_BANNER_PREFIX = "AI draft · generated"
# Generated content is wrapped in named ranges under this prefix.
_NAMED_RANGE_PREFIX = "incident_draft::"
# "PR 1898", "PR #1898", "pr1898" -- how the model refers to a pull request in
# prose once the original Slack link has been summarised away.
# Every way a pull request can appear in drafted text: a full URL the model
# copied through, an explicit "PR 1898"/"pull request 1898", or a bare
# "#1898". Each becomes a hyperlink so no PR is named without a way to open
# it.
_PR_REFERENCE_PATTERN = re.compile(
    r"(?P<url>https?://(?:www\.)?github\.com/[\w.-]+/[\w.-]+/pull/\d+)"
    r"|\b(?:PRs?|pull requests?)\s*#?(?P<number>\d+)\b"
    r"|(?<![\w/])#(?P<issue_number>\d+)\b",
    re.IGNORECASE,
)

# (named range, insert index, block lines, inline text). Exactly one of the last
# two is used: inline text is written on an existing label's line, block lines
# become new paragraphs.
_Placement = tuple[str, int, list[tuple[str, str]], str | None]

# Line kinds produced by _render_body_lines.
_SUBHEADING = "subheading"
_BULLET = "bullet"
_TEXT = "text"

# Guidance every draft should carry under these headings. The report's own
# copy can be missing it, so it is restored rather than assumed.
_ENSURED_GUIDANCE = {
    "detailedtimeline": (
        "Provide a detailed incident timeline, in chronological order, timestamp with timezone(s). "
        "Include any lead-up; start of impact; detection time; escalations, decisions, and changes; "
        "and end of impact."
    ),
    "trigger": "Was there a clear trigger to the incident/outage? If not, leave it blank.",
}

# Impact's labelled groups, dropped from a drafted section when nothing fills
# them rather than left as bare stubs.
_REMOVE_WHEN_EMPTY_LABELS = frozenset(
    {
        "end-users",
        "cds staff",
        "other government department(s)",
        "other",
    }
)

# Metadata labels the template renders as bold headings, which makes them loom
# over the content beneath. They are normalised to ordinary body text instead.
# Some live in the preamble, others inside the Impact section, so they are
# matched by label wherever they appear.
_REGULAR_TEXT_LABELS = frozenset(
    {
        "start-of-impact time",
        "detection time",
        "end-of-impact time",
        "on-call",
        "author(s)",
        "facilitators",
        "end-users",
        "cds staff",
        "other government department(s)",
        "other",
    }
)
_REGULAR_LABEL_FONT_PT = 11

# Labels the template may style as headings. A heading reading "Name: ..." is a
# labelled value, not a section: drafting it as one wrote the value in again
# beneath itself.
_METADATA_LABELS = frozenset(
    {
        "name",
        "team",
        "date",
        "slack channel",
        "status",
    }
)

# Normalised forms, so "Other government department(s)" matches regardless of
# punctuation or spacing drift between the template and the model's output.
_REGULAR_TEXT_LABEL_KEYS = frozenset(re.sub(r"[^a-z0-9]+", "", label) for label in _REGULAR_TEXT_LABELS)
_REMOVE_WHEN_EMPTY_KEYS = frozenset(re.sub(r"[^a-z0-9]+", "", label) for label in _REMOVE_WHEN_EMPTY_LABELS)
_KNOWN_LABEL_KEYS = _REGULAR_TEXT_LABEL_KEYS | frozenset(re.sub(r"[^a-z0-9]+", "", label) for label in _METADATA_LABELS)


def read_document_sections(document_id: str) -> OperationResult[list[DocumentSection]]:
    """Return the document's heading-delimited sections in document order.

    A paragraph styled ``HEADING_*`` starts a new section; every following
    paragraph's text accumulates as that section's instructions until the
    next heading. Text before the first heading is ignored (template
    boilerplate: title, status, metadata table). A fetch the Docs API refuses
    is its classified failure; an unusable response is a transient failure.
    Both are logged.
    """
    service = google_workspace_client.get_docs_service(scopes=_DOCS_SCOPES)
    try:
        document: Document = service.documents().get(documentId=document_id).execute()
    except HttpError as exc:
        status, error_code, retry_after = google_workspace_client.classify_google_error(exc)
        logger.warning(
            "incident_draft_document_fetch_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)
    if not isinstance(document, dict):
        logger.warning("incident_draft_document_fetch_failed", document_id=document_id)
        return OperationResult.transient_error(message="The Docs API returned no document")
    document_data = cast("dict[str, Any]", document)

    sections: list[DocumentSection] = []
    heading: str | None = None
    instruction_parts: list[str] = []

    for element in _body_content(document_data):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        if _is_section_heading(paragraph) and text.strip():
            if heading is not None:
                sections.append(DocumentSection(heading=heading, instructions="".join(instruction_parts)))
            heading = text.strip()
            instruction_parts = []
        elif heading is not None:
            instruction_parts.append(text)

    if heading is not None:
        sections.append(DocumentSection(heading=heading, instructions="".join(instruction_parts)))
    return OperationResult.success(data=sections)


def write_draft_document(
    source_document_id: str,
    drafts: Sequence[SectionDraft],
    fields: Sequence[DocumentField] = (),
    links: Mapping[str, str] = {},
) -> DraftWriteResult | None:
    """Write the draft as a filled-in copy of the incident report.

    The draft is a Drive copy of the source document, so it keeps the
    template's exact formatting -- the metadata block, the blameless
    statement, each section's italic guidance, and the Action Items table.
    Only the bodies of sections the transcript answered are replaced;
    unanswered sections keep the template's guidance untouched, which is
    both simpler and more faithful than rebuilding the layout in code.

    Each run creates a new draft document rather than rewriting one in place.
    Returns ``None`` on any failure; the source report is never written to.
    """
    if not drafts and not fields:
        return None

    # One Drive metadata call yields both the name and the parent folder;
    # fetching the document itself just to read its title meant pulling the
    # whole body over the wire for one string.
    title, folder = _source_name_and_folder(source_document_id)

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    draft_title = f"{title}{_DRAFT_TITLE_SUFFIX} {stamp}"

    # Every run starts from a pristine copy of the report. Editing a
    # long-lived draft in place meant each run inherited the last one's
    # output and had to identify it by heuristics -- the source of
    # duplicated sections, stacked banners and, when two of those analyses
    # proposed overlapping deletions, shredded text. A fresh document
    # cannot accumulate any of it.
    document_id = _copy_source_document(source_document_id, draft_title, folder)
    if not document_id:
        return None

    service = google_workspace_client.get_docs_service(scopes=_DOCS_SCOPES)
    try:
        document: Document = service.documents().get(documentId=document_id).execute()
    except HttpError as exc:
        status, error_code, retry_after = google_workspace_client.classify_google_error(exc)
        logger.warning(
            "incident_draft_draft_fetch_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return None
    if not isinstance(document, dict):
        logger.warning("incident_draft_draft_fetch_failed", document_id=document_id)
        return None
    document_data = cast("dict[str, Any]", document)

    requests = _fill_section_requests(document_data, drafts, fields, links)
    if not requests:
        logger.warning("incident_draft_no_sections_filled", document_id=document_id)
        return None

    body = cast("BatchUpdateDocumentRequest", {"requests": requests})
    try:
        # Index-based insert/delete requests corrupt the document on replay, so retries
        # stay off until a retries-disabled handle exists at construction.
        result = service.documents().batchUpdate(documentId=document_id, body=body).execute(num_retries=0)
    except HttpError as exc:
        status, error_code, retry_after = google_workspace_client.classify_google_error(exc)
        logger.warning(
            "incident_draft_populate_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return None
    if not isinstance(result, dict):
        logger.warning("incident_draft_populate_failed", document_id=document_id)
        return None

    logger.info(
        "incident_draft_document_written",
        document_id=document_id,
        filled_sections=sum(1 for d in drafts if d.is_drafted),
    )
    return DraftWriteResult(document_id=document_id, created=True)


_DOCS_LINK = "https://docs.google.com/document/d/{}/edit"


class GoogleDocsIncidentReport:
    """``IncidentReport`` on Google Docs and Drive, for references of the Google system.

    The document ids are read from [incident_core] at call time, and the tenant
    that names a new report from the Google Workspace entry, the same value the
    configured-systems read reports for Google.
    """

    def create_from_template(self, title: str) -> OperationResult[ReportReference]:
        """Copy the configured template into the configured folder as a new report titled ``title``."""
        settings = get_incident_core_settings()
        missing = _missing_key(
            ("incident_core.folder_id", settings.folder_id), ("incident_core.report_template_id", settings.report_template_id)
        )
        tenant = _google_tenant()
        if missing is None and tenant is None:
            missing = "google_workspace.tenant"
        if missing is not None:
            return _not_configured(missing)
        created = _copy_template(title, settings.folder_id, settings.report_template_id)
        if not created.is_success or not created.data or not created.data["id"]:
            _log_failure("incident_drive_create_document_failed", created)
            return OperationResult.error(
                status=created.status,
                message=created.message or "The report could not be created",
                error_code=created.error_code,
                retry_after=created.retry_after,
            )
        document_id = created.data["id"]
        return OperationResult.success(
            data=ReportReference(
                system=WorkplaceSystem.GOOGLE,
                tenant=cast("str", tenant),
                vendor_id=document_id,
                url=_DOCS_LINK.format(document_id),
            )
        )

    def replace_placeholders(self, report: ReportReference, values: Mapping[str, str]) -> OperationResult[None]:
        """Replace each key with its value in the report, case-sensitive."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _unsupported(report)
        replaced = _replace_all_text(report.vendor_id, values, match_case=True)
        if not replaced.is_success:
            return OperationResult.error(
                status=replaced.status,
                message=replaced.message or "The placeholders could not be replaced",
                error_code=replaced.error_code,
                retry_after=replaced.retry_after,
            )
        return OperationResult.success()

    def read_sections(self, report: ReportReference) -> OperationResult[Sequence[DocumentSection]]:
        """Return the report's sections in document order."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _unsupported(report)
        read = read_document_sections(report.vendor_id)
        if not read.is_success:
            return OperationResult.error(
                status=read.status,
                message=read.message or "The report could not be read",
                error_code=read.error_code,
                retry_after=read.retry_after,
            )
        return OperationResult.success(data=tuple(read.data or ()))

    def write_draft_copy(
        self,
        report: ReportReference,
        drafts: Sequence[SectionDraft],
        fields: Sequence[DocumentField],
        links: Mapping[str, str],
    ) -> OperationResult[DraftWriteResult]:
        """Write a new filled-in copy of the report beside it; failures are logged by the writer."""
        if report.system is not WorkplaceSystem.GOOGLE:
            return _unsupported(report)
        written = write_draft_document(report.vendor_id, drafts, fields, links)
        if written is None:
            return OperationResult.transient_error(message="The draft copy could not be written")
        return OperationResult.success(data=written)

    def link(self, report: ReportReference) -> str | None:
        """Return the stored link of the report."""
        return report.url


def _unsupported[T](report: ReportReference) -> OperationResult[T]:
    logger.warning("incident_report_system_unsupported", system=report.system.value)
    return OperationResult.permanent_error(
        f"Google Docs cannot reach a report on {report.system.value}", ErrorCode.UNSUPPORTED_OPERATION
    )


def _missing_key(*keys: tuple[str, str]) -> str | None:
    return next((key for key, value in keys if not value), None)


def _not_configured[T](key: str) -> OperationResult[T]:
    return OperationResult.permanent_error(f"{key} is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)


def _google_tenant() -> str | None:
    tenant = get_google_workspace_settings().tenant
    return tenant.customer_id if tenant is not None else None


def _regular_label_requests(document: dict) -> list[dict[str, Any]]:
    """Build the requests turning each recognised label line into body text.

    Three things make a label loom: a heading named style, bold text, and an
    enlarged font. All three are reset, so the label matches the surrounding
    body copy regardless of which the template used.
    """
    requests: list[dict[str, Any]] = []
    for element in _body_content(document):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        label, separator, _ = text.partition(":")
        if not separator or _label_key(label) not in _REGULAR_TEXT_LABEL_KEYS:
            continue

        start, end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            continue

        requests.append(_paragraph_style_request(start, end, "NORMAL_TEXT"))
        requests.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end - 1},
                    "textStyle": {
                        "bold": False,
                        "fontSize": {"magnitude": _REGULAR_LABEL_FONT_PT, "unit": "PT"},
                    },
                    "fields": "bold,fontSize",
                }
            }
        )
    return requests


def _copy_source_document(source_document_id: str, draft_title: str, folder: str) -> str | None:
    """Copy the incident report into ``folder`` as the draft; return its id."""
    service = google_workspace_client.get_drive_service(scopes=_DRIVE_SCOPES)
    body = cast("File", {"name": draft_title, "parents": [folder]})
    try:
        # Workspace file copies can't use a pre-generated id, so a replay would duplicate the
        # draft; retries stay off until a retries-disabled handle exists at construction.
        copied = (
            service.files().copy(fileId=source_document_id, body=body, supportsAllDrives=True, fields="id").execute(num_retries=0)
        )
    except HttpError as exc:
        status, error_code, retry_after = google_workspace_client.classify_google_error(exc)
        logger.warning(
            "incident_draft_copy_failed",
            source_document_id=source_document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        return None

    document_id = _created_file_id(copied)
    if not document_id:
        logger.warning("incident_draft_copy_failed", source_document_id=source_document_id)
        return None
    return document_id


def _fill_section_requests(
    document: dict,
    drafts: Sequence[SectionDraft],
    fields: Sequence[DocumentField] = (),
    links: Mapping[str, str] = {},
) -> list[dict[str, Any]]:
    """Write each answered section's draft into the copied template.

    The template's italic guidance is never deleted -- it stays as the
    instructions for that section, with drafted content below it.

    Where the template already provides sub-labels ("What went well", "What
    went wrong", "Where we got lucky"), the draft's matching group is placed
    under *that* label and the generated label is dropped; emitting our own
    would leave the heading printed twice. Anything without a matching label
    goes at the end of the section.

    Content is wrapped in Google Docs *named ranges* so a re-run replaces
    exactly what the previous run wrote. Placements are applied **bottom-up**,
    so an edit higher in the document cannot invalidate indices already used
    below it; fields and the banner follow for the same reason.
    """
    spans = _section_spans(document)
    generated = _generated_ranges(document)
    answered = [d for d in drafts if d.is_drafted and d.heading in spans]
    field_spans = _field_spans(document)
    fillable_fields = [f for f in fields if f.value.strip() and f.label in field_spans]
    # Restyling changes no text lengths, so it can lead the batch: it applies
    # against the snapshot every other edit was computed from, which saves
    # re-fetching the document for a second round trip.
    requests: list[dict[str, Any]] = _regular_label_requests(document)
    repairs = _doubled_value_repairs(document)
    marker_blocks = _sre_bot_generated_timeline_spans(document)
    if not answered and not fillable_fields and not repairs and not marker_blocks:
        return []

    placements: list[_Placement] = []
    stale_blocks: list[tuple[int, int]] = []
    for draft in answered:
        section_placements = _placements_for(document, draft, spans[draft.heading], generated)
        placements.extend(section_placements)
        stale_blocks.extend(_empty_label_spans(document, spans[draft.heading], section_placements))
        stale_blocks.extend(_empty_bullet_spans(document, spans[draft.heading]))
        protected = [span for name, _, _, _ in section_placements for span in generated.get(name, [])]
        stale_blocks.extend(_stale_content_blocks(document, spans[draft.heading], protected))

    # Everything that touches the body is ordered bottom-up together, so an
    # edit higher up cannot invalidate indices already used below it.
    # Several independent sweeps propose deletions from the same snapshot, and
    # they can target overlapping spans. Applied in sequence, the first shifts
    # the document and the second then deletes the wrong range -- which shredded
    # neighbouring text into fragments. Merging first makes the set disjoint.
    operations: list[tuple[int, list[dict[str, Any]]]] = [
        (start, [{"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}])
        for start, end in _merge_overlapping([*stale_blocks, *marker_blocks])
    ]
    operations.extend(repairs)
    operations.extend(_ensured_guidance_operations(document, spans))

    for name, insert_at, lines, inline_text in sorted(placements, key=lambda p: p[1], reverse=True):
        placement_requests: list[dict[str, Any]] = []
        previous = generated.get(name, [])
        if previous:
            # Drop the marker before its content so the name is free to reuse.
            placement_requests.append({"deleteNamedRange": {"name": name}})
            for start, end in sorted(previous, reverse=True):
                placement_requests.append({"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}})

        if inline_text is not None:
            # Written on the label's own line, after its colon.
            placement_requests.append({"insertText": {"location": {"index": insert_at}, "text": inline_text}})
            placement_requests.extend(_pr_link_requests(inline_text, insert_at, links))
            placement_requests.append(
                {
                    "createNamedRange": {
                        "name": name,
                        "range": {"startIndex": insert_at, "endIndex": insert_at + _utf16_len(inline_text)},
                    }
                }
            )
            operations.append((insert_at, placement_requests))
            continue

        builder = _RequestBuilder(start_index=insert_at, links=links)
        for text, kind in lines:
            if kind == _SUBHEADING:
                builder.insert(f"{text}\n", named_style=_SUBHEADING_STYLE)
                continue
            builder.insert(
                f"{text}\n",
                named_style="NORMAL_TEXT",
                bullet=kind == _BULLET,
            )
        placement_requests.extend(builder.build())

        if builder.end_index > insert_at:
            placement_requests.append(
                {
                    "createNamedRange": {
                        "name": name,
                        "range": {"startIndex": insert_at, "endIndex": builder.end_index},
                    }
                }
            )
        operations.append((insert_at, placement_requests))

    for _, operation_requests in sorted(operations, key=lambda item: item[0], reverse=True):
        requests.extend(operation_requests)

    # The metadata block sits above every section, so it is filled after them
    # -- still bottom-up overall.
    for field in sorted(fillable_fields, key=lambda f: field_spans[f.label][0], reverse=True):
        start, end = field_spans[field.label]
        if end > start:
            requests.append({"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}})
        requests.append({"insertText": {"location": {"index": start}, "text": f" {field.value.strip()}"}})

    # The banner sits at the top and shifts the whole document, so it is
    # written last. Every previous banner is removed first (highest index
    # first, so the deletions do not disturb one another), which also clears
    # any pile left by earlier runs.
    existing_banners = _banner_spans(document)
    for banner_start, banner_end in sorted(existing_banners, reverse=True):
        requests.append({"deleteContentRange": {"range": {"startIndex": banner_start, "endIndex": banner_end}}})
    insert_at = min((start for start, _ in existing_banners), default=1)

    generated_on = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    banner = _RequestBuilder(start_index=insert_at)
    banner.insert(
        f"{_BANNER_PREFIX} {generated_on} · review every section before sharing\n",
        named_style="NORMAL_TEXT",
        italic=True,
        muted=True,
    )
    requests.extend(banner.build())
    return requests


def _placements_for(
    document: dict,
    draft: SectionDraft,
    span: tuple[int, int],
    generated: dict[str, list[tuple[int, int]]],
) -> list[_Placement]:
    """Split a draft into placements against the template's own structure.

    Three shapes, in priority order:

    - A ``Label: value`` line whose label the template already prints on its own
      line (Impact's "End-users:", "CDS Staff:", ...) is written *inline* after
      that label's colon, so the value sits beside its label instead of in a
      paragraph of prose further down.
    - A group under a sub-label the template prints ("What went wrong") goes
      beneath that label, without repeating it.
    - Anything left over forms one block at the end of the section.
    """
    lines = _render_body_lines(draft.content, force_bullets=draft.as_list)
    inline_labels = _inline_label_spans(document, span)

    placements: list[_Placement] = []
    remainder: list[tuple[str, str]] = []

    # Action items belong in the template's table, which is where a reader
    # expects to assign a type, owner and priority. Rows are filled first;
    # anything that does not fit falls through to the bullets above it, so no
    # item is silently dropped.
    rows = _empty_table_rows(document, span)
    if draft.as_list or rows:
        logger.info(
            "incident_draft_table_scan",
            heading=draft.heading,
            section_span=span,
            as_list=draft.as_list,
            tables_in_section=_table_count(document, span),
            empty_rows=len(rows),
        )
    if rows and draft.as_list:
        items = [text for text, kind in lines if kind in (_BULLET, _TEXT) and text.strip()]
        for row_index, (item, cell_index) in enumerate(zip(items, rows, strict=False)):
            name = f"{_NAMED_RANGE_PREFIX}{draft.heading}::row{row_index}"
            placements.append((name, _placement_index(name, cell_index, generated), [], item))
        placed = set(items[: len(rows)])
        lines = [(text, kind) for text, kind in lines if text not in placed]

    for label, group in _group_by_subheading(lines):
        if label:
            remainder.append((label, _SUBHEADING))

        for text, kind in group:
            inline = _match_inline_label(text, inline_labels)
            if inline is None:
                remainder.append((text, kind))
                continue

            inline_key, value = inline
            name = f"{_NAMED_RANGE_PREFIX}{draft.heading}::{inline_key}"
            value_start, _, has_value = inline_labels[inline_key]
            if has_value and name not in generated:
                # The template filled this at incident creation (Name, Team,
                # Date, Slack channel, Status). That value is authoritative;
                # writing beside it is what duplicated the text.
                continue
            placements.append((name, _placement_index(name, value_start, generated), [], f" {value}"))

    if remainder:
        name = f"{_NAMED_RANGE_PREFIX}{draft.heading}"
        content_end = _section_content_end(document, span)
        placements.append((name, _placement_index(name, content_end, generated), remainder, None))
    return placements


def _match_inline_label(text: str, inline_labels: dict[str, tuple[int, int, bool]]) -> tuple[str, str] | None:
    """Split ``"Label: value"`` when the template prints that label inline."""
    label, separator, value = text.partition(":")
    if not separator:
        return None
    key = label.strip().lower()
    if key not in inline_labels or not value.strip():
        return None
    return key, value.strip()


def _inline_label_spans(document: dict, span: tuple[int, int]) -> dict[str, tuple[int, int, bool]]:
    """Map ``Label:`` lines inside a section to ``(start, end, has_value)``.

    ``has_value`` reports whether the label already carries text. Fields filled
    when the incident was created -- Name, Team, Date, Slack channel, Status --
    arrive that way, and writing beside them produced "Status: In Progress In
    Progress". Only labels the template left blank are filled.

    Only short labels qualify, so a sentence of guidance that merely contains a
    colon is not mistaken for one.
    """
    start, end = span
    labels: dict[str, tuple[int, int, bool]] = {}
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        text = _paragraph_text(paragraph)
        label, separator, value = text.partition(":")
        key = label.strip().lower()
        if not separator or not key or len(key.split()) > 6 or len(key) > 40:
            continue
        if key not in labels:
            value_start = element_start + _utf16_len(label) + 1
            labels[key] = (value_start, max(value_start, element_end - 1), bool(value.strip()))
    return labels


def _empty_table_rows(document: dict, span: tuple[int, int]) -> list[int]:
    """Insert positions for the first cell of each empty row in a section's table.

    The header row and any row somebody has already filled are skipped, so a
    re-run adds to the table rather than overwriting work.
    """
    start, end = span
    positions: list[int] = []
    for element in _body_content(document):
        element_start = element.get("startIndex")
        table = element.get("table")
        if not table or not isinstance(element_start, int):
            continue
        # Matched on where the table begins: a final section's span stops one
        # character short of the body, so requiring the whole table to fit
        # inside it would miss the Action Items table entirely.
        if not start <= element_start < end:
            continue

        for row in table.get("tableRows") or []:
            cells = row.get("tableCells") or []
            if not cells:
                continue
            first = cells[0]
            text = _table_cell_text(first)
            if text.strip():
                continue  # a header, or a row already written
            insert_at = _table_cell_insert_index(first)
            if insert_at is not None:
                positions.append(insert_at)
    return positions


def _table_count(document: dict, span: tuple[int, int]) -> int:
    """How many tables sit in a section -- diagnostics for the Action Items fill."""
    start, end = span
    return sum(
        1
        for element in _body_content(document)
        if element.get("table") and isinstance(element.get("startIndex"), int) and start <= element["startIndex"] < end
    )


def _table_cell_text(cell: dict) -> str:
    """Concatenate the text of every paragraph in a table cell."""
    parts = []
    for element in cell.get("content") or []:
        paragraph = element.get("paragraph")
        if paragraph:
            parts.append(_paragraph_text(paragraph))
    return "".join(parts)


def _table_cell_insert_index(cell: dict) -> int | None:
    """Return the index at which text is inserted into a cell."""
    for element in cell.get("content") or []:
        start = element.get("startIndex")
        if element.get("paragraph") and isinstance(start, int):
            return start
    return None


def _group_by_subheading(lines: list[tuple[str, str]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split classified lines into ``(subheading, following lines)`` groups."""
    groups: list[tuple[str, list[tuple[str, str]]]] = [("", [])]
    for text, kind in lines:
        if kind == _SUBHEADING:
            groups.append((text, []))
            continue
        groups[-1][1].append((text, kind))
    return [(label, group) for label, group in groups if label or group]


def _guidance_spans(document: dict, span: tuple[int, int]) -> list[tuple[int, int]]:
    """Spans of the template's italic guidance inside a section.

    Used only for sections listed in ``_REMOVE_GUIDANCE_HEADINGS``, where the
    guidance contradicts the drafted answer once one exists ("Was there a clear
    trigger...? If not, leave it blank."). Every other section keeps its
    guidance, which is what the model and the reviewer both work from.
    """
    start, end = span
    spans: list[tuple[int, int]] = []
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if not paragraph or not _paragraph_text(paragraph).strip():
            continue
        if _is_italic_paragraph(paragraph):
            spans.append((element_start, element_end))
    return spans


def _stale_content_blocks(
    document: dict,
    span: tuple[int, int],
    protected: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Content in a drafted section that belongs to neither template nor this run.

    A section should end up holding the template's structure plus exactly one
    generation. Anything else is output from an earlier run that predates named
    ranges, and appending beside it is what produced two summaries saying the
    same thing. Four things are spared:

    - **Italic paragraphs** -- the template's guidance.
    - **``Label:`` lines** -- Impact's groups and the metadata block, which the
      template prints and this package fills in place.
    - **Sub-labels** -- "What went wrong" and friends.
    - **Named ranges this run replaces**, which would otherwise be deleted
      twice.

    Empty paragraphs and non-paragraph elements (the Action Items table) are
    left alone.
    """
    start, end = span
    blocks: list[tuple[int, int]] = []

    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        if any(p_start <= element_start and p_end >= element_end for p_start, p_end in protected):
            continue

        text = _paragraph_text(paragraph).strip()
        if not text or _is_guidance_paragraph(paragraph):
            continue
        if _looks_like_label_line(text):
            continue
        blocks.append((element_start, element_end))

    return _merge_adjacent(blocks)


def _looks_like_label_line(text: str) -> bool:
    """Whether a line is a ``Label:`` the template prints and we fill in place."""
    label, separator, _ = text.partition(":")
    key = label.strip()
    return bool(separator) and bool(key) and len(key.split()) <= 6 and len(key) <= 40


def _merge_adjacent(blocks: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Join touching spans so consecutive paragraphs delete as one range."""
    return _merge_overlapping(blocks)


def _merge_overlapping(blocks: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Reduce spans to a disjoint set, joining those that touch or overlap.

    Two deletions that overlap cannot both be applied: the first shifts every
    index after it, so the second removes text it was never meant to. Merging
    them into one range is the only safe way to honour both.
    """
    merged: list[tuple[int, int]] = []
    for block_start, block_end in sorted(blocks):
        if block_end <= block_start:
            continue
        if merged and block_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], block_end))
        else:
            merged.append((block_start, block_end))
    return merged


def _is_italic_paragraph(paragraph: dict) -> bool:
    """Whether a paragraph's text is italic -- the template's guidance style."""
    runs = _text_runs(paragraph)
    if not runs:
        return False
    return all((run.get("textStyle") or {}).get("italic") for run in runs)


def _is_guidance_paragraph(paragraph: dict) -> bool:
    """Whether a paragraph is template guidance rather than written content.

    Guidance is italic *or* grey. Both are checked because deleting a template's
    instructions would be a destructive misread, and a template that styles its
    guidance with colour alone is entirely plausible.
    """
    runs = _text_runs(paragraph)
    if not runs:
        return False
    return all((run.get("textStyle") or {}).get("italic") or _is_grey(run.get("textStyle") or {}) for run in runs)


def _is_grey(text_style: dict) -> bool:
    """Whether a run is rendered in grey, as template guidance usually is."""
    rgb = (((text_style.get("foregroundColor") or {}).get("color") or {}).get("rgbColor")) or {}
    if not rgb:
        return False
    channels = [float(rgb.get(channel, 0.0)) for channel in ("red", "green", "blue")]
    # Near-equal channels well short of black: a grey rather than a hue.
    return max(channels) - min(channels) < 0.1 and 0.2 < sum(channels) / 3 < 0.85


def _text_runs(paragraph: dict) -> list[dict]:
    """Return a paragraph's non-empty text runs."""
    runs = [element.get("textRun") for element in paragraph.get("elements") or []]
    return [run for run in runs if run and (run.get("content") or "").strip()]


def _empty_label_spans(
    document: dict,
    span: tuple[int, int],
    placements: Sequence[_Placement],
) -> list[tuple[int, int]]:
    """Spans of labels left with no value after filling a section.

    Only labels this package fills (Impact's groups) and only in a section it
    actually drafted: a label carrying a value -- written now, or left by an
    earlier run -- is kept, and a section the transcript could not answer keeps
    its template structure untouched so a human can fill it in.
    """
    filled = {name.rpartition("::")[2] for name, _, _, inline in placements if inline is not None}
    start, end = span
    spans: list[tuple[int, int]] = []

    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        text = _paragraph_text(paragraph)
        label, separator, value = text.partition(":")
        key = label.strip().lower()
        if not separator or _label_key(label) not in _REMOVE_WHEN_EMPTY_KEYS:
            continue
        if key in filled or value.strip():
            continue
        spans.append((element_start, element_end))
    return spans


def _ensured_guidance_operations(
    document: dict,
    spans: dict[str, tuple[int, int]],
) -> list[tuple[int, list[dict[str, Any]]]]:
    """Restore the template guidance a section is missing.

    Inserted immediately under the heading, in the same muted italic the
    template uses elsewhere. A section that already has guidance is left alone,
    so this never produces a second copy.
    """
    operations: list[tuple[int, list[dict[str, Any]]]] = []
    for heading, span in spans.items():
        text = _ENSURED_GUIDANCE.get(_label_key(heading))
        if not text or _has_guidance(document, span):
            continue

        builder = _RequestBuilder(start_index=span[0])
        builder.insert(f"{text}\n", named_style="NORMAL_TEXT", italic=True, muted=True)
        operations.append((span[0], builder.build()))
    return operations


def _has_guidance(document: dict, span: tuple[int, int]) -> bool:
    """Whether a section already carries a line of template guidance."""
    start, end = span
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if paragraph and _paragraph_text(paragraph).strip() and _is_guidance_paragraph(paragraph):
            return True
    return False


def _section_content_end(document: dict, span: tuple[int, int]) -> int:
    """Where a section's written content belongs: after its last real line.

    The template leaves a blank paragraph before the next heading. Inserting at
    the section boundary put the draft below that blank, showing a gap between
    the guidance and the answer.
    """
    start, end = span
    content_end = end
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if paragraph and _paragraph_text(paragraph).strip():
            content_end = element_end
    return content_end


def _empty_bullet_spans(document: dict, span: tuple[int, int]) -> list[tuple[int, int]]:
    """Spans of the template's empty bullets inside a section.

    The template seeds each of Trigger, Detection, Resolution/Recovery and the
    retrospective groupings with a bullet holding no text. Once the section is
    drafted those read as items nobody filled in.
    """
    start, end = span
    spans: list[tuple[int, int]] = []
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if not paragraph or "bullet" not in paragraph:
            continue
        if not _paragraph_text(paragraph).strip():
            spans.append((element_start, element_end))
    return spans


def _sre_bot_generated_timeline_spans(document: dict) -> list[tuple[int, int]]:
    """Spans of the bot's timeline marker, which a draft has no use for.

    It exists so ``modules.incident`` can find the timeline in the *report*;
    the draft is a copy nothing appends to, where it is only noise. The report's
    own copy is untouched.
    """
    spans: list[tuple[int, int]] = []
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        paragraph = element.get("paragraph")
        if paragraph and _SRE_BOT_GENERATED_TIMELINE in _paragraph_text(paragraph):
            spans.append((element_start, element_end))
    return spans


def _placement_index(name: str, default: int, generated: dict[str, list[tuple[int, int]]]) -> int:
    """Where a placement belongs: over the last run's span, else ``default``."""
    previous = generated.get(name)
    if previous:
        return min(start for start, _ in previous)
    return default


def _doubled_value_repairs(document: dict) -> list[tuple[int, list[dict[str, Any]]]]:
    """Collapse ``Label: value value`` lines back to a single value.

    Earlier versions wrote a value beside one the template already had, leaving
    "Status: In Progress In Progress". That text is not inside a named range, so
    nothing else can identify it as generated -- but a value repeated verbatim
    is unambiguous, and repairing it is better than asking for the document to
    be recreated. Only an exact doubling is touched; anything else is left
    alone.
    """
    operations: list[tuple[int, list[dict[str, Any]]]] = []
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        text = _paragraph_text(paragraph)
        label, separator, value = text.partition(":")
        if not separator or not _looks_like_label_line(text):
            continue

        single = _halve_if_doubled(value)
        if single is None:
            continue

        value_start = element_start + _utf16_len(label) + 1
        value_end = max(value_start, element_end - 1)
        if value_end <= value_start:
            continue
        operations.append(
            (
                value_start,
                [
                    {"deleteContentRange": {"range": {"startIndex": value_start, "endIndex": value_end}}},
                    {"insertText": {"location": {"index": value_start}, "text": f" {single}"}},
                ],
            )
        )
    return operations


def _halve_if_doubled(value: str) -> str | None:
    """Return the single value when ``value`` is one string written twice."""
    stripped = value.strip()
    if not stripped:
        return None
    for separator in (" ", ""):
        remainder = len(stripped) - len(separator)
        if remainder <= 0 or remainder % 2:
            continue
        half = remainder // 2
        first, second = stripped[:half], stripped[half + len(separator) :]
        if first and first == second:
            return first
    return None


def _banner_spans(document: dict) -> list[tuple[int, int]]:
    """Return the spans of *every* previous run's banner, in document order.

    All of them, not just the first: a document that already accumulated
    several banners would otherwise shed one per run while gaining a new one,
    so the pile never shrinks.
    """
    spans: list[tuple[int, int]] = []
    for element in _body_content(document):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        if not _paragraph_text(paragraph).lstrip().startswith(_BANNER_PREFIX):
            continue
        start, end = element.get("startIndex"), element.get("endIndex")
        if isinstance(start, int) and isinstance(end, int) and end > start:
            spans.append((start, end))
    return spans


def _field_spans(document: dict) -> dict[str, tuple[int, int]]:
    """Map metadata labels to the ``(start, end)`` span of their value.

    Only the preamble above the first real section is scanned -- that is where
    the report's ``Label: value`` block lives, and a colon further down the
    document is ordinary prose. The span covers the text after the colon up to
    (but not including) the paragraph's newline, so filling a field rewrites
    only its value.

    The stop condition is a *section* heading, not any heading: the template
    styles ``Name:``, ``Team:`` and ``Date:`` as headings, so stopping at the
    first heading of any kind ended the scan before the metadata block began,
    and no field was ever filled.
    """
    spans: dict[str, tuple[int, int]] = {}
    for element in _body_content(document):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        if _is_section_heading(paragraph) and text.strip():
            break  # the metadata block ends at the first real section

        label, separator, _ = text.partition(":")
        start_index = element.get("startIndex")
        end_index = element.get("endIndex")
        if not separator or not isinstance(start_index, int) or not isinstance(end_index, int):
            continue

        label = label.strip()
        if label and label not in spans:
            value_start = start_index + _utf16_len(text.split(":", 1)[0]) + 1
            spans[label] = (value_start, max(value_start, end_index - 1))
    return spans


def _generated_ranges(document: dict) -> dict[str, list[tuple[int, int]]]:
    """Map each named range this package owns to the spans it covers."""
    generated: dict[str, list[tuple[int, int]]] = {}
    for name, entry in (document.get("namedRanges") or {}).items():
        if not name.startswith(_NAMED_RANGE_PREFIX):
            continue
        spans: list[tuple[int, int]] = []
        for named_range in entry.get("namedRanges") or []:
            for span in named_range.get("ranges") or []:
                start, end = span.get("startIndex"), span.get("endIndex")
                if isinstance(start, int) and isinstance(end, int) and end > start:
                    spans.append((start, end))
        if spans:
            generated[name] = spans
    return generated


def _section_spans(document: dict) -> dict[str, tuple[int, int]]:
    """Map each heading to the ``(start, end)`` span of the body beneath it.

    A section's body runs from the end of its heading paragraph to the start of
    the next heading (or the end of the body for the final section). Boundaries
    come from real ``HEADING_*`` styles only -- matching on paragraph text was
    what let a stray "Trigger" line inside the timeline truncate a replacement
    and leave duplicated content behind. The first occurrence of a heading
    wins.
    """
    spans: dict[str, tuple[int, int]] = {}
    heading: str | None = None
    start: int | None = None
    last_end = 1

    for element in _body_content(document):
        element_start = element.get("startIndex")
        element_end = element.get("endIndex")
        if isinstance(element_end, int):
            last_end = element_end

        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph).strip()
        if not (_is_section_heading(paragraph) and text):
            continue

        if heading is not None and start is not None and isinstance(element_start, int) and heading not in spans:
            spans[heading] = (start, max(start, element_start))
        heading = text
        start = element_end if isinstance(element_end, int) else None

    if heading is not None and start is not None and heading not in spans:
        # The final section runs to the end of the body, less its mandatory
        # trailing newline.
        spans[heading] = (start, max(start, last_end - 1))
    return spans


class _RequestBuilder:
    """Accumulates ``batchUpdate`` requests while tracking the running index."""

    def __init__(self, start_index: int = 1, links: Mapping[str, str] = {}) -> None:
        self._requests: list[dict[str, Any]] = []
        self._bullets: list[tuple[int, int]] = []
        self._index = start_index
        self._links = links

    def insert(
        self,
        text: str,
        *,
        named_style: str,
        italic: bool = False,
        muted: bool = False,
        bullet: bool = False,
        bold: bool = False,
        indent_pt: int = 0,
    ) -> None:
        """Insert ``text`` at the running index and style the range it occupies."""
        if not text:
            return
        start, end = self._index, self._index + _utf16_len(text)
        self._requests.append({"insertText": {"location": {"index": start}, "text": text}})
        self._requests.append(_paragraph_style_request(start, end, named_style, indent_pt=indent_pt))
        if italic or muted or bold:
            self._requests.append(_text_style_request(start, end, italic=italic, muted=muted, bold=bold))
        if bullet:
            self._bullets.append((start, end))
        self._requests.extend(_pr_link_requests(text, start, self._links))
        self._index = end

    @property
    def end_index(self) -> int:
        """Index just past the last character inserted."""
        return self._index

    def build(self) -> list[dict[str, Any]]:
        """Return the requests, with bullet conversions applied last."""
        bullet_requests = [_bullet_request(start, end) for start, end in reversed(self._bullets)]
        return [*self._requests, *bullet_requests]


def _render_body_lines(content: str, *, force_bullets: bool = False) -> list[tuple[str, str]]:
    """Classify section content into ``(text, kind)`` lines.

    ``kind`` is one of ``_SUBHEADING``, ``_BULLET`` or ``_TEXT``:

    - A retrospective label ("What went wrong", "What went well", "Where we got
      lucky") or any unbulleted line ending in a colon becomes a sub-heading,
      rendered as ``HEADING_3`` with its trailing colon dropped.
    - A line opening with ``-``, ``*`` or ``•`` becomes a real bullet with the
      marker stripped, so list-shaped answers render as lists instead of
      literal dashes.
    - ``force_bullets`` bullets remaining lines too -- used for action items,
      follow-ups and timelines, which belong in a list even when the model
      returns them unmarked. Sub-headings still win over it.

    Blank lines are dropped; an empty section yields a single blank line so the
    heading still has a paragraph under it.
    """
    lines: list[tuple[str, str]] = []
    for raw_line in content.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        marker = re.match(r"^[-*•]\s+(.*)$", line)
        if marker:
            lines.append((_strip_markdown(marker.group(1)), _BULLET))
            continue

        text = _strip_markdown(line)
        if _is_subheading(text):
            lines.append((text.rstrip(":").strip(), _SUBHEADING))
            continue

        lines.append((text, _BULLET if force_bullets else _TEXT))
    return lines or [("", _TEXT)]


def _is_subheading(text: str) -> bool:
    """Whether an unbulleted line introduces a group of points."""
    stripped = text.rstrip(":").strip().lower()
    # A short trailing-colon label, not a sentence that merely contains a colon.
    return text.endswith(":") and len(stripped.split()) <= 6


def _strip_markdown(text: str) -> str:
    """Remove Markdown emphasis and heading markers from model output.

    The prompt asks for plain text, but models still emit ``**bold**`` and
    ``##`` headings, which Google Docs renders literally. Real styling comes
    from named styles instead.
    """
    text = re.sub(r"^#{1,6}\s+", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    return text.strip()


def _utf16_len(text: str) -> int:
    """Return the length of ``text`` in UTF-16 code units.

    Google Docs indexes count UTF-16 code units, while ``len`` counts code
    points: a character outside the Basic Multilingual Plane (most emoji)
    takes two units, so index arithmetic done with ``len`` drifts after it.
    """
    return len(text.encode("utf-16-le")) // 2


def _pr_link_requests(text: str, start: int, links: Mapping[str, str]) -> list[dict[str, Any]]:
    """Hyperlink every pull request the drafted text names.

    A URL written out in the text links to itself; a "PR 1898" or "#1898"
    reference links to the URL the service resolved for that number. Only a
    reference the service could not resolve at all is left as plain text -- a
    wrong link is worse than none.
    """
    requests: list[dict[str, Any]] = []
    for match in _PR_REFERENCE_PATTERN.finditer(text):
        url = match.group("url") or links.get(match.group("number") or match.group("issue_number") or "")
        if not url:
            continue
        requests.append(
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": start + _utf16_len(text[: match.start()]),
                        "endIndex": start + _utf16_len(text[: match.end()]),
                    },
                    "textStyle": {"link": {"url": url}},
                    "fields": "link",
                }
            }
        )
    return requests


def _paragraph_style_request(start: int, end: int, style: str, *, indent_pt: int = 0) -> dict[str, Any]:
    """Build an ``updateParagraphStyle`` request for a named style and indent."""
    paragraph_style: dict[str, Any] = {"namedStyleType": style}
    fields = ["namedStyleType"]
    if indent_pt:
        paragraph_style["indentStart"] = {"magnitude": indent_pt, "unit": "PT"}
        fields.append("indentStart")
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "paragraphStyle": paragraph_style,
            "fields": ",".join(fields),
        }
    }


def _text_style_request(start: int, end: int, *, italic: bool, muted: bool, bold: bool = False) -> dict[str, Any]:
    """Build an ``updateTextStyle`` request for bold, italic and/or muted text."""
    text_style: dict[str, Any] = {}
    fields = []
    if bold:
        text_style["bold"] = True
        fields.append("bold")
    if italic:
        text_style["italic"] = True
        fields.append("italic")
    if muted:
        text_style["foregroundColor"] = {"color": {"rgbColor": {"red": 0.45, "green": 0.45, "blue": 0.45}}}
        fields.append("foregroundColor")
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "textStyle": text_style,
            "fields": ",".join(fields),
        }
    }


def _bullet_request(start: int, end: int) -> dict[str, Any]:
    """Build a ``createParagraphBullets`` request for a disc bullet."""
    return {
        "createParagraphBullets": {
            "range": {"startIndex": start, "endIndex": end},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
        }
    }


def _source_name_and_folder(document_id: str) -> tuple[str, str]:
    """Return the source document's name and parent folder in one call.

    Falls back to the configured incident folder when the metadata lookup
    fails, so a draft still lands somewhere responders can find it.
    """
    service = google_workspace_client.get_drive_service(scopes=_DRIVE_SCOPES)
    metadata: Any = None
    try:
        metadata = service.files().get(fileId=document_id, fields="id, name, parents", supportsAllDrives=True).execute()
    except HttpError as exc:
        status, error_code, retry_after = google_workspace_client.classify_google_error(exc)
        logger.warning(
            "incident_draft_metadata_lookup_failed",
            document_id=document_id,
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )

    name, folder = "Incident report", ""
    if isinstance(metadata, dict):
        name = str(metadata.get("name") or name)
        parents = metadata.get("parents") or []
        if parents:
            folder = str(parents[0])
    if not folder:
        logger.warning("incident_draft_parent_folder_not_found", document_id=document_id)
        folder = get_incident_core_settings().folder_id
    return name, folder


def _created_file_id(created: Any) -> str | None:
    """Normalize ``create_file``'s return value (dict or bare id) to an id."""
    if isinstance(created, dict):
        return created.get("id")
    if isinstance(created, str) and created:
        return created
    return None


def _body_content(document: dict) -> list[dict]:
    """Return the document body's structural elements (empty when absent)."""
    body = document.get("body") or {}
    content = body.get("content") or []
    return content if isinstance(content, list) else []


def _is_heading(paragraph: dict) -> bool:
    """Whether a paragraph carries any ``HEADING_*`` named style."""
    return _heading_style(paragraph).startswith("HEADING")


def _is_section_heading(paragraph: dict) -> bool:
    """Whether a paragraph starts a top-level section of the report.

    Only ``HEADING_1``/``HEADING_2`` delimit sections. Deeper headings are
    content *inside* a section -- notably the ``HEADING_3`` sub-headings this
    package writes into Lessons Learned. Treating those as boundaries made a
    re-run see "What went wrong" as its own section, so the Lessons Learned
    span collapsed to nothing, nothing was deleted, and each run stacked
    another copy of the content.

    A heading that is really a labelled value ("Name:", "Other:") is not a
    section either. The template styles several of those as headings, and
    drafting them as sections wrote each value in again underneath itself.
    """
    if _heading_style(paragraph) not in _SECTION_HEADING_STYLES:
        return False
    return not _is_label_heading(_paragraph_text(paragraph))


def _is_label_heading(text: str) -> bool:
    """Whether a heading is a ``Label:`` line rather than a section title."""
    label, separator, _ = text.partition(":")
    if not separator:
        return False
    return _label_key(label) in _KNOWN_LABEL_KEYS


def _label_key(label: str) -> str:
    """Normalise a label for comparison: case, spacing and punctuation."""
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _heading_style(paragraph: dict) -> str:
    """Return a paragraph's named style."""
    return (paragraph.get("paragraphStyle") or {}).get("namedStyleType") or ""


def _paragraph_text(paragraph: dict) -> str:
    """Concatenate a paragraph's text runs."""
    parts = []
    for element in paragraph.get("elements") or []:
        text_run = element.get("textRun") or {}
        parts.append(text_run.get("content") or "")
    return "".join(parts)
