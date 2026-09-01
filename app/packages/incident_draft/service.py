"""Platform-agnostic incident-document drafting logic.

The incident document created at channel creation is a template: each heading
is followed by guidance describing what belongs in that section. This service
reads those heading/guidance pairs through the ``IncidentDocumentPort``, treats
the guidance as per-section drafting instructions, answers each one from the
incident channel transcript via the ``Summarizer`` port
(``integrations.openai``), and writes the answers into a new draft document on
each run (a fresh copy of the incident report template). The incident report
created at channel creation is only ever read, never modified.

This module is deliberately free of Slack, HTTP, and Google SDK imports: it
consumes domain values and Protocols and returns an ``OperationResult`` so any
platform adapter can reuse it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Any, Protocol, runtime_checkable

import structlog

from infrastructure.operations import OperationResult
from integrations.openai import Summarizer, get_summarizer
from packages.incident_draft.domain import (
    AI_AUTHOR,
    DocumentField,
    DocumentSection,
    DraftedDocument,
    DraftWriteResult,
    SectionDraft,
    TranscriptMessage,
)
from packages.incident_draft.settings import get_incident_draft_settings

logger = structlog.get_logger()

DOCUMENT_UNREADABLE_CODE = "DOCUMENT_UNREADABLE"
EMPTY_HISTORY_CODE = "EMPTY_HISTORY"
DRAFT_UNPARSEABLE_CODE = "DRAFT_UNPARSEABLE"
NO_ANSWERS_CODE = "NO_ANSWERS"
CREATE_FAILED_CODE = "CREATE_FAILED"

_DRAFT_INSTRUCTIONS = """\
You are an incident-response scribe filling in an incident report.

## SOURCES
You are given the report's sections -- each a heading followed by the template's
instructions for what belongs under it -- a list of metadata field labels, and the
incident channel's transcript. Every transcript line begins with its timestamp in
square brackets: "[YYYY-MM-DD HH:MM ZZZ] Name: message".
The section instructions tell you WHAT to write. The transcript is your ONLY
source of facts. Never invent a detail, name, time or cause it does not state.

## OUTPUT
Return one JSON object and nothing else. Keys are the section headings exactly as
given, plus every label in the metadata list. Values are plain text -- no
markdown. Use an empty string for anything the transcript does not support: a
blank value is expected and fine, a wrong one is not. Where a value runs to
several lines, separate them with newline characters inside that one string.
Never return an array.

## WRITING
Write in past tense, in complete sentences, factually.
A prose section is 1-4 sentences. That limit does NOT apply to list sections
(timeline, action items, follow-ups, next steps), which run as long as the
transcript supports.
Answer the specific questions a section's instructions ask -- if it asks for
severity and how long impact lasted, give both.
When you mention a pull request, write it as "PR <number>" and nothing else --
never paste its URL beside it. The report turns "PR 1898" into a link on its
own, so a URL in your text only prints the same reference twice.
Omit an unsupported detail rather than writing that it was not stated, not
provided or not confirmed. Do not repeat the instructions back, do not restate a
point in two sentences, and do not close a section by recapping it.

