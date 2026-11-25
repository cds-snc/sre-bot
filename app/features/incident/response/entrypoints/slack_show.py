"""Slack entry point for ``/sre incident show`` and its update modal.

``show`` opens the information modal on the channel's incident (slack_show_views.py):
its links, five roles (``read_incident_roles``: the record, else the report's legacy
Drive properties), severity, status, security flag and times. The command answers in
the invoker's language (matched to a supported one by the language policy), which the
modal carries in its private metadata for the rest of the flow.

An Update button acks, reads the incident again and pushes the field's modal over the
information modal. Its submission acks first (the pushed view closes), then writes the
record, the commit point: the status through ``change_status`` (then the report status
line, the list row and the notice), any other field through ``update_fields`` (then
the notice). The notice is posted to the incident's channel, a shared conversation, in
the instance languages and order (decisions/languages.md); a refusal, a lost guard and a follower that
failed or was skipped are told to the submitter privately in the modal's locale.
Finally the information modal is refreshed from the incident as written; a refresh
that fails because the user closed it is expected and only logged.

Handlers open one service scope and run the services in one event loop
(``asyncio.run``, the sync Bolt edge). Views and private lines go through the reply
sender, never the raw Slack client.
"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from contracts.languages import LanguagePolicy, MultilingualText
from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.services import ServiceScopeOpener
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from features.incident.common.vocabulary import IncidentRole, IncidentStatus, Severity
from features.incident.core.api import (
    ConversationReference,
    Incident,
    IncidentChanges,
    IncidentStore,
    find_incident_for_conversation,
    read_incident_roles,
)
from features.incident.core.api import translate as t
from features.incident.response import providers
from features.incident.response.entrypoints.scope import incident_scope, language_policy, shared_languages
from features.incident.response.entrypoints.slack_show_views import (
    FIELD_CALLBACK_ID,
    SELECT_BLOCK_ID,
    SHOW_DOMAIN,
    TIME_ATTRIBUTES,
    UPDATE_ACTION_ID,
    VALUE_ACTION_ID,
    WHEN_BLOCK_ID,
    Field,
    build_field_view,
    build_show_view,
    instant_text,
    option_text,
)
from features.incident.response.service.fields import update_fields
from features.incident.response.service.status import StageOutcome, StageResult, change_status

logger = structlog.get_logger()

STATUS_DOMAIN = "incident_response.status"


@dataclass(frozen=True)
class _Shown:
    """What the information modal shows: the incident, its roles and its links."""

    incident: Incident
    roles: Mapping[IncidentRole, str | None]
    report_link: str | None
    call_link: str | None


@dataclass(frozen=True)
class _Submitted:
    """A committed field change: the refreshed modal's content and the followers that need a private line."""

    shown: _Shown
    lines: tuple[str, ...]


def register_show(registrar: SlackCommandRegistrar, scopes: ServiceScopeOpener) -> None:
    """Register ``/sre incident show``, its Update buttons and the update modal's submission.

    Args:
        registrar: Slack command registrar.
        scopes: Opens the service scope the incident store is built in.
    """

    def _dispatch_show(payload: CommandPayload) -> CommandResponse:
        return handle_show_command(payload, registrar.reply, scopes)

    def _press(ack: Callable[..., Any], body: dict[str, Any]) -> None:
        handle_update_press(ack, body, registrar.reply, scopes)

    def _submit(ack: Callable[..., Any], body: dict[str, Any]) -> None:
        handle_update_submission(ack, body, registrar.reply, scopes)

    registrar.register_command(
        command="show",
        handler=_dispatch_show,
        parent="sre.incident",
        description="Show this incident's information",
        description_key=f"{SHOW_DOMAIN}.description",
        usage_hint="",
        examples=[""],
        example_keys=[f"{SHOW_DOMAIN}.examples.default"],
    )
    registrar.register_block_action(UPDATE_ACTION_ID, _press)
    registrar.register_view_submission(FIELD_CALLBACK_ID, _submit)


