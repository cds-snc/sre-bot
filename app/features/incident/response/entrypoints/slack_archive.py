"""Slack entry points for the archive: ``/sre incident close`` and the stale notice's archive button.

Both call ``archive_incident`` (service/archive.py) at the sync Bolt edge with
``asyncio.run``. Both post their channel notices in the channel's shared
languages, in order (decisions/languages.md). The command replies in the
invoker's language like ``status update``: the outcome and a line per skipped
or failed stage. The button is the
legacy attachment ``archive_channel``, registered as ``incident.response.archive``
with the alias scoped to its ``archive`` value (decisions/transport-slack.md), so
``ignore`` and ``schedule_retro`` still reach the legacy listener. A button press
names no locale, so its replies are in the instance languages too; it replies only on a refusal or a
skipped or failed stage, since the channel notices announce a success.
"""

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog

from contracts.languages import LanguagePolicy, MultilingualText
from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.services import ServiceScopeOpener
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.api import translate as t
from features.incident.response import providers
from features.incident.response.entrypoints.scope import incident_scope, language_policy, shared_languages
from features.incident.response.service.archive import Archive, archive_incident
from features.incident.response.service.status import StageOutcome

logger = structlog.get_logger()

ARCHIVE_DOMAIN = "incident_response.archive"
STATUS_DOMAIN = "incident_response.status"
ARCHIVE_CALLBACK_ID = "incident.response.archive"
LEGACY_ARCHIVE_VALUES = {"archive_channel": ("archive",)}


def register_archive(registrar: SlackCommandRegistrar, scopes: ServiceScopeOpener) -> None:
    """Register ``/sre incident close`` and the archive button of the stale-channel notice.

    Args:
        registrar: Slack command registrar.
        scopes: Opens the service scope the incident store is built in.
    """

    def _dispatch_close(payload: CommandPayload) -> CommandResponse:
        return handle_close_command(payload, scopes)

    def _press(ack: Callable[..., Any], body: dict[str, Any], client: Any, respond: Callable[..., Any]) -> None:
        handle_archive_press(ack, body, client, respond, scopes)

    registrar.register_command(
        command="close",
        handler=_dispatch_close,
        parent="sre.incident",
        description="Close this incident and archive its channel",
        description_key=f"{ARCHIVE_DOMAIN}.description",
        usage_hint="",
        examples=[""],
        example_keys=[f"{ARCHIVE_DOMAIN}.examples.default"],
    )
    registrar.register_attachment_action(ARCHIVE_CALLBACK_ID, _press, legacy_callback_values=LEGACY_ARCHIVE_VALUES)


def handle_close_command(payload: CommandPayload, scopes: ServiceScopeOpener) -> CommandResponse:
    """Handle ``/sre incident close`` by closing the channel's incident and archiving the channel.

    Args:
        payload: Command payload; the channel and the invoker.
        scopes: Opens the service scope the incident store is built in.

    Returns:
        One ephemeral reply in the invoker's locale: the outcome and a line per
        skipped or failed stage, or why nothing was changed.
    """
    policy = language_policy(scopes)
    locales = policy.reply_languages(payload.user_locale)
    if not payload.channel_id:
        return _reply(_render(locales, "not_an_incident"))
    result = _archive(scopes, payload.channel_id, payload.user_id, policy)
    if not result.is_success or result.data is None:
        logger.warning(
            "incident_close_refused",
            user_id=payload.user_id,
            channel_id=payload.channel_id,
            operation_status=result.status.value,
            error_code=result.error_code,
        )
        return _reply(_refusal(result, locales))
    return _reply("\n".join([_outcome_line(result.data, locales), *_stage_lines(result.data, locales)]))