## TIMELINE (any section whose heading refers to a timeline)
This section is a LIST of the incident's significant moments, and it MUST hold
10-15 entries. Returning one entry, or a paragraph, is a failure of the task.
Rank the transcript's messages by how much each changed the incident and write
the top 10-15 as lines, in chronological order. Significant means: the first
alert or detection, confirmation of impact, each diagnostic finding that changed
what the team understood, each decision, each fix attempted and whether it
worked, escalations, customer or status communications, recovery, and
resolution.
List every one of them only if the incident genuinely produced fewer than 10
such moments; a long transcript always produces more.
Merge two messages only when they describe the same moment. Skip greetings,
acknowledgements ("ok", "thanks", "on it"), status pings and routine chatter.
Before you answer, count the lines you have written for this section. If there
are fewer than 10 and the transcript still holds significant messages you left
out, add them until you reach at least 10.
Every line takes this shape, in chronological order:
- YYYY-MM-DD HH:MM ZZZ Name: what happened
Each line MUST open with the full YYYY-MM-DD HH:MM timestamp, copied from the
front of that transcript line exactly as written, including the timezone that
follows it. A bare clock time such as "19:25" is wrong, and a missing date is
wrong.
Worked example -- these transcript lines:
[2026-09-01 19:25 EDT] Jane: pipeline alert just fired
[2026-09-01 19:31 EDT] John: confirmed, checkout is down for everyone
[2026-09-01 19:40 EDT] Jane: rolling back the 19:10 deploy
produce exactly this value:
"- 2026-09-01 19:25 EDT Jane: Pipeline alert fired.\\n- 2026-09-01 19:31 EDT \
John: Confirmed checkout was down for all users.\\n- 2026-09-01 19:40 EDT \
Jane: Rolled back the 19:10 deploy."

## ACTION ITEMS (action items, follow-ups, next steps)
One item per line, each starting with "- ", phrased as a concrete task, naming an
owner when the transcript identifies one. Never a prose paragraph.

## LABELLED GROUPS
When a section's instructions list labelled groups -- Impact's "End-users",
"CDS Staff", "Other government department(s)" and "Other", for example -- answer
each on its own line as "Label: value", using the labels exactly as given, one or
two sentences each. Do not run them together into a paragraph, and do not add a
summary paragraph repeating them.

## BOT ACTIVITY
Channel setup, topic and description changes, severity-warning posts,
hangout/meeting links and "an incident report has been created" notices are
tooling scaffolding, not incident events. Never place them in the timeline, never
describe them as things the team did, and never raise an action item about work a
bot performed automatically -- action items are tasks for people.

## METADATA FIELDS
Fill each label only when the transcript establishes it, otherwise use "".
"Start-of-impact time", "Detection time", "End-of-impact time" take the
YYYY-MM-DD HH:MM timestamp of the message evidencing impact starting, the problem
first being noticed, and impact ending. Never estimate a time no message supports.
"On-call" takes whoever the transcript says was on call or was paged; do not
assume the first person to speak was on call.
"Facilitators" takes anyone the transcript identifies as running or coordinating
the incident or its review.
Names must appear in the transcript.\
"""

# Metadata fields the model is asked to fill from the transcript. Each is left
# blank unless a message actually establishes it -- a wrong on-call name or
# detection time in a retro is worse than an empty line.
_MODEL_FIELD_LABELS = (
    "On-call",
    "Facilitators",
    "Start-of-impact time",
    "Detection time",
    "End-of-impact time",
)
_AUTHORS_FIELD_LABEL = "Author(s)"

# Pull-request links as they appear in Slack messages. The model writes "PR
# 1898" in prose, so the number is mapped back to the URL somebody actually
# posted. Group 1 is the repository, kept so a PR the channel discussed without
# posting its link can still be resolved against that repository.
_PR_URL_PATTERN = re.compile(r"(https?://(?:www\.)?github\.com/[\w.-]+/[\w.-]+)/pull/(\d+)")

# "PR 1898, https://github.com/org/repo/pull/1898" -- the reference and its URL
# printed side by side. The URL is dropped, keeping the short form the document
# hyperlinks; any separator between them ("," ";" "(") goes with it.
_PR_REFERENCE_WITH_URL_PATTERN = re.compile(
    r"\bPR\s*#?(?P<number>\d+)\b[\s,;:-]*[(\[]?\s*"
    r"(?P<url>https?://(?:www\.)?github\.com/[\w.-]+/[\w.-]+/pull/(?P<url_number>\d+))"
    r"(?:\s*[)\]])?",
    re.IGNORECASE,
)

# An explicit pull-request mention in drafted prose: "PR 1898", "PR #1898",
# "pull request 1898". Only these wordings are resolved against the channel's
# repository -- a bare "#123" may be an issue, and a /pull/ URL built for an
# issue number is a broken link.
_PR_MENTION_PATTERN = re.compile(r"\b(?:PRs?|pull requests?)\s*#?(\d+)\b", re.IGNORECASE)

# Sections left for humans: a five-whys chain and a retrospective are
# judgement calls the team makes together, not something to be pre-filled from
# a transcript. They are never sent to the model and never written.
_HUMAN_ONLY_HEADING_MARKERS = (
    "five whys",
    "root cause",
    "lessons learned",
    "retrospective",
)

# Sections that read as lists rather than prose: every line is bulleted, even
# when the model returns them unmarked.
# The stamp every timeline entry must open with, e.g. "2026-09-01 19:25 EDT".
# Used to re-split a timeline the model ran together into one paragraph.
_TIMELINE_STAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?:\s+[A-Z]{2,5})?\b")

_LIST_HEADING_MARKERS = (
    "action item",
    "follow-up",
    "follow up",
    "next step",
    "to-do",
    "todo",
    "timeline",
)


@runtime_checkable
class IncidentDocumentPort(Protocol):
    """Behavior contract for reading the incident document and creating the draft."""

    def read_sections(self, document_id: str) -> list[DocumentSection]:
        """Return the document's sections in document order (empty on failure)."""
        ...

    def write_draft_document(
        self,
        source_document_id: str,
        drafts: Sequence[SectionDraft],
        fields: Sequence[DocumentField],
        links: Mapping[str, str],
    ) -> DraftWriteResult | None:
        """Write the draft document (creating or rewriting it); ``None`` on failure."""
        ...


