"""Block Kit views, payload parsers and wording for the incident scribe Slack entry point; the only scribe module that translates.

The handlers in ``entrypoints/slack.py`` render every reply, modal and notice
through the builders here, so all translated strings and action ids live in
one place. No Slack SDK is imported here.
"""

import json
import re
from types import MappingProxyType
from typing import Any

import structlog

from contracts.operations.codes import ErrorCode
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.reply import SlackReplySender
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)
from features.incident.core.api import translate as t
from features.incident.scribe.comms_profile import ProfileLabels, format_profile_time, render_profile
from features.incident.scribe.domain import (
    CopyReadyText,
    DraftedDocument,
    NoNewInformationWording,
    StatusUpdateEdit,
    StatusUpdateOverview,
)
from features.incident.scribe.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    NO_DOCUMENT_CODE,
)
from features.incident.scribe.status_update import DRAFT_UNPARSEABLE_CODE
from features.incident.scribe.status_update_prompt import MAX_INSTRUCTIONS_CHARS

DRAFT_DOMAIN = "incident_draft"
SUMMARY_DOMAIN = "incident_summary"
STATUS_UPDATE_DOMAIN = "incident_status_update"
_SLACK_TEXT_LIMIT = 3000
REVIEW_ACTION_ID = "incident.scribe.status_update.review"
REVIEW_CALLBACK_ID = "incident.scribe.status_update.approve"
OPEN_ACTION_ID = "incident.scribe.status_update.open"
HISTORY_ACTION_ID = "incident.scribe.status_update.history"
PUBLISHED_ACTION_ID = "incident.scribe.status_update.published"
GENERATE_ACTION_ID = "incident.scribe.status_update.generate"
NEW_ACTION_ID = "incident.scribe.status_update.new"
SAVE_ACTION_ID = "incident.scribe.status_update.save"
_APPROVED_ROW_CAP = 50
_SECURITY_CONFIRMED = "confirmed"
_TEXT_FIELDS = ("affected_service", "impact", "current_action", "workaround")


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


def status_t(key: str, locale: str, fallback: str, **variables: Any) -> str:
    return t(f"{STATUS_UPDATE_DOMAIN}.{key}", locale, fallback, **variables)


def status_error_text(error_code: str | None, locale: str) -> str:
    """Map a lookup, store or drafting error code onto its localized in-modal message."""
    if error_code == ErrorCode.EMPTY_HISTORY:
        return status_t("empty_history", locale, "There is no channel history to draft a status update from yet.")
    if error_code == DRAFT_UNPARSEABLE_CODE:
        return status_t("unparseable", locale, "I couldn't turn the model's answer into a status update. Please try again.")
    if error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
        return status_t("conflict", locale, "Another status update was saved at the same time. Please try again.")
    if error_code == ErrorCode.NOT_AN_INCIDENT:
        return status_t(
            "not_an_incident", locale, "This channel is not an incident channel, so there are no status updates to show."
        )
    if error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION:
        return status_t(
            "ambiguous", locale, "More than one incident uses this channel, so I can't tell which status updates to show."
        )
    return status_t("error", locale, "Couldn't load the status update right now. Please try again shortly.")


def status_update_open_failed(locale: str) -> CommandResponse:
    message = status_t("open_failed", locale, "Couldn't open the status updates right now. Please try again shortly.")
    return CommandResponse(message=message, ephemeral=True)


def status_update_view(locale: str, private_metadata: str, blocks: list[dict[str, Any]], *, close: bool) -> dict[str, Any]:
    """Build the status-updates modal; the loading view has no Close button."""
    view: dict[str, Any] = {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": status_t("title", locale, "Mises à jour de statut" if locale.startswith("fr") else "Status updates"),
        },
        "private_metadata": private_metadata,
        "blocks": blocks,
    }
    if close:
        view["close"] = {
            "type": "plain_text",
            "text": status_t("close", locale, "Fermer" if locale.startswith("fr") else "Close"),
        }
    return view