def handle_archive_press(
    ack: Callable[..., Any], body: dict[str, Any], client: Any, respond: Callable[..., Any], scopes: ServiceScopeOpener
) -> None:
    """Handle the stale notice's archive button: ack, then close the incident and archive the channel.

    Args:
        ack: Bolt ack callable, called first.
        body: The ``interactive_message`` payload; carries the channel and the presser.
        client: Bolt Slack web client, used for the presser's private refusal.
        respond: Bolt ``response_url`` sender, used for every other reply.
        scopes: Opens the service scope the incident store is built in.
    """
    ack()
    channel_id = str((body.get("channel") or {}).get("id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    policy = language_policy(scopes)
    replies = policy.reply_languages(None)
    result = _archive(scopes, channel_id, user_id, policy)
    if not result.is_success or result.data is None:
        logger.warning(
            "incident_archive_refused",
            user_id=user_id,
            channel_id=channel_id,
            operation_status=result.status.value,
            error_code=result.error_code,
        )
        if result.error_code == ErrorCode.NOT_AN_INCIDENT:
            client.chat_postEphemeral(channel=channel_id, user=user_id, text=_refusal(result, replies))
        else:
            respond(_refusal(result, replies))
        return
    lines = _stage_lines(result.data, replies)
    if lines:
        respond("\n".join(lines))


def _archive(scopes: ServiceScopeOpener, channel_id: str, user_id: str, policy: LanguagePolicy) -> OperationResult[Archive]:
    """Close and archive; the channel notices are in the channel's shared languages."""
    user = f"<@{user_id}>"
    with incident_scope(scopes, channel_id) as (incidents, conversation):
        languages = shared_languages(policy, conversation)
        return asyncio.run(
            archive_incident(
                incidents,
                providers.incident_report(),
                providers.incident_list_projection(),
                providers.incident_conversation(),
                providers.archive_event_sink(),
                conversation,
                user_id=user_id,
                at=datetime.now(UTC),
                status_notice=MultilingualText.of(
                    languages,
                    lambda locale: _t("notice", locale, domain=STATUS_DOMAIN, user=user, status=IncidentStatus.CLOSED.value),
                ),
                archived_notice=MultilingualText.of(languages, lambda locale: _t("notice", locale, user=user)),
            )
        )


def _refusal(result: OperationResult[Archive], locales: Sequence[str]) -> str:
    match result.error_code:
        case ErrorCode.NOT_AN_INCIDENT:
            return _render(locales, "not_an_incident")
        case ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION:
            return _render(locales, "ambiguous")
        case ErrorCode.INCIDENT_RECORD_CONFLICT:
            return _render(locales, "conflict")
        case ErrorCode.INCIDENT_RECORD_UNREADABLE:
            return _render(locales, "unreadable")
    return _render(locales, "unavailable")


def _outcome_line(archive: Archive, locales: Sequence[str]) -> str:
    if archive.archive.outcome is StageOutcome.DONE:
        return _render(locales, "archived")
    return _render(locales, "updated", domain=STATUS_DOMAIN, status=archive.change.incident.status.value)


def _stage_lines(archive: Archive, locales: Sequence[str]) -> list[str]:
    """One line per skipped or failed stage; a channel the bot could not join is named once, by the join line."""
    change = archive.change
    lines: list[str] = []
    if change.report.outcome is StageOutcome.SKIPPED:
        lines.append(_render(locales, "report_skipped", domain=STATUS_DOMAIN))
    if change.report.outcome is StageOutcome.FAILED:
        lines.append(_render(locales, "report_failed", domain=STATUS_DOMAIN))
    if change.projection.outcome is StageOutcome.FAILED:
        lines.append(_render(locales, "projection_failed", domain=STATUS_DOMAIN))
    if archive.join.outcome is StageOutcome.FAILED:
        lines.append(_render(locales, "join_failed"))
        return lines
    if change.channel.outcome is StageOutcome.FAILED:
        lines.append(_render(locales, "channel_failed", domain=STATUS_DOMAIN))
    if archive.notice.outcome is StageOutcome.FAILED:
        lines.append(_render(locales, "notice_failed"))
    if archive.archive.outcome is StageOutcome.FAILED:
        lines.append(_render(locales, "archive_failed"))
    return lines


def _render(locales: Sequence[str], key: str, *, domain: str = ARCHIVE_DOMAIN, **variables: str) -> str:
    """Translate ``key`` in each reply language, one line each, for a private reply."""
    return "\n".join(_t(key, locale, domain=domain, **variables) for locale in locales)


def _t(key: str, locale: str, *, domain: str = ARCHIVE_DOMAIN, **variables: str) -> str:
    """Translate ``key``; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{domain}.{key}"
    return t(full_key, locale, full_key, **variables)


def _reply(message: str) -> CommandResponse:
    return CommandResponse(message=message, ephemeral=True)
