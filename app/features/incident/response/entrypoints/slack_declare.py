"""Slack entry point of the declare: ``/incident``, its form, the locale toggle and the alert buttons.

``/incident <name>`` opens a loading view on the command's trigger at once, then
replaces it with the declare form (slack_declare_views.py), its name prefilled and
its products the report placements. The form is in the invoker's language when the
form has it, English otherwise; its locale button re-renders it in the other
language, keeping the typed name.

The form's submission is validated before its single ack: a name that is not
letters, digits, spaces and dashes, or is 60 characters or more, answers the field
error in the instance languages and declares nothing. A valid one acks, then runs
``declare`` with the view id as its idempotency key, so a redelivered submission is
the same incident. The record is written first; then the success view opens on the
submission's trigger, naming the new channel. A declare that could not record the
incident, or created no channel, tells the declarer in a direct message; one whose
later steps failed says so in the incident channel.

The alert buttons arrive as a legacy attachment's ``interactive_message`` under the
callback id the webhook producer posts. ``call-incident`` opens the form named after
the alert, carrying the alert's channel and message in its private metadata, which
the submission turns into the incident's source alert with its permalink.
``ignore-incident`` claims the press for that message, counts one acknowledgement
on the webhook for the first press only, then replaces the buttons with who ignored
the alert, in the alert channel's languages. A failed count is logged and never
blocks the replacement.

Handlers open one service scope and run in one event loop (``asyncio.run``, the
sync Bolt edge). Views, messages and links go through the reply sender, never the
raw Slack client. Each handler sends its Sentinel event with ids only.
"""

import asyncio
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog

from contracts.coordination import ClaimResult, ConditionalWriteStore
from contracts.languages import LanguagePolicy, MultilingualText
from contracts.operations.codes import ErrorCode
from contracts.records import RecordStore
from contracts.services import ServiceScopeOpener
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.vocabulary import Severity
from features.incident.core.api import ConversationReference, MessageReference, ReportPlacement
from features.incident.core.api import translate as t
from features.incident.response import providers
from features.incident.response.entrypoints.scope import language_policy, shared_languages
from features.incident.response.entrypoints.slack_declare_texts import SlackDeclareTexts
from features.incident.response.entrypoints.slack_declare_views import (
    DECLARE_CALLBACK_ID,
    DECLARE_DOMAIN,
    LOCALE_ACTION_ID,
    NAME_BLOCK_ID,
    POLICY_HELP_BLOCK_ID,
    PRODUCT_BLOCK_ID,
    SECURITY_BLOCK_ID,
    SEVERITY_BLOCK_ID,
    build_declare_view,
    build_loading_view,
    build_success_view,
    form_locale,
    toggled,
    view_locale,
)
from features.incident.response.service.declare import ChatSurface, Declared, DeclareRequest, declare
from features.incident.response.service.status import StageOutcome
from features.incident.response.settings import get_incident_response_settings

logger = structlog.get_logger()

ALERT_BUTTONS_CALLBACK_ID = "incident.response.alert_buttons"
# The callback id and locale action the legacy declare used; the webhook producer posts the callback id.
LEGACY_ALERT_BUTTONS_CALLBACK_ID = "handle_incident_action_buttons"
LEGACY_LOCALE_ACTION_ID = "incident_change_locale"

CALL_INCIDENT = "call-incident"
IGNORE_INCIDENT = "ignore-incident"

DECLARE_SUBMITTED = "incident_called"
CALL_PRESSED = "call_incident_button_pressed"
IGNORE_PRESSED = "ignore_incident_button_pressed"

_NAME = re.compile(r"^[\w\-\s]+$")
_NAME_MAX = 59

# Writable legacy attachment fields; Slack echoes read-only keys (id, app_unfurl_url, from_url, ...) that chat.update rejects.
_WRITABLE_ATTACHMENT_KEYS = frozenset(
    {
        "fallback",
        "color",
        "pretext",
        "author_name",
        "author_link",
        "author_icon",
        "title",
        "title_link",
        "text",
        "fields",
        "image_url",
        "thumb_url",
        "footer",
        "footer_icon",
        "ts",
        "mrkdwn_in",
        "blocks",
        "callback_id",
        "actions",
        "attachment_type",
    }
)
_IGNORED_COLOR = "3AA3E3"