def mrkdwn_blocks(text: str) -> list[dict[str, Any]]:
    """Split ``text`` into section blocks, each under Slack's text limit."""
    chunks = [text[i : i + _SLACK_TEXT_LIMIT] for i in range(0, len(text), _SLACK_TEXT_LIMIT)] or [""]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]


def _language_heading(language: str) -> str:
    """Name a profile language in that language ("English", "Français"), matching the catalogue."""
    locale, fallback = ("en-US", "English") if language == "en" else ("fr-FR", "Français")
    return status_t(f"language.{language}", locale, fallback)


def _pending_blocks(update: StatusUpdate) -> list[dict[str, Any]]:
    """Render the draft in English then French with the default comms profile.

    Both languages use fixed locale lookups, so both render whatever the
    invoker's locale is.
    """
    blocks: list[dict[str, Any]] = []
    for locale, language, text in (("en-US", "en", update.en), ("fr-FR", "fr", update.fr)):
        heading = _language_heading(language)
        profile = render_profile(text, update.stage, update.next_update_at, build_profile_labels(locale))
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": heading}})
        blocks.extend(mrkdwn_blocks(profile))
    return blocks


def build_profile_labels(locale: str) -> ProfileLabels:
    """Build the comms profile labels for one language from the catalogue."""
    fr = locale.startswith("fr")
    return ProfileLabels(
        stage=status_t("label.stage", locale, "Étape" if fr else "Stage"),
        affected_service=status_t("label.affected_service", locale, "Service touché" if fr else "Affected service"),
        impact=status_t("label.impact", locale, "Incidence" if fr else "Impact"),
        current_action=status_t("label.current_action", locale, "Mesure en cours" if fr else "Current action"),
        workaround=status_t("label.workaround", locale, "Solution de contournement" if fr else "Workaround"),
        next_update=status_t("label.next_update", locale, "Prochaine mise à jour" if fr else "Next update"),
        time_suffix=status_t("time_suffix", locale, "HE" if fr else "ET"),
        stage_names=MappingProxyType(
            {stage: status_t(f"stage.{stage.value}", locale, stage.value.capitalize()) for stage in StatusUpdateStage}
        ),
    )


def _overview_actions(locale: str, update: StatusUpdate | None) -> dict[str, Any]:
    """Build the overview's actions block: New update with nothing pending, Review with a pending draft."""
    fr = locale.startswith("fr")
    if update is None:
        button = {
            "type": "button",
            "action_id": NEW_ACTION_ID,
            "text": {
                "type": "plain_text",
                "text": status_t("new_update_button", locale, "Nouvelle mise à jour" if fr else "New update"),
            },
        }
    else:
        button = {
            "type": "button",
            "action_id": REVIEW_ACTION_ID,
            "text": {"type": "plain_text", "text": status_t("review_button", locale, "Réviser" if fr else "Review")},
            "value": json.dumps({"incident_id": update.incident_id, "sequence": update.sequence}),
        }
    return {"type": "actions", "block_id": "overview_actions", "elements": [button | {"style": "primary"}]}


def origin_line(update: StatusUpdate, locale: str) -> str:
    """Say who made the draft, how and when, for example ``Written by <@U1> at 2026-10-07 11:00 ET``.

    A record from before origins existed names only its author.
    """
    key = f"origin.{update.origin.value if update.origin is not None else 'unknown'}"
    time = format_profile_time(update.created_at, build_profile_labels(locale))
    return status_t(key, locale, key, author=f"<@{update.author}>", time=time)


def _stage_line(update: StatusUpdate, locale: str) -> str:
    """Return ``*Stage* - time - approved by <@U> - Published`` for an approved or published update."""
    fr = locale.startswith("fr")
    labels = build_profile_labels(locale)
    parts = [f"*{labels.stage_names[update.stage]}*", format_profile_time(update.approved_at or update.created_at, labels)]
    if update.approver:
        by = status_t("row.approved_by", locale, "approuvée par" if fr else "approved by")
        parts.append(f"{by} <@{update.approver}>")
    if update.state is StatusUpdateState.PUBLISHED:
        parts.append(status_t("row.published", locale, "Publiée" if fr else "Published"))
    else:
        parts.append(status_t("row.not_published", locale, "Non publiée" if fr else "Not published"))
    return " - ".join(parts)