def handle_show_command(payload: CommandPayload, reply: SlackReplySender, scopes: ServiceScopeOpener) -> CommandResponse:
    """Handle ``/sre incident show`` by opening the information modal on the channel's incident.

    Args:
        payload: Command payload; ``platform_metadata["trigger_id"]`` opens the view.
        reply: Interface used to open the modal.
        scopes: Opens the service scope the incident store is built in.

    Returns:
        An empty ephemeral response once the modal opened; a private notice in
        the invoker's locale when the channel is no incident, the record can't
        be read or the view could not open.
    """
    locales = language_policy(scopes).reply_languages(payload.user_locale)
    log = logger.bind(command="incident_show", user_id=payload.user_id, channel_id=payload.channel_id)
    trigger_id = str(payload.platform_metadata.get("trigger_id", ""))
    if not payload.channel_id:
        return _reply(_render(locales, "not_an_incident"))
    if not trigger_id:
        log.warning("incident_show_no_trigger")
        return _reply(_render(locales, "open_failed"))

    shown = _read_shown(scopes, payload.channel_id)
    if not shown.is_success or shown.data is None:
        log.warning("incident_show_refused", operation_status=shown.status.value, error_code=shown.error_code)
        return _reply(_refusal(shown, locales))

    opened = reply.open_view(trigger_id=trigger_id, view=_show_view(shown.data, locales[0], payload.channel_id))
    if not opened.is_success:
        log.warning("incident_show_open_failed", error=opened.message, error_code=opened.error_code)
        return _reply(_render(locales, "open_failed"))
    log.info("incident_show_opened", incident_id=shown.data.incident.id)
    return CommandResponse(message="", ephemeral=True)


def handle_update_press(
    ack: Callable[..., Any], body: dict[str, Any], reply: SlackReplySender, scopes: ServiceScopeOpener
) -> None:
    """Handle an Update button of the information modal: push the field's modal on the current value.

    Args:
        ack: Bolt ack callable, called first.
        body: The ``block_actions`` payload; the button's value names the field.
        reply: Interface used to push the modal and tell the presser privately.
        scopes: Opens the service scope the incident store is built in.
    """
    ack()
    metadata = _metadata(body)
    channel_id = str(metadata.get("channel_id", ""))
    locales = _locales(language_policy(scopes), metadata)
    user_id = str((body.get("user") or {}).get("id", ""))
    value = str(((body.get("actions") or [{}])[0]).get("value", ""))
    log = logger.bind(operation="incident_update_press", user_id=user_id, channel_id=channel_id, field=value)
    if value not in set(Field):
        log.warning("incident_update_press_unknown_field")
        return

    with incident_scope(scopes, channel_id) as (incidents, conversation):
        found = asyncio.run(find_incident_for_conversation(incidents, conversation))
    if not found.is_success or found.data is None:
        log.warning("incident_update_press_refused", operation_status=found.status.value, error_code=found.error_code)
        _tell(reply, channel_id, user_id, _refusal(found, locales), log)
        return

    view = build_field_view(found.data, Field(value), locale=locales[0], channel_id=channel_id)
    pushed = reply.push_view(trigger_id=str(body.get("trigger_id", "")), view=view)
    if not pushed.is_success:
        log.warning("incident_update_push_failed", error=pushed.message, error_code=pushed.error_code)
        _tell(reply, channel_id, user_id, _render(locales, "push_failed"), log)