# The declare steps after the record whose failure the incident channel is told about.
_FOLLOWER_STAGES = ("report", "video_call", "messages", "invites", "list_row")


def register_declare(registrar: SlackCommandRegistrar, scopes: ServiceScopeOpener) -> None:
    """Register ``/incident``, the form's submission and locale toggle, and the alert buttons.

    Args:
        registrar: Slack command registrar.
        scopes: Opens the service scope each handler runs in.
    """

    def _dispatch(payload: CommandPayload) -> CommandResponse:
        return handle_declare_command(payload, registrar.reply, scopes)

    def _toggle(ack: Callable[..., Any], body: dict[str, Any]) -> None:
        handle_locale_toggle(ack, body, registrar.reply)

    def _submit(ack: Callable[..., Any], body: dict[str, Any]) -> None:
        handle_declare_submission(ack, body, registrar.reply, scopes)

    def _press(ack: Callable[..., Any], body: dict[str, Any]) -> None:
        handle_alert_button(ack, body, registrar.reply, scopes)

    registrar.register_command(
        command="incident",
        handler=_dispatch,
        parent=None,
        description="Declare an incident",
        description_key=f"{DECLARE_DOMAIN}.description",
        usage_hint="<name>",
        examples=["too many 500 errors"],
        example_keys=[f"{DECLARE_DOMAIN}.examples.default"],
    )
    registrar.register_view_submission(DECLARE_CALLBACK_ID, _submit)
    registrar.register_block_action(LOCALE_ACTION_ID, _toggle, legacy_action_ids=(LEGACY_LOCALE_ACTION_ID,))
    registrar.register_attachment_action(
        ALERT_BUTTONS_CALLBACK_ID, _press, legacy_callback_ids=(LEGACY_ALERT_BUTTONS_CALLBACK_ID,)
    )


def handle_declare_command(payload: CommandPayload, reply: SlackReplySender, scopes: ServiceScopeOpener) -> CommandResponse:
    """Handle ``/incident <name>``: open the loading view, then the declare form prefilled with ``name``.

    Returns:
        An empty ephemeral response once the form opened; a private notice in the
        invoker's language when it could not open.
    """
    locale = form_locale(language_policy(scopes).reply_languages(payload.user_locale)[0])
    log = logger.bind(command="incident_declare", user_id=payload.user_id, channel_id=payload.channel_id)
    trigger_id = str(payload.platform_metadata.get("trigger_id", ""))
    if not trigger_id or not _open_form(reply, trigger_id, name=payload.text.strip(), locale=locale, metadata=""):
        log.warning("incident_declare_form_open_failed", trigger=bool(trigger_id))
        return CommandResponse(message=_t("reply.open_failed", locale), ephemeral=True)
    log.info("incident_declare_form_opened")
    return CommandResponse(message="", ephemeral=True)


def handle_locale_toggle(ack: Callable[..., Any], body: dict[str, Any], reply: SlackReplySender) -> None:
    """Handle the form's locale button: re-render the open form in the other language, keeping the typed name."""
    ack()
    view = body.get("view") or {}
    current = str(((body.get("actions") or [{}])[0]).get("value", ""))
    name = _input_value(view, NAME_BLOCK_ID) or ""
    form = build_declare_view(
        name=name,
        placements=_placements(),
        locale=toggled(form_locale(current)),
        private_metadata=str(view.get("private_metadata") or ""),
        handbook_url=_handbook_url(),
    )
    updated = reply.update_view(view_id=str(view.get("id", "")), view=form)
    if not updated.is_success:
        logger.warning("incident_declare_locale_toggle_failed", error_code=updated.error_code)