async def draft_incident_document(
    document_id: str,
    messages: Sequence[TranscriptMessage],
    *,
    documents: IncidentDocumentPort | None = None,
    summarizer: Summarizer | None = None,
) -> OperationResult[DraftedDocument]:
    """Draft a filled-in copy of the incident document from channel history.

    Args:
        document_id: Google Docs id of the source incident document. It is
            only ever read, never modified.
        messages: Chronologically ordered incident-channel messages -- the only
            source of facts for the drafted content.
        documents: Optional ``IncidentDocumentPort``; defaults to the
            Google-Docs-backed adapter from ``providers``. Injected in tests.
        summarizer: Optional ``Summarizer`` port; defaults to the process
            singleton. Injected in tests.

    Returns:
        ``OperationResult`` carrying a ``DraftedDocument`` on success, or a
        classified error: ``DOCUMENT_UNREADABLE`` when the source yields no
        sections, ``EMPTY_HISTORY`` when there is no transcript to draft from,
        ``DRAFT_UNPARSEABLE`` when the model output is not usable JSON,
        ``NO_ANSWERS`` when no section could be answered, ``CREATE_FAILED``
        when the draft document cannot be created, or the summarizer's
        classified error.
    """
    log = logger.bind(
        operation="draft_incident_document",
        document_id=document_id,
        message_count=len(messages),
    )

    if documents is None:
        from packages.incident_draft.providers import get_incident_document_port

        documents = get_incident_document_port()

    sections = [s for s in documents.read_sections(document_id) if not _is_human_only(s.heading)]
    if not sections:
        log.warning("incident_draft_document_unreadable")
        return OperationResult.permanent_error(
            message="Could not read any sections from the incident document",
            error_code=DOCUMENT_UNREADABLE_CODE,
        )

    if not messages:
        log.info("incident_draft_empty_history")
        return OperationResult.permanent_error(
            message="No channel history to draft from",
            error_code=EMPTY_HISTORY_CODE,
        )

    summarizer = summarizer or get_summarizer()
    payload = _build_payload(sections, messages)
    result = await summarizer.summarize(
        payload,
        instructions=_DRAFT_INSTRUCTIONS,
        max_output_tokens=get_incident_draft_settings().MAX_OUTPUT_TOKENS,
    )
    if not result.is_success:
        log.warning(
            "incident_draft_summarizer_failed",
            status=result.status,
            error=result.message,
        )
        return OperationResult.error(
            status=result.status,
            message=result.message,
            error_code=result.error_code,
        )

    raw = result.data or ""
    answers, was_truncated = _parse_answers(raw)
    if answers is not None and was_truncated:
        # Keep what arrived. Discarding it made sense when a run rewrote a
        # long-lived draft, where a fragment would replace good content; every
        # run now writes a fresh document, so a partial draft costs nothing and
        # beats no draft at all. The timeline is the exception -- see below.
        log.warning(
            "incident_draft_truncated_response_salvaged",
            recovered_sections=len(answers),
            section_count=len(sections),
            raw_length=len(raw),
        )
    if answers is None:
        # Log what actually came back -- an empty string, prose instead of
        # JSON, and a response truncated by the token budget all look
        # identical from the error code alone.
        log.warning(
            "incident_draft_unparseable_model_output",
            raw_length=len(raw),
            raw_preview=raw[:400],
        )
        return OperationResult.permanent_error(
            message="The model did not return a parseable JSON draft",
            error_code=DRAFT_UNPARSEABLE_CODE,
        )

    drafts = _build_drafts(sections, answers)
    _log_answer_coverage(log, sections, answers, drafts)
    _log_timeline_shape(log, answers, drafts, raw)
    if not any(draft.is_drafted for draft in drafts):
        log.info("incident_draft_no_answers")
        return OperationResult.permanent_error(
            message="The channel history did not answer any of the document's sections",
            error_code=NO_ANSWERS_CODE,
        )

    fields = _build_fields(answers, messages)
    # Links are resolved before the URLs are collapsed away, so a URL only the
    # model supplied still ends up hyperlinking its "PR <number>".
    links = _resolve_pr_links(messages, drafts)
    drafts = _collapse_pr_references(drafts)
    written = documents.write_draft_document(document_id, drafts, fields, links)
    if written is None:
        log.warning("incident_draft_write_failed", section_count=len(drafts))
        return OperationResult.transient_error(
            message="Failed to write the draft document",
            error_code=CREATE_FAILED_CODE,
        )

    outcome = DraftedDocument(
        document_id=written.document_id,
        created=written.created,
        partial=was_truncated,
        drafted_headings=tuple(d.heading for d in drafts if d.is_drafted),
        unanswered_headings=tuple(d.heading for d in drafts if not d.is_drafted),
    )
    log.info(
        "incident_draft_generated",
        draft_document_id=written.document_id,
        drafted=len(outcome.drafted_headings),
        unanswered=len(outcome.unanswered_headings),
    )
    return OperationResult.success(
        data=outcome,
        provider="openai",
        operation="draft_incident_document",
    )


