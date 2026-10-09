"""Replies, notices and wording for the incident scribe Slack entry point; the only scribe module that translates.

The handlers in ``entrypoints/slack.py`` render every reply and notice through
the builders here, so all translated strings live in one place. No Slack SDK is imported here.
"""

import re
from typing import Any

import structlog

from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.reply import SlackReplySender
from features.incident.core.api import translate as t
from features.incident.scribe.domain import DraftedDocument
from features.incident.scribe.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    NO_DOCUMENT_CODE,
)

DRAFT_DOMAIN = "incident_draft"
SUMMARY_DOMAIN = "incident_summary"
_SLACK_TEXT_LIMIT = 3000


def notify_working(
    reply: SlackReplySender,
    channel_id: str,
    payload: CommandPayload,
    locale: str,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Tell the invoker the draft is being written, before the slow work starts.

    Ephemeral, so only they see it. A failure here must never fail the command:
    a missing progress note is a far smaller problem than a lost draft.
    """
    text = t(
        f"{DRAFT_DOMAIN}.result.working",
        locale,
        "🤖 Reading this channel and drafting the incident report — this usually takes up to a minute. "
        "I'll post a link here when it's ready.",
    )
    posted = reply.post_ephemeral(channel_id=channel_id, user_id=payload.user_id, text=text)
    if not posted.is_success:
        log.warning("incident_draft_progress_notice_failed", error=posted.message, error_code=posted.error_code)


def draft_success_response(outcome: DraftedDocument | None, locale: str) -> CommandResponse:
    """Render the one-line confirmation, linking the new draft."""
    if outcome is None:
        return draft_error_response(locale)

    url = f"https://docs.google.com/document/d/{outcome.document_id}/edit"
    if outcome.partial:
        # Worth saying: later sections are missing because the response ran out,
        # not because the channel had nothing to say about them.
        message = t(
            f"{DRAFT_DOMAIN}.result.partial",
            locale,
            "Created an AI-generated <{{url}}|draft incident report> from this channel, but the "
            "response ran long and later sections are missing — re-run to fill them in. Copy over "
            "whatever's useful into the original incident doc created when the incident opened.",
            url=url,
        )
        return CommandResponse(message=message.replace("{{url}}", url), ephemeral=True)

    message = t(
        f"{DRAFT_DOMAIN}.result.header",
        locale,
        "Created an AI-generated <{{url}}|draft incident report> from this channel. "
        "Copy over whatever's useful — all or part — into the original incident doc "
        "created when the incident opened.",
        url=url,
    )
    # t() returns the fallback template verbatim when the catalogue isn't
    # loaded; interpolating here covers both paths (no-op when translated).
    return CommandResponse(message=message.replace("{{url}}", url), ephemeral=True)


def render_error(
    error_code: str | None,
    locale: str,
    log: structlog.stdlib.BoundLogger,
    result: Any,
) -> CommandResponse:
    """Map service error codes onto localized ephemeral notices."""
    if error_code == NO_DOCUMENT_CODE:
        msg = t(
            f"{DRAFT_DOMAIN}.result.no_document",
            locale,
            "I couldn't find an incident document bookmarked in this channel.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == DOCUMENT_UNREADABLE_CODE:
        msg = t(
            f"{DRAFT_DOMAIN}.result.unreadable",
            locale,
            "I couldn't read any sections from the incident document.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == EMPTY_HISTORY_CODE:
        msg = t(
            f"{DRAFT_DOMAIN}.result.empty_history",
            locale,
            "There's no channel history to draft from yet.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == NO_ANSWERS_CODE:
        msg = t(
            f"{DRAFT_DOMAIN}.result.no_answers",
            locale,
            "The channel history didn't answer any of the document's sections, so no draft was created.",
        )
        return CommandResponse(message=msg, ephemeral=True)

    log.warning(
        "incident_draft_service_error",
        status=getattr(result, "status", None),
        error_code=error_code,
        error=getattr(result, "message", None),
    )
    return draft_error_response(locale)


def draft_error_response(locale: str) -> CommandResponse:
    """Build the generic ephemeral error response."""
    msg = t(
        f"{DRAFT_DOMAIN}.result.error",
        locale,
        "❌ Couldn't create the draft document right now. Please try again shortly.",
    )
    return CommandResponse(message=msg, ephemeral=True)


def to_slack_mrkdwn(text: str) -> str:
    """Normalize model output into valid Slack ``mrkdwn``.

    Models occasionally emit standard/GitHub Markdown despite instructions.
    Slack does not render ``**bold**``, ``__bold__``, or ``#`` headings, and it
    shows literal ``**`` characters. This is a defensive, format-only pass:

    - ``**bold**``/``__bold__`` -> ``*bold*`` (Slack bold).
    - Markdown headings (``#``..``######``) -> a bold line.
    - Bullet markers (``-``, ``*``, ``+``, one or more ``•``) -> a single
      ``• `` prefix, collapsing duplicates like ``• •``.

    Content is never altered -- only formatting markers.
    """
    # **bold** / __bold__ -> *bold* first, so heading/bullet handling below
    # never has to reason about double-marker runs.
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        # Markdown heading -> bold line (drop the leading #s).
        heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
        if heading:
            content = heading.group(1).strip().strip("*")
            lines.append(f"*{content}*" if content else "")
            continue

        # Collapse any run of bullet markers (-, *, +, •) into a single "• ".
        # "*" counts only when whitespace follows, so a "*bold title*" line is kept.
        bullet = re.match(r"^(?:[-+\u2022]\s*|\*\s+)+(.*)$", stripped)
        if bullet:
            content = bullet.group(1).strip()
            stripped = f"\u2022 {content}" if content else "\u2022"

        lines.append(f"{indent}{stripped}")

    return "\n".join(lines).strip()


def summary_error_response(locale: str) -> CommandResponse:
    """Build the generic ephemeral error response."""
    msg = t(
        f"{SUMMARY_DOMAIN}.result.error",
        locale,
        "❌ Couldn't generate a summary right now. Please try again shortly.",
    )
    return CommandResponse(message=msg, ephemeral=True)


def summary_success_response(body: str, locale: str) -> CommandResponse:
    """Render the summary under its header with the AI disclaimer below it."""
    header = t(f"{SUMMARY_DOMAIN}.result.header", locale, "🧾 AI-generated Incident summary")
    disclaimer = t(
        f"{SUMMARY_DOMAIN}.result.disclaimer",
        locale,
        "This summary is AI-generated and AI can make mistakes, please review for accuracy.",
    )
    # Single asterisks are Slack mrkdwn bold. A header block renders the title
    # bold and larger; the plain message is the notification fallback.
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header, "emoji": True}},
        *mrkdwn_blocks(body),
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{disclaimer}*"}},
    ]
    return CommandResponse(message=f"{header}\n\n{body}\n\n*{disclaimer}*", ephemeral=True, blocks=blocks)


def summary_text(key: str, locale: str, fallback: str) -> str:
    """Translate one ``incident_summary`` catalogue key."""
    return t(f"{SUMMARY_DOMAIN}.{key}", locale, fallback)


def mrkdwn_blocks(text: str) -> list[dict[str, Any]]:
    """Split ``text`` into section blocks, each under Slack's text limit."""
    chunks = [text[i : i + _SLACK_TEXT_LIMIT] for i in range(0, len(text), _SLACK_TEXT_LIMIT)] or [""]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]