def handle_declare_submission(
    ack: Callable[..., Any], body: dict[str, Any], reply: SlackReplySender, scopes: ServiceScopeOpener
) -> None:
    """Handle the form's submission: validate, ack once, declare, then open the success view or tell the declarer."""
    view = body.get("view") or {}
    name = (_input_value(view, NAME_BLOCK_ID) or "").strip()
    policy = language_policy(scopes)
    error = _name_error(name, policy.reply_languages(None))
    if error is not None:
        ack(response_action="errors", errors={NAME_BLOCK_ID: error})
        return
    ack()

    user_id = str((body.get("user") or {}).get("id", ""))
    locale = view_locale(view)
    log = logger.bind(operation="incident_declare_submission", user_id=user_id, view_id=view.get("id"))
    with scopes.create_scope() as services:
        systems = services.get(ConfiguredSystems)
        tenants = systems.tenants()
        placement = _placement(view, tenants.get(WorkplaceSystem.GOOGLE))
        request = DeclareRequest(
            idempotency_key=f"slack:{tenants.get(WorkplaceSystem.SLACK, '')}:{view.get('id', '')}",
            title=name,
            security_incident=_selected(view, SECURITY_BLOCK_ID) == "yes",
            declarer=user_id,
            declared_at=datetime.now(UTC),
            severity=_severity(_selected(view, SEVERITY_BLOCK_ID)),
            placement=placement,
            policy_help=_selected(view, POLICY_HELP_BLOCK_ID) == "yes",
            source_alert=_source_alert(view, tenants.get(WorkplaceSystem.SLACK), reply),
        )
        ports = providers.declare_ports(
            services.get(RecordStore), services.get(ConditionalWriteStore), systems, services.get(LanguagePolicy)
        )
        declare_policy = providers.declare_policy()
        texts = SlackDeclareTexts(placement, primary=policy.reply_languages(None)[0])
        result = asyncio.run(declare(request, ports, declare_policy, texts))
        if result.is_success and result.data is not None:
            asyncio.run(_warn_followers(result.data, ports.chat, policy))
    asyncio.run(providers.declare_event_sink().send(DECLARE_SUBMITTED, {"user_id": user_id, "view_id": str(view.get("id"))}))

    if not result.is_success or result.data is None:
        log.warning("incident_declare_refused", operation_status=result.status.value, error_code=result.error_code)
        key = "reply.in_progress" if result.error_code == ErrorCode.DECLARE_IN_PROGRESS else "reply.record_failed"
        _direct(reply, user_id, _t(key, locale), log)
        return
    conversation = result.data.incident.conversation
    if conversation is None:
        log.warning("incident_declare_no_conversation", incident_id=result.data.incident.id)
        _direct(reply, user_id, _t("reply.conversation_failed", locale), log)
        return
    success = build_success_view(locale=locale, channel_id=conversation.vendor_id)
    opened = reply.open_view(trigger_id=str(body.get("trigger_id", "")), view=success)
    if not opened.is_success:
        log.warning("incident_declare_success_view_failed", error_code=opened.error_code)


