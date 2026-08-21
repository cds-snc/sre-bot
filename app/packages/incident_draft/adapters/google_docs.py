"""Google-backed adapter for the ``IncidentDocumentPort``.

Owns every Google structural detail: walking the source document body to turn
heading-styled paragraphs into ``DocumentSection`` values (the heading plus the
template guidance written under it), and writing the draft document -- in the
source document's Drive folder -- populated with the drafted sections. The
draft is reused across runs: an existing one is cleared and rebuilt so repeated
invocations leave a single document. The source incident report is only ever
read; the sole content-removing operation here is guarded to fire only on a
document whose title matches the expected draft.

Per ``decisions/feature-packages.md`` this is the only place in the package
allowed to import ``integrations``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import structlog

from infrastructure.configuration.integrations.google import get_google_resources_config
from integrations.google_workspace import google_docs, google_drive
from packages.incident_draft.domain import DocumentField, DocumentSection, DraftWriteResult, SectionDraft

logger = structlog.get_logger()

_DRAFT_TITLE_SUFFIX = " - AI draft"
_SUBHEADING_STYLE = "HEADING_3"
# Only these delimit sections; deeper headings are content within one.
_SECTION_HEADING_STYLES = frozenset({"HEADING_1", "HEADING_2"})
_BANNER_PREFIX = "AI draft · generated"
# Generated content is wrapped in named ranges under this prefix so a re-run can
# find and replace exactly what it wrote, leaving the template untouched.
_NAMED_RANGE_PREFIX = "incident_draft::"
# Metadata labels the template renders as bold headings, which makes them loom
# over the content beneath. They are normalised to ordinary body text instead.
# Some live in the preamble, others inside the Impact section, so they are
# matched by label wherever they appear.
_REGULAR_LABEL_FONT_PT = 11
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

# Line kinds produced by _render_body_lines.
_SUBHEADING = "subheading"
_BULLET = "bullet"
_QUESTION = "question"
_ANSWER = "answer"
_TEXT = "text"

# Retrospective groupings that render as sub-headings with bullets beneath.
_SUBHEADING_LABELS = frozenset(
    {
        "what went wrong",
        "what went well",
        "where we got lucky",
        "what could be improved",
        "what could have gone better",
    }
)
_TIMELINE_HEADING_MARKER = "timeline"
# The heading that closes the timeline section in the incident template.
_TIMELINE_END_MARKER = "Trigger"
# modules.incident locates the timeline by this exact line; it must survive.
_SENTINEL_LINE = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."


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

    def replace_timeline(self, document_id: str, entries: str) -> bool:
        """Replace the incident report's timeline entries with ``entries``.

        This is the only write this package makes to the incident report
        itself. It replaces the whole timeline section -- the template's
        warning banner, its explanatory paragraph, and any existing entries --
        with the sentinel line plus the drafted timeline. The sentinel is
        re-inserted verbatim so reaction-driven timeline updates in
        ``modules.incident`` keep working, and every other section of the
        report is untouched. Returns ``False`` (writing nothing) when the
        document has no timeline section or cannot be read.
        """
        if not entries.strip():
            return False

        document = google_docs.get_document(document_id)
        if not isinstance(document, dict):
            logger.warning("incident_draft_timeline_fetch_failed", document_id=document_id)
            return False

        region = _timeline_region(document)
        if region is None:
            logger.warning("incident_draft_timeline_section_not_found", document_id=document_id)
            return False

        start, end = region
        requests: list[dict[str, Any]] = []
        if end > start:
            requests.append({"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}})
        requests.extend(_render_timeline_requests(start, entries))

        result = google_docs.batch_update(document_id, requests)
        if not isinstance(result, dict):
            logger.warning("incident_draft_timeline_update_failed", document_id=document_id)
            return False

        logger.info("incident_draft_timeline_replaced", document_id=document_id, start=start, end=end)
        return True

    def write_draft_document(
        self,
        source_document_id: str,
        drafts: Sequence[SectionDraft],
        fields: Sequence[DocumentField] = (),
    ) -> DraftWriteResult | None:
        """Write the draft as a filled-in copy of the incident report.

        The draft is a Drive copy of the source document, so it keeps the
        template's exact formatting -- the metadata block, the blameless
        statement, each section's italic guidance, and the Action Items table.
        Only the bodies of sections the transcript answered are replaced;
        unanswered sections keep the template's guidance untouched, which is
        both simpler and more faithful than rebuilding the layout in code.

        A re-run refills the same document rather than creating another.
        Returns ``None`` on any failure; the source report is never written to.
        """
        if not drafts and not fields:
            return None

        title = _source_title(source_document_id)
        if title is None:
            return None

        draft_title = f"{title}{_DRAFT_TITLE_SUFFIX}"
        folder = _source_folder(source_document_id)

        existing_id = _find_existing_draft(draft_title, folder, source_document_id)
        document_id = existing_id or _copy_source_document(source_document_id, draft_title, folder)
        if not document_id:
            return None

        document = google_docs.get_document(document_id)
        if not isinstance(document, dict):
            logger.warning("incident_draft_draft_fetch_failed", document_id=document_id)
            return None

        requests = _fill_section_requests(document, drafts, fields)
        if not requests:
            logger.warning("incident_draft_no_sections_filled", document_id=document_id)
            return None

        result = google_docs.batch_update(document_id, requests)
        if not isinstance(result, dict):
            logger.warning("incident_draft_populate_failed", document_id=document_id)
            return None

        _normalize_label_styling(document_id)

        logger.info(
            "incident_draft_document_written",
            document_id=document_id,
            created=existing_id is None,
            filled_sections=sum(1 for d in drafts if d.is_drafted),
        )
        return DraftWriteResult(document_id=document_id, created=existing_id is None)


def _normalize_label_styling(document_id: str) -> None:
    """Render the report's metadata labels as ordinary body text.

    Deliberately a separate ``batchUpdate`` on a freshly fetched document:
    styling ranges are computed from indices, and running them alongside the
    content edits would mean reasoning about how every insert and delete shifts
    them. Re-reading first makes the indices exact. Purely cosmetic, so a
    failure is logged and swallowed rather than failing the draft.
    """
    document = google_docs.get_document(document_id)
    if not isinstance(document, dict):
        logger.warning("incident_draft_label_style_fetch_failed", document_id=document_id)
        return

    requests = _regular_label_requests(document)
    if not requests:
        return

    if not isinstance(google_docs.batch_update(document_id, requests), dict):
        logger.warning("incident_draft_label_styling_failed", document_id=document_id)


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
        if not separator or label.strip().lower() not in _REGULAR_TEXT_LABELS:
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
    copied = google_drive.create_file_from_template(draft_title, folder, source_document_id, fields="id")
    document_id = _created_file_id(copied)
    if not document_id:
        logger.warning("incident_draft_copy_failed", source_document_id=source_document_id)
        return None
    return document_id


def _fill_section_requests(
    document: dict,
    drafts: Sequence[SectionDraft],
    fields: Sequence[DocumentField] = (),
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
    if not answered and not fillable_fields:
        return []

    placements: list[tuple[str, int, list[tuple[str, str]]]] = []
    for draft in answered:
        placements.extend(_placements_for(document, draft, spans[draft.heading], generated))

    requests: list[dict[str, Any]] = []
    for name, insert_at, lines in sorted(placements, key=lambda p: p[1], reverse=True):
        previous = generated.get(name, [])
        if previous:
            # Drop the marker before its content so the name is free to reuse.
            requests.append({"deleteNamedRange": {"name": name}})
            for start, end in sorted(previous, reverse=True):
                requests.append({"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}})

        builder = _RequestBuilder(start_index=insert_at)
        for text, kind in lines:
            if kind == _SUBHEADING:
                builder.insert(f"{text}\n", named_style=_SUBHEADING_STYLE)
                continue
            builder.insert(
                f"{text}\n",
                named_style="NORMAL_TEXT",
                bullet=kind == _BULLET,
                bold=kind == _QUESTION,
                indent_pt=18 if kind == _ANSWER else 0,
            )
        requests.extend(builder.build())

        if builder.end_index > insert_at:
            requests.append(
                {
                    "createNamedRange": {
                        "name": name,
                        "range": {"startIndex": insert_at, "endIndex": builder.end_index},
                    }
                }
            )

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
) -> list[tuple[str, int, list[tuple[str, str]]]]:
    """Split a draft into ``(range name, insert index, lines)`` placements.

    Groups whose label the template already prints are placed under it, sans
    the duplicate label. Everything else forms one placement at the end of the
    section.
    """
    lines = _render_body_lines(draft.content, force_bullets=draft.as_list)
    template_labels = _sub_label_indices(document, span)

    placements: list[tuple[str, int, list[tuple[str, str]]]] = []
    remainder: list[tuple[str, str]] = []

    for label, group in _group_by_subheading(lines):
        key = label.rstrip(":").strip().lower() if label else ""
        if key and key in template_labels:
            name = f"{_NAMED_RANGE_PREFIX}{draft.heading}::{key}"
            placements.append((name, _placement_index(name, template_labels[key], generated), group))
            continue
        if label:
            remainder.append((label, _SUBHEADING))
        remainder.extend(group)

    if remainder:
        name = f"{_NAMED_RANGE_PREFIX}{draft.heading}"
        placements.append((name, _placement_index(name, span[1], generated), remainder))
    return placements


def _group_by_subheading(lines: list[tuple[str, str]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split classified lines into ``(subheading, following lines)`` groups."""
    groups: list[tuple[str, list[tuple[str, str]]]] = [("", [])]
    for text, kind in lines:
        if kind == _SUBHEADING:
            groups.append((text, []))
            continue
        groups[-1][1].append((text, kind))
    return [(label, group) for label, group in groups if label or group]


