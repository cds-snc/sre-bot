"""Google-backed adapter for the ``IncidentDocumentPort``.

Owns every Google structural detail: walking the source document body to turn
heading-styled paragraphs into ``DocumentSection`` values (the heading plus the
template guidance written under it), and writing the draft document -- in the
source document's Drive folder -- populated with the drafted sections. Each run
creates a fresh Drive copy of the source document, so repeated invocations
produce new draft documents rather than rewriting one in place. The source
incident report is only ever read; the sole content-removing operation here is guarded to fire only on a

Per ``decisions/feature-packages.md`` this is the only place in the package
allowed to import ``integrations``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from googleapiclient.errors import HttpError

from infrastructure.configuration.integrations.google import get_google_resources_config
from integrations.google_workspace import client as google_workspace_client
from integrations.google_workspace import google_docs, google_drive
from packages.incident_draft.domain import (
    DocumentField,
    DocumentSection,
    DraftWriteResult,
    SectionDraft,
)

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()

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


class GoogleDocsIncidentDocument:
    """``IncidentDocumentPort`` implementation backed by Google Docs and Drive."""

    def read_sections(self, document_id: str) -> list[DocumentSection]:
        """Return the document's heading-delimited sections in document order.

        A paragraph styled ``HEADING_*`` starts a new section; every following
        paragraph's text accumulates as that section's instructions until the
        next heading. Text before the first heading is ignored (template
        boilerplate: title, status, metadata table). Returns an empty list when
        the document cannot be fetched.
        """
        document = google_docs.get_document(document_id)
        if not isinstance(document, dict):
            logger.warning("incident_draft_document_fetch_failed", document_id=document_id)
            return []

        sections: list[DocumentSection] = []
        heading: str | None = None
        instruction_parts: list[str] = []

        for element in _body_content(document):
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
        return sections

    def write_draft_document(
        self,
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

        document = google_docs.get_document(document_id)
        if not isinstance(document, dict):
            logger.warning("incident_draft_draft_fetch_failed", document_id=document_id)
            return None

        requests = _fill_section_requests(document, drafts, fields, links)
        if not requests:
            logger.warning("incident_draft_no_sections_filled", document_id=document_id)
            return None

        result = google_docs.batch_update(document_id, requests)
        if not isinstance(result, dict):
            logger.warning("incident_draft_populate_failed", document_id=document_id)
            return None

        logger.info(
            "incident_draft_document_written",
            document_id=document_id,
            filled_sections=sum(1 for d in drafts if d.is_drafted),
        )
        return DraftWriteResult(document_id=document_id, created=True)


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
    service = google_workspace_client.get_drive_service(scopes=google_drive.DRIVE_SCOPES)
    body = cast("File", {"name": draft_title, "parents": [folder]})
    try:
        copied = (
            service.files().copy(fileId=source_document_id, body=body, supportsAllDrives=True, fields="id").execute()
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
                        "range": {"startIndex": insert_at, "endIndex": insert_at + len(inline_text)},
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
            value_start = element_start + len(label) + 1
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

        value_start = element_start + len(label) + 1
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
            value_start = start_index + len(text.split(":", 1)[0]) + 1
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
        start, end = self._index, self._index + len(text)
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
                    "range": {"startIndex": start + match.start(), "endIndex": start + match.end()},
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
    service = google_workspace_client.get_drive_service(scopes=google_drive.DRIVE_SCOPES)
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
        folder = get_google_resources_config().incident_folder_id
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