def _log_timeline_shape(
    log: Any,
    answers: dict[str, str],
    drafts: Sequence[SectionDraft],
    raw: str,
) -> None:
    """Log how many timeline entries the model returned, and what they were.

    A one-entry timeline in the finished document has three possible causes
    that are indistinguishable from the document itself: the model returned one
    entry, it returned many that something here collapsed, or the running
    process is not executing the current prompt. ``model_entries`` versus
    ``written_entries`` separates the first two, and the preview shows which
    prompt the answer was actually shaped by.
    """
    for draft in drafts:
        if "timeline" not in draft.heading.lower() or not draft.is_drafted:
            continue

        answer = _match_answer(draft.heading, answers, {_normalize_heading(k): v for k, v in answers.items()}) or ""
        written = len(draft.content.splitlines())
        log.info(
            "incident_draft_timeline_shape",
            heading=draft.heading,
            model_entries=len(answer.splitlines()),
            written_entries=written,
            model_chars=len(answer),
            raw_preview=raw[:400] if written < 10 else None,
        )


def _log_answer_coverage(
    log: Any,
    sections: Sequence[DocumentSection],
    answers: dict[str, str],
    drafts: Sequence[SectionDraft],
) -> None:
    """Log why any section came out unanswered.

    Distinguishes the three causes that all look identical in the finished
    document: the model omitted the section, it answered under a key matching
    no heading (so the response was probably truncated or the heading drifted),
    or it deliberately returned an empty string.
    """
    matched = {_normalize_heading(s.heading) for s in sections}
    unmatched_keys = [key for key in answers if _normalize_heading(key) not in matched]
    blank_keys = [key for key, value in answers.items() if not value.strip()]
    missing = [d.heading for d in drafts if not d.is_drafted]

    if not missing and not unmatched_keys:
        return

    log.warning(
        "incident_draft_answer_coverage",
        section_count=len(sections),
        answer_count=len(answers),
        unanswered_headings=missing,
        model_keys_matching_no_heading=unmatched_keys,
        model_keys_left_blank=blank_keys,
    )