def handle_alert_button(
    ack: Callable[..., Any], body: dict[str, Any], reply: SlackReplySender, scopes: ServiceScopeOpener
) -> None:
    """Handle an alert's call-incident or ignore-incident button."""
    ack()
    action = (body.get("actions") or [{}])[0]
    name, value = str(action.get("name", "")), str(action.get("value", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    channel_id, message_ts = _alert_location(body)
    log = logger.bind(operation="incident_alert_button", button=name, user_id=user_id, channel_id=channel_id)
    event = {"user_id": user_id, "channel_id": channel_id, "message_ts": message_ts}
    if name == CALL_INCIDENT:
        metadata = json.dumps({"source_channel_id": channel_id, "source_message_ts": message_ts})
        locale = form_locale(language_policy(scopes).reply_languages(None)[0])
        if not _open_form(reply, str(body.get("trigger_id", "")), name=value, locale=locale, metadata=metadata):
            log.warning("incident_declare_form_open_failed", trigger=bool(body.get("trigger_id")))
        asyncio.run(providers.declare_event_sink().send(CALL_PRESSED, event))
        return
    if name != IGNORE_INCIDENT:
        log.warning("incident_alert_button_unknown")
        return
    with scopes.create_scope() as services:
        tenant = services.get(ConfiguredSystems).tenants().get(WorkplaceSystem.SLACK, "")
        languages = shared_languages(
            services.get(LanguagePolicy),
            ConversationReference(system=WorkplaceSystem.SLACK, tenant=tenant, vendor_id=channel_id),
        )
        asyncio.run(_count_ignore(services.get(RecordStore), services.get(ConditionalWriteStore), value, channel_id, message_ts))
    _replace_buttons(reply, body, channel_id, message_ts, _ignored(user_id, languages), log)
    asyncio.run(providers.declare_event_sink().send(IGNORE_PRESSED, event))


def ignore_claim_key(channel_id: str, message_ts: str) -> str:
    """The claim of an alert message's ignore: the first press counts, a repeat does not."""
    return f"incident:alert_ignore:{channel_id}:{message_ts}"


async def _count_ignore(
    records: RecordStore, claims_store: ConditionalWriteStore, webhook_id: str, channel_id: str, message_ts: str
) -> None:
    """Count one acknowledgement for the message's first ignore; a lost claim or failed count is logged."""
    claims = providers.claims(claims_store)
    key = ignore_claim_key(channel_id, message_ts)
    claimed = await claims.claim(key)
    if claimed.result is not ClaimResult.NEW or claimed.claim_token is None:
        logger.info("incident_alert_ignore_already_counted", channel_id=channel_id, result=claimed.result.value)
        return
    counted = await providers.alert_acknowledgements(records).increment(webhook_id)
    if not counted.is_success:
        logger.warning(
            "incident_alert_acknowledgement_failed",
            webhook_id=webhook_id,
            operation_status=counted.status.value,
            error_code=counted.error_code,
        )
    await claims.complete(key, {"counted": counted.is_success}, claimed.claim_token)


async def _warn_followers(declared: Declared, chat: ChatSurface | None, policy: LanguagePolicy) -> None:
    """Post the resources warning in the incident channel when a step after the record failed."""
    conversation = declared.incident.conversation
    failed = [stage for stage in _FOLLOWER_STAGES if getattr(declared, stage).outcome is StageOutcome.FAILED]
    if chat is None or conversation is None or not failed:
        return
    logger.warning("incident_declare_followers_failed", incident_id=declared.incident.id, stages=failed)
    warning = MultilingualText.of(shared_languages(policy, conversation), lambda language: _t("reply.resources_failed", language))
    posted = await chat.conversations.post(conversation, warning)
    if not posted.is_success:
        logger.warning("incident_declare_warning_failed", incident_id=declared.incident.id, error_code=posted.error_code)


def _open_form(reply: SlackReplySender, trigger_id: str, *, name: str, locale: str, metadata: str) -> bool:
    """Open the loading view on ``trigger_id``, then replace it with the form; False when the view did not open."""
    if not trigger_id:
        return False
    opened = reply.open_view(trigger_id=trigger_id, view=build_loading_view(locale))
    if not opened.is_success or opened.data is None:
        return False
    form = build_declare_view(
        name=name, placements=_placements(), locale=locale, private_metadata=metadata, handbook_url=_handbook_url()
    )
    updated = reply.update_view(view_id=opened.data, view=form)
    if not updated.is_success:
        logger.warning("incident_declare_form_update_failed", error_code=updated.error_code)
    return updated.is_success


def _placements() -> tuple[ReportPlacement, ...]:
    """The report placements the form offers; none when they cannot be listed (the default folder is used)."""
    listed = asyncio.run(providers.incident_report().list_placements())
    if not listed.is_success or listed.data is None:
        logger.warning("incident_declare_placements_unavailable", error_code=listed.error_code)
        return ()
    return listed.data


def _handbook_url() -> str:
    return f"https://docs.google.com/document/d/{get_incident_response_settings().handbook_id}"


def _name_error(name: str, languages: Sequence[str]) -> str | None:
    """The name field's error in every instance language, or ``None`` for a valid name."""
    if len(name) > _NAME_MAX:
        key = "modal.name_too_long"
    elif not _NAME.match(name):
        key = "modal.name_invalid"
    else:
        return None
    return " // ".join(_t(key, language) for language in languages)


def _values(view: Mapping[str, Any], block_id: str) -> Mapping[str, Any]:
    return ((view.get("state") or {}).get("values") or {}).get(block_id, {}).get(block_id) or {}


def _input_value(view: Mapping[str, Any], block_id: str) -> str | None:
    value = _values(view, block_id).get("value")
    return str(value) if value is not None else None


def _selected(view: Mapping[str, Any], block_id: str) -> str | None:
    selected = _values(view, block_id).get("selected_option") or {}
    value = selected.get("value")
    return str(value) if value else None


def _placement(view: Mapping[str, Any], google_tenant: str | None) -> ReportPlacement | None:
    """The chosen product's placement, from the option's folder id and label; ``None`` when none was offered."""
    selected = _values(view, PRODUCT_BLOCK_ID).get("selected_option") or {}
    folder_id = selected.get("value")
    label = (selected.get("text") or {}).get("text")
    if not folder_id or not label or not google_tenant:
        return None
    return ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=google_tenant, vendor_id=str(folder_id), label=str(label))


def _severity(value: str | None) -> Severity | None:
    """``sev-<n>`` as its severity; ``none`` or anything else is not rated (SEV0 is 0, so never tested for truth)."""
    if value is None or not value.startswith("sev-"):
        return None
    try:
        return Severity(int(value.removeprefix("sev-")))
    except ValueError:
        return None


def _source_alert(view: Mapping[str, Any], slack_tenant: str | None, reply: SlackReplySender) -> MessageReference | None:
    """The alert named by the form's private metadata, with its permalink when Slack gives one."""
    metadata = _parse(view.get("private_metadata"))
    channel_id, message_ts = metadata.get("source_channel_id"), metadata.get("source_message_ts")
    if not channel_id or not message_ts or not slack_tenant:
        return None
    link = reply.permalink(channel_id=str(channel_id), message_ts=str(message_ts))
    if not link.is_success:
        logger.warning("incident_declare_source_alert_permalink_failed", channel_id=channel_id, error_code=link.error_code)
    return MessageReference(
        system=WorkplaceSystem.SLACK,
        tenant=slack_tenant,
        conversation_id=str(channel_id),
        message_id=str(message_ts),
        url=link.data if link.is_success else None,
    )


def _alert_location(body: Mapping[str, Any]) -> tuple[str, str]:
    """The alert message's channel and timestamp, from the payload or its container."""
    container = body.get("container") or {}
    channel_id = (body.get("channel") or {}).get("id") or container.get("channel_id") or ""
    message_ts = body.get("message_ts") or container.get("message_ts") or ""
    return str(channel_id), str(message_ts)


def _ignored(user_id: str, languages: Sequence[str]) -> str:
    key = "incident_response.alert.ignored"
    return MultilingualText.of(languages, lambda language: t(key, language, key, user=f"<@{user_id}>")).plain_text()


def _replace_buttons(
    reply: SlackReplySender,
    body: Mapping[str, Any],
    channel_id: str,
    message_ts: str,
    text: str,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Rewrite the alert without its buttons attachment, adding who ignored it; rich_text blocks are cleared."""
    original = body.get("original_message") or {}
    attachments = list(original.get("attachments") or [])
    buttons = next(
        (i for i, attachment in enumerate(attachments) if attachment.get("callback_id") == LEGACY_ALERT_BUTTONS_CALLBACK_ID),
        len(attachments) - 1,
    )
    kept = [
        {key: value for key, value in attachment.items() if key in _WRITABLE_ATTACHMENT_KEYS}
        for i, attachment in enumerate(attachments)
        if i != buttons
    ]
    kept.append({"color": _IGNORED_COLOR, "fallback": text, "text": text})
    # rich_text blocks are only accepted from first-party Slack clients; chat.update from a bot rejects them.
    blocks = list(original.get("blocks") or [])
    if any(block.get("type") == "rich_text" for block in blocks):
        blocks = []
    updated = reply.update_message(
        channel_id=channel_id,
        ts=str(original.get("ts") or message_ts),
        text=str(original.get("text") or ""),
        attachments=kept,
        blocks=blocks,
    )
    if not updated.is_success:
        log.warning("incident_alert_buttons_replace_failed", error_code=updated.error_code)


def _direct(reply: SlackReplySender, user_id: str, text: str, log: structlog.stdlib.BoundLogger) -> None:
    told = reply.post_message(channel_id=user_id, text=text)
    if not told.is_success:
        log.warning("incident_declare_direct_message_failed", error_code=told.error_code)


def _parse(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
    except TypeError, ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the declare catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{DECLARE_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)
