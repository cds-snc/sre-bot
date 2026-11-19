"""Template fill over any ``AIWriter``: build the request, write, read the JSON answer.

The adapters delegate ``fill_template`` here, so every writer (and the in-memory fake) fills the
same way and differs only in how ``write`` reaches a model. Logs carry the answer's shape only:
source text and model output are content and never logged (decisions/observability.md).
"""

from collections.abc import Sequence

import structlog

from capabilities.ai_writing.api import AIWriter
from capabilities.ai_writing.domain import (
    FilledTemplate,
    TemplateField,
    TemplateSection,
    describe_match,
    extract_json_object,
    fill,
    parse_answers,
)
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult

logger = structlog.get_logger()


async def fill_template(
    writer: AIWriter,
    source: str,
    *,
    sections: Sequence[TemplateSection],
    instructions: str,
    max_output_tokens: int,
    temperature: float | None = None,
    fields: Sequence[TemplateField] = (),
) -> OperationResult[FilledTemplate]:
    """Fill ``sections`` and ``fields`` from ``source`` with one ``writer.write`` call.

    Returns the filled template (``truncated`` when only the complete pairs of a cut-off answer
    were kept), the write's classified error unchanged, or a permanent ``AI_WRITING_UNPARSEABLE``
    when nothing usable came back.
    """
    written = await writer.write(
        build_request(source, sections, fields),
        instructions=instructions,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    if not written.is_success:
        return OperationResult.error(
            status=written.status,
            message=written.message or "AI writing failed",
            error_code=written.error_code,
            retry_after=written.retry_after,
        )

    raw = written.data or ""
    answers, truncated = parse_answers(raw)
    if answers is None:
        # An empty string, prose instead of JSON and an answer cut off before
        # its first complete pair all look identical from the error code alone.
        logger.warning(
            "ai_writing_fill_unparseable",
            raw_length=len(raw),
            object_found=extract_json_object(raw) is not None,
            fenced="```" in raw,
        )
        return OperationResult.permanent_error(
            message="The model did not return a parseable JSON answer",
            error_code=ErrorCode.AI_WRITING_UNPARSEABLE,
        )

    filled = fill(answers, sections, fields, truncated=truncated)
    match = describe_match(answers, filled)
    if truncated:
        logger.warning(
            "ai_writing_fill_truncated_salvaged",
            raw_length=len(raw),
            key_count=match.key_count,
            section_count=len(sections),
        )
    if match.blank_requested or match.unmatched_key_count:
        # Separates the causes of a blank section that look identical in the
        # result: the model omitted it, answered under a key matching nothing
        # requested, or deliberately returned an empty string.
        logger.warning(
            "ai_writing_fill_coverage",
            section_count=len(sections),
            key_count=match.key_count,
            unmatched_key_count=match.unmatched_key_count,
            blank_key_count=match.blank_key_count,
            blank_sections=match.blank_requested,
        )
    return OperationResult.success(data=filled)


def build_request(source: str, sections: Sequence[TemplateSection], fields: Sequence[TemplateField]) -> str:
    """Render the sections (heading and instructions), the fields, then the caller's source, last and verbatim."""
    blocks = [
        f"### {section.heading}\nInstructions: {section.instructions.strip() or '(no instructions given)'}"
        for section in sections
    ]
    parts = ["Template sections:\n\n" + "\n\n".join(blocks)]
    if fields:
        lines = (f"- {f.label}: {f.instructions.strip()}" if f.instructions.strip() else f"- {f.label}" for f in fields)
        parts.append("Metadata fields:\n" + "\n".join(lines))
    parts.append(source)
    return "\n\n".join(parts)