def _build_payload(
    sections: Sequence[DocumentSection],
    messages: Sequence[TranscriptMessage],
) -> str:
    """Render the sections (heading + instructions) and the transcript."""
    blocks = []
    for section in sections:
        instructions = section.instructions.strip() or "(no instructions given)"
        blocks.append(f"### {section.heading}\nInstructions: {instructions}")
    fields_text = "\n".join(f"- {label}" for label in _MODEL_FIELD_LABELS)
    sections_text = "\n\n".join(blocks)
    transcript = "\n".join(_transcript_line(message) for message in messages)
    return f"Report sections:\n\n{sections_text}\n\nMetadata fields:\n{fields_text}\n\nIncident channel transcript:\n{transcript}"


def _transcript_line(message: TranscriptMessage) -> str:
    """Render one transcript line, prefixed with its time when known."""
    if message.timestamp:
        return f"[{message.timestamp}] {message.author}: {message.text}"
    return f"{message.author}: {message.text}"


def _parse_answers(raw: str) -> tuple[dict[str, str] | None, bool]:
    """Parse the model output into ``(answers, was_truncated)``.

    Models do not reliably emit bare JSON, so parsing is forgiving: it strips
    Markdown code fences and ignores prose wrapped around the object. When the
    object never closes -- the response was cut off by the completion budget --
    the key/value pairs that did arrive are salvaged and ``was_truncated`` is
    ``True``. Callers must not treat a truncated parse as a complete draft:
    the missing sections are an artefact of the cutoff, not the model's
    judgement. ``answers`` is ``None`` only when nothing usable was recovered.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    candidate = _first_json_object(text) or text
    try:
        parsed = json.loads(candidate)
    except TypeError, ValueError:
        parsed = None

    if isinstance(parsed, dict):
        return {str(key): text for key, value in parsed.items() if (text := _coerce_answer(value))}, False

    return _salvage_pairs(text) or None, True


def _coerce_answer(value: object) -> str:
    """Normalise one JSON value into section text, or ``""`` if unusable.

    Asking for "one event per line" reliably tempts a model into answering with
    a JSON array instead of a newline-joined string; the list-shaped sections
    (timeline, action items) are exactly the ones it does this to. Those values
    used to be discarded silently, which read in the document as the model
    having nothing to say. Lists are joined back into lines instead, and dict
    entries (``{"time": ..., "text": ...}``) are flattened in field order.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(line for item in value if (line := _coerce_answer(item).strip()))
    if isinstance(value, dict):
        return " ".join(str(item).strip() for item in value.values() if str(item).strip())
    return ""


def _split_run_on_timeline(content: str) -> str:
    """Break a timeline the model ran together into one entry per line.

    The other way a timeline collapses is a single paragraph holding every
    event, which renders as one bullet containing the whole incident. Every
    entry is required to open with a stamp, so a stamp appearing mid-line marks
    the start of the next entry. Content that is already one-per-line, and
    prose with no stamps at all, pass through untouched.
    """
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        starts = [match.start() for match in _TIMELINE_STAMP_PATTERN.finditer(line)]
        if len(starts) < 2:
            lines.append(line)
            continue

        # Cut before every stamp but the first, so any bullet marker or prose
        # ahead of the opening stamp stays with the entry it introduces. The
        # marker preceding a later stamp is left trailing on the previous
        # slice, and stripped there.
        bounds = [0, *starts[1:], len(line)]
        for begin, end in pairwise(bounds):
            if entry := line[begin:end].strip().rstrip("-*•").strip():
                lines.append(entry)
    return "\n".join(lines)