def handle_update_submission(
    ack: Callable[..., Any], body: dict[str, Any], reply: SlackReplySender, scopes: ServiceScopeOpener
) -> None:
    """Handle the update modal's submission: write the field, announce it, refresh the information modal.

    Args:
        ack: Bolt ack callable, called first; it closes the pushed view.
        body: The ``view_submission`` payload; the view's metadata names the field and its state the value.
        reply: Interface used to refresh the information modal and tell the submitter privately.
        scopes: Opens the service scope the incident store is built in.
    """
    ack()
    view = body.get("view") or {}
    metadata = _parse(view.get("private_metadata"))
    channel_id = str(metadata.get("channel_id", ""))
    policy = language_policy(scopes)
    locales = _locales(policy, metadata)
    user_id = str((body.get("user") or {}).get("id", ""))
    field_name = str(metadata.get("field", ""))
    log = logger.bind(operation="incident_update_submission", user_id=user_id, channel_id=channel_id, field=field_name)
    picked = _picked(view)
    if field_name not in set(Field) or picked is None:
        log.warning("incident_update_submission_unreadable")
        return
    field = Field(field_name)

    with incident_scope(scopes, channel_id) as (incidents, conversation):
        notice_languages = shared_languages(policy, conversation)
        result = asyncio.run(_submit(incidents, conversation, field, picked, user_id, locales, notice_languages))
    if not result.is_success or result.data is None:
        log.warning("incident_update_refused", operation_status=result.status.value, error_code=result.error_code)
        _tell(reply, channel_id, user_id, _refusal(result, locales), log)
        return
    if result.data.lines:
        _tell(reply, channel_id, user_id, "\n".join(result.data.lines), log)

    root_view_id = str(view.get("root_view_id", ""))
    refreshed = reply.update_view(view_id=root_view_id, view=_show_view(result.data.shown, locales[0], channel_id))
    if not refreshed.is_success:
        # The user closed the information modal: Slack answers not_found, an expected outcome.
        level = log.info if refreshed.error_code == "not_found" else log.warning
        level("incident_update_refresh_failed", view_id=root_view_id, error_code=refreshed.error_code)


# Write the field, then read what the refreshed information modal shows.
async def _submit(
    incidents: IncidentStore,
    conversation: ConversationReference,
    field: Field,
    picked: str | int,
    user_id: str,
    locales: Sequence[str],
    notice_languages: Sequence[str],
) -> OperationResult[_Submitted]:
    at = datetime.now(UTC)
    if field is Field.STATUS:
        status = IncidentStatus(str(picked))
        changed_status = await change_status(
            incidents,
            providers.incident_report(),
            providers.incident_list_projection(),
            providers.incident_conversation(),
            conversation,
            status,
            at=at,
            notice=_notice(user_id, field, status.value, notice_languages),
        )
        if not changed_status.is_success or changed_status.data is None:
            return _carry(changed_status)
        incident = changed_status.data.incident
        lines = _status_lines(changed_status.data.report, changed_status.data.projection, changed_status.data.channel, locales)
    else:
        changes, shown_value = _changes(field, picked)
        changed = await update_fields(
            incidents,
            providers.incident_conversation(),
            conversation,
            changes,
            by=user_id,
            at=at,
            notice=_notice(user_id, field, shown_value, notice_languages),
        )
        if not changed.is_success or changed.data is None:
            return _carry(changed)
        incident = changed.data.incident
        lines = _channel_lines(changed.data.channel, locales)
    return OperationResult.success(_Submitted(shown=await _shown(incident), lines=tuple(lines)))


def _changes(field: Field, picked: str | int) -> tuple[IncidentChanges, str | datetime]:
    """The record change a submitted value makes, and the value the notice names (a time as its instant)."""
    if field in TIME_ATTRIBUTES:
        when = datetime.fromtimestamp(int(picked), tz=UTC)
        match field:
            case Field.DETECTION_TIME:
                return IncidentChanges(detected_at=when), when
            case Field.START_IMPACT_TIME:
                return IncidentChanges(impact_started_at=when), when
        return IncidentChanges(impact_ended_at=when), when
    if field is Field.SECURITY_INCIDENT:
        return IncidentChanges(security_incident=picked == "yes"), str(picked)
    severity = None if picked == "none" else Severity(int(str(picked).removeprefix("sev-")))
    return IncidentChanges(severity=severity), str(picked)


def _notice(user_id: str, field: Field, value: str | datetime, languages: Sequence[str]) -> MultilingualText:
    """The notice posted to the incident's channel, in the instance languages and order (decisions/languages.md)."""

    def line(locale: str) -> str:
        shown = instant_text(value) if isinstance(value, datetime) else option_text(field, value, locale)
        return _t("notice", locale, user=f"<@{user_id}>", field=field.value, value=shown)

    return MultilingualText.of(languages, line)