def _approved_blocks(approved: tuple[StatusUpdate, ...], locale: str) -> list[dict[str, Any]]:
    """Render the approved-updates header, then one Open row per update (newest 50), an empty state or a cap note."""
    fr = locale.startswith("fr")
    header = status_t("history_header", locale, "Mises à jour approuvées" if fr else "Approved updates")
    blocks: list[dict[str, Any]] = [
        {"type": "header", "block_id": "approved_updates", "text": {"type": "plain_text", "text": header}}
    ]
    if not approved:
        empty = status_t(
            "history_empty",
            locale,
            "Aucune mise à jour de statut n'a encore été approuvée pour cet incident."
            if fr
            else "No status update has been approved for this incident yet.",
        )
        blocks.append({"type": "section", "block_id": "approved_updates_empty", "text": {"type": "mrkdwn", "text": empty}})
        return blocks
    open_text = status_t("open_button", locale, "Ouvrir" if fr else "Open")
    for update in approved[:_APPROVED_ROW_CAP]:
        blocks.append(
            {
                "type": "section",
                "block_id": f"approved_update.{update.sequence}",
                "text": {"type": "mrkdwn", "text": _stage_line(update, locale)},
                "accessory": {
                    "type": "button",
                    "action_id": OPEN_ACTION_ID,
                    "text": {"type": "plain_text", "text": open_text},
                    "value": json.dumps({"incident_id": update.incident_id, "sequence": update.sequence}),
                },
            }
        )
    if len(approved) > _APPROVED_ROW_CAP:
        note = status_t(
            "history_truncated",
            locale,
            "Affichage des 50 dernières mises à jour approuvées." if fr else "Showing the latest 50 approved updates.",
        )
        blocks.append(
            {"type": "context", "block_id": "approved_updates_truncated", "elements": [{"type": "mrkdwn", "text": note}]}
        )
    return blocks


