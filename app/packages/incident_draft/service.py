"""Platform-agnostic incident-document drafting logic.

The incident document created at channel creation is a template: each heading
is followed by guidance describing what belongs in that section. This service
reads those heading/guidance pairs through the ``IncidentDocumentPort``, treats
the guidance as per-section drafting instructions, answers each one from the
incident channel transcript via the ``Summarizer`` port
(``integrations.openai``), and writes the answers into this incident's draft
document -- created on the first run and rewritten in place on later ones, so
repeated invocations leave a single draft. The one exception is the incident
report's own timeline section: the drafted timeline is written back there,
replacing the entries beneath the bot's generated-timeline marker.

This module is deliberately free of Slack, HTTP, and Google SDK imports: it
consumes domain values and Protocols and returns an ``OperationResult`` so any
platform adapter can reuse it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import structlog

from infrastructure.operations import OperationResult
from integrations.openai import Summarizer, get_summarizer
from packages.incident_draft.domain import (
    AI_AUTHOR,
    NOT_INDICATED,
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
TRUNCATED_CODE = "TRUNCATED"
CREATE_FAILED_CODE = "CREATE_FAILED"

_DRAFT_INSTRUCTIONS = (
    "You are an incident-response scribe filling in an incident report. You "
    "are given the report's sections -- each a heading followed by the "
    "template's instructions for what belongs under it -- and the chat "
    "transcript of the incident channel. For every heading, follow that "
    "section's instructions and write the section's content using ONLY facts "
    "stated in the transcript. The instructions tell you what to write; the "
    "transcript is your only source of facts. Be concise and factual, in "
    "complete sentences and past tense; 1-4 sentences per section unless its "
    "instructions ask for a list. Never invent details, names, times, or "
    "causes that are not in the transcript. Do not repeat the instructions "
    "back. Answer the specific questions a section's instructions ask -- if it "
    "asks for severity and how long impact lasted, give them. Never write "
    "about what the transcript does not contain: omit an unsupported detail "
    "instead of writing that it was not stated, not provided, or not "
    "confirmed. Do not restate the same point in two sentences, and do not add "
    "a closing sentence that recaps what you just wrote. "
    "Respond with a single JSON object and nothing else: keys are the "
    "section headings EXACTLY as given, values are the section's content as "
    "plain text (no markdown). Use an empty string for any section the "
    "transcript does not support. For a section whose heading refers to a "
    "timeline, instead write one event per line, each line starting with "
    "'- ' and formatted 'HH:MM Name: what happened', in chronological order, "
    "using the timestamps given in the transcript. Be highly selective: a "
    "timeline is a short record of moments that changed the incident, NOT a "
    "log of the conversation. Include only events such as first detection or "
    "alert, confirmation of impact, key diagnostic findings, decisions taken, "
    "mitigation and rollback actions, recovery, and resolution. Exclude "
    "greetings, acknowledgements ('ok', 'thanks', 'on it'), speculation that "
    "led nowhere, status pings, and routine chatter. Prefer roughly 5-12 "
    "entries for a typical incident; merge closely related messages into one "
    "entry rather than listing each message. For a retrospective section "
    "(lessons learned), organise the content under the sub-headings 'What "
    "went wrong', 'What went well' and 'Where we got lucky': write each "
    "sub-heading on its own line ending with a colon, followed by its points "
    "one per line each starting with '- '. Include all three sub-headings even "
    "when the transcript supports nothing for one: give it the single point "
    f"'- {NOT_INDICATED}' rather than leaving it out. For a "
    "section about action items, follow-ups or next steps, write one item per "
    "line, each starting with '- ', phrased as a concrete task and naming an "
    "owner when the transcript identifies one -- never as a prose paragraph. "
    "When a section's instructions list labelled groups -- Impact's "
    "'End-users', 'CDS Staff', 'Other government department(s)' and 'Other', "
    "for example -- answer each on its own line as 'Label: value', using the "
    "labels exactly as given and keeping each to one or two sentences. Do not "
    "run them together into a paragraph, and do not add a separate summary "
    "paragraph repeating them. "
    "For a five-whys or root-cause section, write it as question-and-answer "
    "pairs: each question on its own line ending with '?', its answer on the "
    "very next line, with a blank line between pairs and no bullet markers. "
    "For five whys, always write exactly five pairs: start from the "
    "user-visible failure and let each question ask why the previous answer "
    "happened, drilling from symptom through mechanism to the underlying "
    "process or design gap. Do not stop early. Where the transcript stops "
    "supporting the chain, keep asking the next why and answer it with what "
    "the evidence does allow -- name the gap plainly (for example 'No check "
    "caught the removed configuration before it shipped') rather than "
    "inventing a specific cause or writing that the transcript is silent. "
    "Then state the root cause on its own line after the fifth pair. "
    "Ignore automated bot activity "
    "entirely: channel setup, topic or description changes, severity-warning "
    "posts, hangout/meeting links, and 'an incident report has been created' "
    "notices are tooling scaffolding, not incident events. Never list them in "
    "the timeline, never describe them as things the team did, and never "
    "create an action item about work a bot performed automatically -- action "
    "items are tasks for people. You are also given a 'Metadata fields' list; "
    "include each of those labels as a key too. Fill each one only when the "
    "transcript establishes it, and use an empty string otherwise -- a blank "
    "field is expected and fine, a wrong one is not. Times "
    "('Start-of-impact time', 'Detection time', 'End-of-impact time') take the "
    "'YYYY-MM-DD HH:MM' timestamp of the message that evidences impact "
    "starting, the problem first being noticed, and impact ending; never "
    "estimate a time no message supports. 'On-call' takes the name of whoever "
    "the transcript says was on call or was paged; do not assume the first "
    "person to speak was on call. 'Facilitators' takes the name of anyone the "
    "transcript identifies as running or coordinating the incident or its "
    "review. Names must appear in the transcript."
)

# Headings matching this are written back into the incident report itself,
# not just the draft document.
_TIMELINE_HEADING_MARKER = "timeline"

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

# Five-whys sections are capped at this many questions. The prompt asks for
# exactly five; this enforces it, since a prompt is a request and not a
# guarantee.
# Pull-request links as they appear in Slack messages. The model writes "PR
# 1898" in prose, so the number is mapped back to the URL somebody actually
# posted -- inferring a repository from a bare number would be a guess.
_PR_URL_PATTERN = re.compile(r"https?://(?:www\.)?github\.com/[\w.-]+/[\w.-]+/pull/(\d+)")

_MAX_WHYS = 5
_FIVE_WHYS_MARKERS = ("five whys", "root cause")

# Sections that read as lists rather than prose: every line is bulleted, even
# when the model returns them unmarked.
_LIST_HEADING_MARKERS = (
    "lessons learned",
    "retrospective",
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

    def replace_timeline(self, document_id: str, entries: str, links: Mapping[str, str]) -> bool:
        """Replace the incident report's timeline entries; ``True`` on success."""
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

    sections = documents.read_sections(document_id)
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
    if not any(draft.is_drafted for draft in drafts):
        log.info("incident_draft_no_answers")
        return OperationResult.permanent_error(
            message="The channel history did not answer any of the document's sections",
            error_code=NO_ANSWERS_CODE,
        )

    fields = _build_fields(answers, messages)
    links = _extract_pr_links(messages)
    written = documents.write_draft_document(document_id, drafts, fields, links)
    if written is None:
        log.warning("incident_draft_write_failed", section_count=len(drafts))
        return OperationResult.transient_error(
            message="Failed to write the draft document",
            error_code=CREATE_FAILED_CODE,
        )

    # The timeline is the one section written back into the incident report
    # itself; everything else stays in the draft document.
    timeline_updated = False
    timeline = _find_timeline_draft(drafts)
    if timeline is not None and was_truncated:
        # The timeline overwrites curated entries in the real report, so a
        # chain that may itself have been cut short must not be written there.
        log.warning("incident_draft_timeline_skipped_after_truncation", heading=timeline.heading)
    elif timeline is not None:
        timeline_updated = documents.replace_timeline(document_id, timeline.content, links)
        if not timeline_updated:
            log.warning("incident_draft_timeline_not_updated", heading=timeline.heading)

    outcome = DraftedDocument(
        document_id=written.document_id,
        created=written.created,
        partial=was_truncated,
        drafted_headings=tuple(d.heading for d in drafts if d.is_drafted),
        unanswered_headings=tuple(d.heading for d in drafts if not d.is_drafted),
        timeline_updated=timeline_updated,
    )
    log.info(
        "incident_draft_generated",
        draft_document_id=written.document_id,
        created=written.created,
        drafted=len(outcome.drafted_headings),
        unanswered=len(outcome.unanswered_headings),
        timeline_updated=timeline_updated,
    )
    return OperationResult.success(
        data=outcome,
        provider="openai",
        operation="draft_incident_document",
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


def _find_timeline_draft(drafts: Sequence[SectionDraft]) -> SectionDraft | None:
    """Return the drafted timeline section, if the document has one."""
    for draft in drafts:
        if draft.is_drafted and _TIMELINE_HEADING_MARKER in draft.heading.lower():
            return draft
    return None


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
        return {str(key): str(value) for key, value in parsed.items() if isinstance(value, str)}, False

    return _salvage_pairs(text) or None, True


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
        content = answer or section.instructions.strip()
        is_chain = _is_five_whys_heading(section.heading)
        if answer and is_chain:
            content = _cap_questions(content, _MAX_WHYS, section.heading)
        drafts.append(
            SectionDraft(
                heading=section.heading,
                content=content,
                is_drafted=bool(answer),
                as_list=_is_list_heading(section.heading),
                is_question_chain=is_chain,
            )
        )
    return drafts


def _is_five_whys_heading(heading: str) -> bool:
    """Whether a section holds a five-whys chain."""
    lowered = heading.lower()
    return any(marker in lowered for marker in _FIVE_WHYS_MARKERS)


def _cap_questions(content: str, limit: int, heading: str) -> str:
    """Drop question-and-answer pairs beyond ``limit``.

    Only the surplus pairs are removed: a trailing root-cause statement, which
    is not part of the chain, survives. Answers are recognised as the lines
    following a question up to the next blank line.

    Every line ending in "?" counts, bullets and numbering included. The
    template asks for the whys "as a list", so a bulleted chain is a normal
    shape for this section -- excluding those let a long chain past the cap
    untouched.
    """
    kept: list[str] = []
    questions = 0
    dropping = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.endswith("?"):
            questions += 1
            dropping = questions > limit
            if dropping:
                continue
        elif dropping:
            if stripped:
                continue  # the dropped question's answer
            dropping = False
            continue
        kept.append(line)

    if questions > limit:
        logger.info("incident_draft_whys_capped", heading=heading, returned=questions, kept=limit)
    return "\n".join(kept).strip()


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
            links.setdefault(match.group(1), match.group(0))
    return links


def _is_list_heading(heading: str) -> bool:
    """Whether a section's content should render as a bulleted list."""
    lowered = heading.lower()
    return any(marker in lowered for marker in _LIST_HEADING_MARKERS)