def _read_shown(scopes: ServiceScopeOpener, channel_id: str) -> OperationResult[_Shown]:
    with incident_scope(scopes, channel_id) as (incidents, conversation):
        return asyncio.run(_find_shown(incidents, conversation))


async def _find_shown(incidents: IncidentStore, conversation: ConversationReference) -> OperationResult[_Shown]:
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return _carry(found)
    return OperationResult.success(await _shown(found.data))


# Read the incident's roles and links; the stored url is the adapters' hint.
async def _shown(incident: Incident) -> _Shown:
    roles = await read_incident_roles(incident, providers.legacy_roles_reader())
    report_link = providers.incident_report().link(incident.report) if incident.report is not None else None
    call_link = providers.video_call().link(incident.video_call) if incident.video_call is not None else None
    return _Shown(incident=incident, roles=roles, report_link=report_link, call_link=call_link)


def _show_view(shown: _Shown, locale: str, channel_id: str) -> dict[str, Any]:
    return build_show_view(
        shown.incident,
        shown.roles,
        report_link=shown.report_link,
        call_link=shown.call_link,
        locale=locale,
        channel_id=channel_id,
    )


def _picked(view: Mapping[str, Any]) -> str | int | None:
    """The submitted value: the selected option's value, or the picked instant in UNIX seconds."""
    values = (view.get("state") or {}).get("values") or {}
    selected = ((values.get(SELECT_BLOCK_ID) or {}).get(VALUE_ACTION_ID) or {}).get("selected_option") or {}
    if selected.get("value"):
        return str(selected["value"])
    instant = ((values.get(WHEN_BLOCK_ID) or {}).get(VALUE_ACTION_ID) or {}).get("selected_date_time")
    return int(instant) if instant is not None else None


def _status_lines(report: StageResult, projection: StageResult, channel: StageResult, locales: Sequence[str]) -> list[str]:
    """The status reply's lines for a report, list or channel write that was skipped or failed."""
    keys = []
    if report.outcome is not StageOutcome.DONE:
        keys.append(f"report_{report.outcome.value}")
    if projection.outcome is StageOutcome.FAILED:
        keys.append("projection_failed")
    if channel.outcome is not StageOutcome.DONE:
        keys.append(f"channel_{channel.outcome.value}")
    return [t(f"{STATUS_DOMAIN}.{key}", locale, f"{STATUS_DOMAIN}.{key}") for key in keys for locale in locales]


def _channel_lines(channel: StageResult, locales: Sequence[str]) -> list[str]:
    if channel.outcome is StageOutcome.DONE:
        return []
    return [_t(f"channel_{channel.outcome.value}", locale) for locale in locales]


def _refusal(result: OperationResult[Any], locales: Sequence[str]) -> str:
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


def _tell(reply: SlackReplySender, channel_id: str, user_id: str, text: str, log: structlog.stdlib.BoundLogger) -> None:
    told = reply.post_ephemeral(channel_id=channel_id, user_id=user_id, text=text)
    if not told.is_success:
        log.warning("incident_update_private_line_failed", error_code=told.error_code)


def _carry[T](result: OperationResult[Any]) -> OperationResult[T]:
    return OperationResult.error(
        status=result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )


def _metadata(body: Mapping[str, Any]) -> dict[str, Any]:
    return _parse((body.get("view") or {}).get("private_metadata"))


def _parse(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
    except TypeError, ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _locales(policy: LanguagePolicy, metadata: Mapping[str, Any]) -> tuple[str, ...]:
    """The reply languages for the modal's locale; a view that names none is answered in the instance languages."""
    locale = metadata.get("locale")
    return policy.reply_languages(str(locale) if locale else None)


def _render(locales: Sequence[str], key: str) -> str:
    return "\n".join(_t(key, locale) for locale in locales)


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the show catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{SHOW_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)


def _reply(message: str) -> CommandResponse:
    return CommandResponse(message=message, ephemeral=True)