def _first_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` span, ignoring braces inside strings.

    Lets an object survive prose wrapped around it ("Here is the JSON: {...}").
    Returns ``None`` when no complete object is present (e.g. truncated output).
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            in_string = not in_string
        elif not in_string:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None


def _salvage_pairs(text: str) -> dict[str, str]:
    """Recover complete ``"key": "value"`` pairs from unparseable output.

    A response truncated mid-object still carries every section the model
    finished writing; recovering those turns a total failure into a partial
    draft, with the unfinished sections falling back to their template
    instructions.
    """
    pairs: dict[str, str] = {}
    pattern = re.compile(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"')
    for raw_key, raw_value in pattern.findall(text):
        try:
            key = json.loads(f'"{raw_key}"')
            value = json.loads(f'"{raw_value}"')
        except ValueError:
            continue
        pairs[key] = value
    return pairs


def _build_drafts(
    sections: Sequence[DocumentSection],
    answers: dict[str, str],
) -> list[SectionDraft]:
    """Pair every section with its drafted content, in document order.

    A section the transcript could not answer keeps the source document's
    original instructions so the draft still tells a human what is needed.
    """
    lookup = {_normalize_heading(key): value for key, value in answers.items()}

    drafts: list[SectionDraft] = []
    for section in sections:
        answer = _match_answer(section.heading, answers, lookup)
        if answer and "timeline" in section.heading.lower():
            answer = _split_run_on_timeline(answer)
        drafts.append(
            SectionDraft(
                heading=section.heading,
                content=answer or section.instructions.strip(),
                is_drafted=bool(answer),
                as_list=_is_list_heading(section.heading),
            )
        )
    return drafts


def _match_answer(heading: str, answers: dict[str, str], lookup: dict[str, str]) -> str:
    """Find the model's answer for ``heading``, tolerating key drift.

    Models rarely echo a heading byte-for-byte: they drop numbering, change
    case, or add punctuation. An exact-only lookup turns that into a silently
    blank section, so fall back to a normalized comparison.
    """
    exact = (answers.get(heading) or "").strip()
    if exact:
        return exact
    return (lookup.get(_normalize_heading(heading)) or "").strip()


def _normalize_heading(text: str) -> str:
    """Reduce a heading to a comparable form: no numbering, case or punctuation."""
    without_numbering = re.sub(r"^\s*\d+\s*[.)\-:]\s*", "", text)
    alphanumeric = re.sub(r"[^a-z0-9 ]+", " ", without_numbering.lower())
    return re.sub(r"\s+", " ", alphanumeric).strip()


def _build_fields(answers: dict[str, str], messages: Sequence[TranscriptMessage]) -> list[DocumentField]:
    """Build the metadata values to write into the report's header block.

    The model fills what the transcript evidences -- on-call, facilitators and
    the impact/detection times. The author is always the bot: a reader needs to
    know the draft was machine-written, and the responders who spoke in the
    channel did not author this document. Fields the model left empty are
    omitted entirely, so an unestablished field keeps the template's blank line
    rather than acquiring a guess.
    """
    fields: list[DocumentField] = []
    for label in _MODEL_FIELD_LABELS:
        value = _match_answer(label, answers, {_normalize_heading(k): v for k, v in answers.items()})
        if value:
            fields.append(DocumentField(label=label, value=value))

    fields.append(DocumentField(label=_AUTHORS_FIELD_LABEL, value=AI_AUTHOR))
    return fields


def _extract_pr_links(messages: Sequence[TranscriptMessage]) -> dict[str, str]:
    """Map pull-request numbers to the URLs posted in the channel.

    Slack wraps links as ``<url|label>``; the pattern stops at the PR number so
    the label never leaks into the URL. The first link posted for a number
    wins.
    """
    links: dict[str, str] = {}
    for message in messages:
        for match in _PR_URL_PATTERN.finditer(message.text):
            links.setdefault(match.group(2), match.group(0))
    return links


def _channel_repository(messages: Sequence[TranscriptMessage]) -> str | None:
    """Return the repository the channel's pull-request links point at.

    ``None`` when the channel referenced more than one repository, because a
    number could then belong to either and a wrong link is worse than none.
    """
    repositories = {match.group(1) for message in messages for match in _PR_URL_PATTERN.finditer(message.text)}
    return repositories.pop() if len(repositories) == 1 else None


def _resolve_pr_links(
    messages: Sequence[TranscriptMessage],
    drafts: Sequence[SectionDraft],
) -> dict[str, str]:
    """Map every pull request the draft cites to a URL.

    A reference is linkable when the channel posted its URL, or when the model
    wrote the URL into the draft itself -- that one is harvested here because
    the draft's copy is about to be collapsed to "PR <number>", and it would
    otherwise be the only record of where the PR lives. Failing both, but with
    every pull-request link in the channel belonging to one repository, the URL
    is built from that repository and the cited number: a report that names a PR
    without linking it makes the reader search for it by hand.
    """
    links = _extract_pr_links(messages)
    for draft in drafts:
        for match in _PR_URL_PATTERN.finditer(draft.content):
            links.setdefault(match.group(2), match.group(0))

    repository = _channel_repository(messages)
    if repository is None:
        return links

    for draft in drafts:
        for match in _PR_MENTION_PATTERN.finditer(draft.content):
            links.setdefault(match.group(1), f"{repository}/pull/{match.group(1)}")
    return links


def _collapse_pr_references(drafts: Sequence[SectionDraft]) -> list[SectionDraft]:
    """Reduce every pull-request mention to a single "PR <number>".

    The model is told to write the short form alone, but it still pastes the URL
    beside it often enough to matter: "Opened PR 1898,
    https://github.com/org/repo/pull/1898, to add error handling" prints the
    same reference twice, once as a link and once as raw URL text. The short
    form is kept because the document hyperlinks it, so dropping the URL loses
    nothing. A URL standing on its own becomes "PR <number>" for the same
    reason -- it is the only mention, and it reads better short.
    """
    collapsed: list[SectionDraft] = []
    for draft in drafts:
        if not draft.is_drafted:
            collapsed.append(draft)
            continue

        content = _PR_REFERENCE_WITH_URL_PATTERN.sub(_drop_duplicate_url, draft.content)
        content = _PR_URL_PATTERN.sub(lambda match: f"PR {match.group(2)}", content)
        collapsed.append(replace(draft, content=_tidy_spacing(content)))
    return collapsed


def _drop_duplicate_url(match: re.Match[str]) -> str:
    """Keep "PR <number>", dropping the URL only when it names that same PR."""
    if match.group("number") != match.group("url_number"):
        # Two different pull requests side by side; neither is redundant, so
        # only the URL is shortened.
        return f"PR {match.group('number')}, PR {match.group('url_number')}"
    return f"PR {match.group('number')}"


def _tidy_spacing(text: str) -> str:
    """Repair the spacing a removed URL leaves behind."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.;:])", r"\1", text)
    return re.sub(r"\(\s*\)", "", text).strip()


def _is_human_only(heading: str) -> bool:
    """Whether a section is left for the team rather than drafted."""
    lowered = heading.lower()
    return any(marker in lowered for marker in _HUMAN_ONLY_HEADING_MARKERS)


def _is_list_heading(heading: str) -> bool:
    """Whether a section's content should render as a bulleted list."""
    lowered = heading.lower()
    return any(marker in lowered for marker in _LIST_HEADING_MARKERS)