def _sub_label_indices(document: dict, span: tuple[int, int]) -> dict[str, int]:
    """Map the template's sub-labels inside a section to their insert points.

    The insert point is just after the label's own paragraph, so generated
    points sit directly beneath the label the template already prints.
    """
    start, end = span
    labels: dict[str, int] = {}
    for element in _body_content(document):
        element_start, element_end = element.get("startIndex"), element.get("endIndex")
        if not isinstance(element_start, int) or not isinstance(element_end, int):
            continue
        if element_start < start or element_end > end:
            continue
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        key = _paragraph_text(paragraph).strip().rstrip(":").strip().lower()
        if key in _SUBHEADING_LABELS and key not in labels:
            labels[key] = element_end
    return labels


def _placement_index(name: str, default: int, generated: dict[str, list[tuple[int, int]]]) -> int:
    """Where a placement belongs: over the last run's span, else ``default``."""
    previous = generated.get(name)
    if previous:
        return min(start for start, _ in previous)
    return default


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

    Only the preamble above the first heading is scanned -- that is where the
    report's ``Label: value`` block lives, and a colon further down the
    document is ordinary prose. The span covers the text after the colon up to
    (but not including) the paragraph's newline, so filling a field rewrites
    only its value.
    """
    spans: dict[str, tuple[int, int]] = {}
    for element in _body_content(document):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        if _is_heading(paragraph) and text.strip():
            break  # the metadata block ends at the first heading

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


def _timeline_region(document: dict) -> tuple[int, int] | None:
    """Locate the replaceable span of the incident report's timeline section.

    Returns ``(start, end)`` spanning everything between the timeline heading
    and the section that follows it -- the template's warning banner and
    explanatory paragraph included, since those are boilerplate the drafted
    timeline replaces. The sentinel line is deleted along with them and then
    re-inserted by ``_render_timeline_requests``, so it survives every rewrite
    while the surrounding clutter does not.

    The section's end is the next heading, or a paragraph reading ``Trigger``
    -- matching how ``modules.incident`` finds the same boundary, which is
    robust to templates where ``Trigger`` is not styled as a real heading.

    Returns ``None`` when the timeline heading or its closing boundary cannot
    be found, in which case nothing is written at all. Refusing to guess the
    end matters: falling back to the document end would delete every remaining
    section.
    """
    start: int | None = None
    fallback: int | None = None

    for element in _body_content(document):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph).strip()
        element_start = element.get("startIndex")
        element_end = element.get("endIndex")

        if start is None:
            if _is_section_heading(paragraph) and text and _TIMELINE_HEADING_MARKER in text.lower():
                start = element_end if isinstance(element_end, int) else None
            continue

        if not isinstance(element_start, int):
            continue
        if _is_section_heading(paragraph) and text:
            # A real section heading is the authoritative boundary.
            return (start, max(start, element_start))
        if text.startswith(_TIMELINE_END_MARKER):
            # Fallback for templates where "Trigger" is plain text. Recorded
            # rather than returned so a later real heading still wins -- a
            # stray "Trigger" line inside the section must not truncate the
            # replacement and leave duplicated entries behind.
            fallback = fallback or max(start, element_start)

    if start is not None and fallback is not None:
        return (start, fallback)
    return None


def _render_timeline_requests(start: int, entries: str) -> list[dict[str, Any]]:
    """Build the insert/style requests writing the timeline section at ``start``.

    Re-inserts the sentinel line the delete removed -- muted and italic, since
    it is machinery rather than content -- followed by the drafted entries as
    bullets.
    """
    builder = _RequestBuilder(start_index=start)
    builder.insert(f"{_SENTINEL_LINE}\n", named_style="NORMAL_TEXT", italic=True, muted=True)
    for text, kind in _render_body_lines(entries, force_bullets=True):
        if kind == _SUBHEADING:
            builder.insert(f"{text}\n", named_style=_SUBHEADING_STYLE)
            continue
        builder.insert(f"{text}\n", named_style="NORMAL_TEXT", bullet=kind == _BULLET)
    return builder.build()


def _find_existing_draft(draft_title: str, folder: str, source_document_id: str) -> str | None:
    """Return the id of this incident's existing draft document, if any.

    Looks only for an exact title match inside the incident's own folder, and
    refuses to return the source document's id -- that value goes on to be
    cleared, so it must never point at the incident report.
    """
    matches = google_drive.find_files_by_name(draft_title, folder)
    if not isinstance(matches, list):
        return None

    for match in matches:
        if not isinstance(match, dict):
            continue
        file_id = match.get("id")
        if not file_id or file_id == source_document_id:
            continue
        if match.get("name") != draft_title:
            continue
        return str(file_id)
    return None


class _RequestBuilder:
    """Accumulates ``batchUpdate`` requests while tracking the running index."""

    def __init__(self, start_index: int = 1) -> None:
        self._requests: list[dict[str, Any]] = []
        self._bullets: list[tuple[int, int]] = []
        self._index = start_index

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

        if text.endswith("?"):
            lines.append((text, _QUESTION))
            continue

        # A line directly under a question is that question's answer.
        if lines and lines[-1][1] == _QUESTION:
            lines.append((text, _ANSWER))
            continue

        lines.append((text, _BULLET if force_bullets else _TEXT))
    return lines or [("", _TEXT)]


def _is_subheading(text: str) -> bool:
    """Whether an unbulleted line introduces a group of points."""
    stripped = text.rstrip(":").strip().lower()
    if stripped in _SUBHEADING_LABELS:
        return True
    # "What went well:" style — a short trailing-colon label, not a sentence
    # that merely happens to contain a colon.
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


def _source_title(document_id: str) -> str | None:
    """Return the source document's title, or ``None`` when unreadable."""
    document = google_docs.get_document(document_id)
    if not isinstance(document, dict):
        logger.warning("incident_draft_document_fetch_failed", document_id=document_id)
        return None
    return document.get("title") or "Incident report"


def _source_folder(document_id: str) -> str:
    """Return the source document's parent folder id.

    Falls back to the configured incident folder when the Drive metadata
    lookup fails, so the draft still lands somewhere responders can find.
    """
    metadata = google_drive.get_file_by_id(document_id, fields="id, name, parents")
    if isinstance(metadata, dict):
        parents = metadata.get("parents") or []
        if parents:
            return str(parents[0])
    logger.warning("incident_draft_parent_folder_not_found", document_id=document_id)
    return get_google_resources_config().incident_folder_id


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
    """
    return _heading_style(paragraph) in _SECTION_HEADING_STYLES


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