def build_overview_view(overview: StatusUpdateOverview, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the status-updates modal: the pending draft part (who made it, the draft, the buttons), then the approved-updates list."""
    if overview.pending is not None:
        origin = {
            "type": "context",
            "block_id": "pending_origin",
            "elements": [{"type": "mrkdwn", "text": origin_line(overview.pending, locale)}],
        }
        blocks = [origin, *_pending_blocks(overview.pending), _overview_actions(locale, overview.pending)]
    else:
        blocks = [
            *mrkdwn_blocks(status_t("no_pending", locale, "There is no status update draft for this incident yet.")),
            _overview_actions(locale, None),
        ]
    blocks.extend(_approved_blocks(overview.approved, locale))
    return status_update_view(locale, private_metadata, blocks, close=True)


def build_draft_error_view(error_code: str | None, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal showing a localized drafting error with a Close button."""
    return status_update_view(locale, private_metadata, mrkdwn_blocks(status_error_text(error_code, locale)), close=True)


def build_review_error_view(error_code: str | None, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal showing a localized review or approval error with a Close button.

    Differs from ``build_draft_error_view`` in the wording of a conflict (the
    draft changed or was approved elsewhere) and in the stage-below-floor refusal.
    """
    if error_code == ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR:
        text = status_t(
            "stage_below_floor",
            locale,
            "L'étape ne peut pas précéder celle de la dernière mise à jour approuvée. Rouvrez la révision et choisissez une étape ultérieure."
            if locale.startswith("fr")
            else "The stage cannot be earlier than the latest approved update's stage. Reopen the review and pick a later stage.",
        )
    elif error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
        text = status_t(
            "review_conflict",
            locale,
            "Ce brouillon a changé ou a été approuvé ailleurs. Rouvrez les mises à jour de statut pour voir la dernière version."
            if locale.startswith("fr")
            else "This draft changed or was approved elsewhere. Reopen the status updates to see the latest version.",
        )
    else:
        text = status_error_text(error_code, locale)
    return status_update_view(locale, private_metadata, mrkdwn_blocks(text), close=True)


def build_published_error_view(error_code: str | None, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the Close-only modal for a failed published toggle; only a conflict has its own wording."""
    if error_code != ErrorCode.STATUS_UPDATE_CONFLICT:
        return build_draft_error_view(error_code, locale, private_metadata)
    text = status_t(
        "toggle_conflict",
        locale,
        "Cette mise à jour a été marquée comme publiée ou non publiée ailleurs. Rouvrez les mises à jour de statut pour voir la dernière version."
        if locale.startswith("fr")
        else "This update was marked published or not published elsewhere. Reopen the status updates to see the latest version.",
    )
    return status_update_view(locale, private_metadata, mrkdwn_blocks(text), close=True)


def _review_input(block_id: str, label: str, element: dict[str, Any]) -> dict[str, Any]:
    return {"type": "input", "block_id": block_id, "label": {"type": "plain_text", "text": label}, "element": element}


def _ai_blocks(locale: str, instructions: str | None, *, security_confirm: bool) -> list[dict[str, Any]]:
    """Build the AI section: the optional instructions input, the optional confirmation checkbox, the Draft with AI button."""
    fr = locale.startswith("fr")
    element: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": "text",
        "multiline": True,
        "max_length": MAX_INSTRUCTIONS_CHARS,
    }
    if instructions:
        element["initial_value"] = instructions
    label = status_t(
        "generate_label", locale, "Instructions pour l'IA (facultatif)" if fr else "Instructions for the AI (optional)"
    )
    hint = status_t(
        "generate_hint",
        locale,
        "Laissez vide pour rédiger à partir de la conversation, ou indiquez ce qu'il faut changer, "
        "par exemple : ne pas nommer le fournisseur."
        if fr
        else "Leave empty to draft from the conversation, or say what to change, for example: do not name the vendor.",
    )
    blocks = [_review_input("instructions", label, element) | {"hint": {"type": "plain_text", "text": hint}, "optional": True}]
    if security_confirm:
        title = status_t("security_confirm_title", locale, "Confirmation de sécurité" if fr else "Security confirmation")
        option = status_t(
            "security_confirm_label",
            locale,
            "Je confirme l'envoi de ce contenu au modèle d'IA" if fr else "I confirm sending this content to the AI model",
        )
        checkbox = {
            "type": "checkboxes",
            "action_id": "confirm",
            "options": [{"text": {"type": "plain_text", "text": option}, "value": _SECURITY_CONFIRMED}],
        }
        blocks.append(_review_input("security_confirm", title, checkbox) | {"optional": True})
    button = {
        "type": "button",
        "action_id": GENERATE_ACTION_ID,
        "text": {
            "type": "plain_text",
            "text": status_t("generate_button", locale, "Rédiger avec l'IA" if fr else "Draft with AI"),
        },
    }
    blocks.append({"type": "actions", "block_id": "generate_button", "elements": [button]})
    return blocks


def build_review_view(
    update: StatusUpdate,
    locale: str,
    private_metadata: str,
    notice: str | None = None,
    *,
    instructions: str | None = None,
    security_confirm: bool = False,
    with_ai: bool = True,
) -> dict[str, Any]:
    """Build the review modal: any notice, the AI section, the stage select, the EN and FR fields, then Save draft.

    Field inputs are optional so Slack never blocks a blank field itself; the
    submission listener validates and names the blank ones. The Draft with AI
    and Save draft buttons are block actions, so Approve stays the only submit.
    ``instructions`` prefills the instructions input and ``security_confirm``
    adds the security confirmation checkbox. ``with_ai=False`` leaves the AI
    section out, for when text generation is not configured.
    """
    fr = locale.startswith("fr")
    stage_names = build_profile_labels(locale).stage_names
    options = [{"text": {"type": "plain_text", "text": stage_names[stage]}, "value": stage.value} for stage in StatusUpdateStage]
    blocks = mrkdwn_blocks(notice) if notice else []
    if with_ai:
        blocks.extend(_ai_blocks(locale, instructions, security_confirm=security_confirm))
    blocks.append(
        _review_input(
            "stage",
            status_t("label.stage", locale, "Étape" if fr else "Stage"),
            {
                "type": "static_select",
                "action_id": "stage",
                "options": options,
                "initial_option": next(option for option in options if option["value"] == update.stage.value),
            },
        )
    )
    for profile_locale, language, text in (("en-US", "en", update.en), ("fr-FR", "fr", update.fr)):
        labels = build_profile_labels(profile_locale)
        heading = _language_heading(language)
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": heading}})
        for name in _TEXT_FIELDS:
            element = {
                "type": "plain_text_input",
                "action_id": "text",
                "multiline": True,
                "initial_value": getattr(text, name),
            }
            block = _review_input(f"{language}.{name}", getattr(labels, name), element)
            block["optional"] = True
            blocks.append(block)
    save = {
        "type": "button",
        "action_id": SAVE_ACTION_ID,
        "text": {
            "type": "plain_text",
            "text": status_t("save_button", locale, "Enregistrer le brouillon" if fr else "Save draft"),
        },
    }
    blocks.append({"type": "actions", "block_id": "save_button", "elements": [save]})
    view = status_update_view(locale, private_metadata, blocks, close=False)
    view["title"] = {
        "type": "plain_text",
        "text": status_t("review_title", locale, "Réviser la mise à jour" if fr else "Review update"),
    }
    view["callback_id"] = REVIEW_CALLBACK_ID
    view["submit"] = {"type": "plain_text", "text": status_t("approve_button", locale, "Approuver" if fr else "Approve")}
    view["close"] = {"type": "plain_text", "text": status_t("cancel", locale, "Annuler" if fr else "Cancel")}
    return view


def parse_review_submission(view: dict[str, Any]) -> StatusUpdateEdit | None:
    """Read the submitted stage and fields back into an edit; ``None`` when the stage is missing or unknown.

    Text is not trimmed and a cleared field (Slack sends null) reads as ``""``,
    so ``validate_approval_edit`` is the single blank-handling path.
    """
    values: dict[str, Any] = (view.get("state") or {}).get("values") or {}
    selected = ((values.get("stage") or {}).get("stage") or {}).get("selected_option") or {}
    try:
        stage = StatusUpdateStage(str(selected.get("value", "")))
    except ValueError:
        return None

    def read(language: str) -> StatusUpdateText:
        return StatusUpdateText(
            **{name: ((values.get(f"{language}.{name}") or {}).get("text") or {}).get("value") or "" for name in _TEXT_FIELDS}
        )

    return StatusUpdateEdit(stage=stage, en=read("en"), fr=read("fr"))


def parse_ai_form(view: dict[str, Any]) -> tuple[str, bool]:
    """Read the untrimmed instructions and whether the security confirmation is checked from a block action's view.

    A missing or cleared input (Slack sends null) reads as ``""``; only the
    confirmed option counts as a confirmation.
    """
    values: dict[str, Any] = (view.get("state") or {}).get("values") or {}
    instructions = ((values.get("instructions") or {}).get("text") or {}).get("value") or ""
    selected = ((values.get("security_confirm") or {}).get("confirm") or {}).get("selected_options") or []
    confirmed = any(isinstance(option, dict) and option.get("value") == _SECURITY_CONFIRMED for option in selected)
    return str(instructions), confirmed


def build_generating_view(locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal shown while the model fills the draft; no buttons."""
    text = status_t(
        "generating",
        locale,
        "Rédaction de la mise à jour de statut avec l'IA en cours. Cela prend généralement jusqu'à une minute..."
        if locale.startswith("fr")
        else "Drafting the status update with AI. This usually takes up to a minute...",
    )
    return status_update_view(locale, private_metadata, mrkdwn_blocks(text), close=False)


def generate_notice(key: str, locale: str) -> str:
    """Return the localized Draft with AI notice for ``key``.

    ``key`` is one of ``generated_note``, ``generate_carried_forward``,
    ``generate_failed``, ``generate_unparseable``, ``generate_security``,
    ``generate_unavailable`` or ``generate_empty_history``.
    """
    return status_t(key, locale, key)


def save_notice(key: str, locale: str) -> str:
    """Return the localized Save draft notice for ``key``: ``saved_note`` or ``save_failed``."""
    return status_t(key, locale, key)


def build_review_field_errors(block_ids: tuple[str, ...], locale: str) -> dict[str, str]:
    """Map each rejected block id to the localized blank-field message for ``ack(response_action="errors")``."""
    message = status_t("field_blank", locale, "Entrez une valeur." if locale.startswith("fr") else "Enter a value.")
    return dict.fromkeys(block_ids, message)


def build_saving_view(locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal shown while the approval is saved; no buttons and no submit."""
    blocks = mrkdwn_blocks(
        status_t("saving", locale, "Enregistrement de l'approbation..." if locale.startswith("fr") else "Saving the approval...")
    )
    return status_update_view(locale, private_metadata, blocks, close=False)


def build_copy_ready_view(
    copy: CopyReadyText, locale: str, private_metadata: str, update: StatusUpdate | None = None
) -> dict[str, Any]:
    """Build the modal showing the approved text, one preformatted block per language, with Close.

    With ``update`` (a reopened approved update) a status line comes first, with
    a toggle button carrying the target published state (so a stale view cannot
    invert a newer one), then who marked it published and when if it is
    published, and a Back button, valued with the channel id from the metadata,
    comes last.
    """
    note = status_t(
        "approved_note",
        locale,
        "Approuvé. Relisez, puis copiez dans le canal de votre produit. Rien n'a été publié."
        if locale.startswith("fr")
        else "Approved. Proofread, then copy into your product's channel. Nothing was posted.",
    )
    blocks = mrkdwn_blocks(note)
    for language, text in (("en", copy.en), ("fr", copy.fr)):
        heading = _language_heading(language)
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": heading}})
        preformatted = {"type": "rich_text_preformatted", "elements": [{"type": "text", "text": text}]}
        blocks.append({"type": "rich_text", "elements": [preformatted]})
    if update is not None:
        fr = locale.startswith("fr")
        published = update.state is StatusUpdateState.PUBLISHED
        if published:
            toggle_text = status_t("mark_unpublished", locale, "Marquer comme non publiée" if fr else "Mark as not published")
        else:
            toggle_text = status_t("mark_published", locale, "Marquer comme publiée" if fr else "Mark as published")
        toggle = {
            "type": "button",
            "action_id": PUBLISHED_ACTION_ID,
            "text": {"type": "plain_text", "text": toggle_text},
            "value": json.dumps({"incident_id": update.incident_id, "sequence": update.sequence, "published": not published}),
        }
        status: list[dict[str, Any]] = [
            {
                "type": "section",
                "block_id": "approved_status",
                "text": {"type": "mrkdwn", "text": _stage_line(update, locale)},
                "accessory": toggle,
            }
        ]
        if published and update.published_by and update.published_at is not None:
            by = status_t("published_line.by", locale, "Publiée par" if fr else "Published by")
            at = status_t("published_line.at", locale, "le" if fr else "at")
            when = format_profile_time(update.published_at, build_profile_labels(locale))
            line = f"{by} <@{update.published_by}> {at} {when}"
            status.append({"type": "section", "block_id": "published_status", "text": {"type": "mrkdwn", "text": line}})
        channel_id = json.loads(private_metadata).get("channel_id", "")
        back = {
            "type": "button",
            "action_id": HISTORY_ACTION_ID,
            "text": {
                "type": "plain_text",
                "text": status_t("back_button", locale, "Retour" if locale.startswith("fr") else "Back"),
            },
            "value": json.dumps({"channel_id": channel_id}),
        }
        blocks = [*status, *blocks, {"type": "actions", "block_id": "history_button", "elements": [back]}]
    return status_update_view(locale, private_metadata, blocks, close=True)


def build_no_new_information_wording() -> NoNewInformationWording:
    """Build the carried-forward current-action wording in both languages."""
    return NoNewInformationWording(
        en=status_t("no_new_information", "en-US", "No new information since the last update."),
        fr=status_t("no_new_information", "fr-FR", "Aucune nouvelle information depuis la dernière mise à jour."),
    )
