"""Slack entry point for the incident response subdomain: ``/sre incident status`` and ``status update``, and the roles commands.

Registers ``status`` as a child of ``sre.incident`` and ``update`` under it.
``status update <status>`` changes the status of the channel's incident through
``change_status`` (the record first, then the report status line, the list
projection and the channel notice) and answers the invoker privately with one
reply: the outcome and a line for each follower write that was skipped or failed.

``status`` alone, ``status show`` and any other text answer the command's help;
a bare valid status (``status Closed``, the form retired after 2025-11-01)
answers a pointer to ``status update`` and changes nothing. TASK-145.13 deletes
the pointer with the legacy contract.

``register`` also registers the roles commands and modal (``slack_roles.py``), ``close``
and the archive button (``slack_archive.py``), and ``show`` with its update modal
(``slack_show.py``).

A handler opens one service scope, builds the ``IncidentStore`` there from the
resolved ``RecordStore`` and the configured systems, and runs the service in one
event loop (``asyncio.run``, the sync Bolt edge). The report, list and
conversation ports come from ``response/providers.py``. Registration reads the
configured systems once: without a Slack tenant nothing is registered and one
startup event names ``[slack.tenant]``. Every string goes through the
``incident_response`` catalogue: the channel notice in the conversation's
shared languages, the replies in the invoker's reply languages
(decisions/languages.md).
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog

from contracts.languages import MultilingualText
from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.services import ServiceScopeOpener
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.api import translate as t
from features.incident.response import providers
from features.incident.response.entrypoints.scope import incident_scope, language_policy, shared_languages
from features.incident.response.entrypoints.slack_archive import register_archive
from features.incident.response.entrypoints.slack_roles import register_roles
from features.incident.response.entrypoints.slack_show import register_show
from features.incident.response.service.status import StageOutcome, StageResult, StatusChange, change_status

logger = structlog.get_logger()

STATUS_DOMAIN = "incident_response.status"

# Listed in the order responders know them from the legacy command.
_LISTED_STATUSES = (
    IncidentStatus.IN_PROGRESS,
    IncidentStatus.OPEN,
    IncidentStatus.READY_TO_BE_REVIEWED,
    IncidentStatus.REVIEWED,
    IncidentStatus.CLOSED,
)


def register(registrar: SlackCommandRegistrar) -> None:
    """Register ``/sre incident status`` and ``/sre incident status update``.

    Registers nothing when Slack is not a configured system, since no
    conversation could be resolved to an incident.

    Args:
        registrar: Slack command registrar.
    """
    scopes = registrar.service_scopes
    with scopes.create_scope() as services:
        slack_configured = WorkplaceSystem.SLACK in services.get(ConfiguredSystems).tenants()
    if not slack_configured:
        logger.warning("incident_response_registration_skipped", reason="slack_not_configured", setting="[slack.tenant]")
        return

    def _dispatch_status(payload: CommandPayload) -> CommandResponse:
        return handle_status_command(payload, scopes)

    def _dispatch_status_update(payload: CommandPayload) -> CommandResponse:
        return handle_status_update_command(payload, scopes)

    registrar.register_command(
        command="status",
        handler=_dispatch_status,
        parent="sre.incident",
        description="Change this incident's status",
        description_key=f"{STATUS_DOMAIN}.description",
        usage_hint="update <status>",
        examples=["update Closed"],
        example_keys=[f"{STATUS_DOMAIN}.examples.default"],
    )
    registrar.register_command(
        command="update",
        handler=_dispatch_status_update,
        parent="sre.incident.status",
        description="Set this incident's status",
        description_key=f"{STATUS_DOMAIN}.update.description",
        usage_hint="<status>",
        examples=["Ready to be Reviewed"],
        example_keys=[f"{STATUS_DOMAIN}.update.examples.default"],
    )
    register_roles(registrar, scopes)
    register_archive(registrar, scopes)
    register_show(registrar, scopes)


def handle_status_command(payload: CommandPayload, scopes: ServiceScopeOpener) -> CommandResponse:
    """Answer ``/sre incident status`` without a known subcommand: a pointer for a bare status, otherwise the help.

    Args:
        payload: Command payload; ``text`` is what followed ``status``.
        scopes: Opens the service scope the language policy is resolved in.

    Returns:
        An ephemeral pointer to ``status update`` when the text is a valid
        status, the command's help otherwise. Nothing is read or written.
    """
    languages = language_policy(scopes).reply_languages(payload.user_locale)
    text = payload.text.strip()
    if text in set(IncidentStatus):
        logger.info("incident_status_bare_form_answered", user_id=payload.user_id, channel_id=payload.channel_id)
        return _reply(_render(languages, "bare_status", status=text))
    return _reply(_render(languages, "help", statuses=_statuses()))


def handle_status_update_command(payload: CommandPayload, scopes: ServiceScopeOpener) -> CommandResponse:
    """Handle ``/sre incident status update <status>`` by changing the status of the channel's incident.

    Args:
        payload: Command payload; ``text`` is the status, which may hold spaces.
        scopes: Opens the service scope the incident store is built in.

    Returns:
        One ephemeral reply in the invoker's reply languages: the outcome and a
        line per skipped or failed follower write, or why nothing was changed.
    """
    policy = language_policy(scopes)
    languages = policy.reply_languages(payload.user_locale)
    text = payload.text.strip()
    if not text:
        return _reply(_render(languages, "missing"))
    if text not in set(IncidentStatus):
        return _reply(_render(languages, "invalid", statuses=_statuses()))
    if not payload.channel_id:
        return _reply(_render(languages, "not_an_incident"))
    status = IncidentStatus(text)
    user = f"<@{payload.user_id}>"

    with incident_scope(scopes, payload.channel_id) as (incidents, conversation):
        notice = MultilingualText.of(
            shared_languages(policy, conversation), lambda language: _t("notice", language, user=user, status=status.value)
        )
        result = asyncio.run(
            change_status(
                incidents,
                providers.incident_report(),
                providers.incident_list_projection(),
                providers.incident_conversation(),
                conversation,
                status,
                at=datetime.now(UTC),
                notice=notice,
            )
        )
    if not result.is_success or result.data is None:
        logger.warning(
            "incident_status_update_refused",
            user_id=payload.user_id,
            channel_id=payload.channel_id,
            operation_status=result.status.value,
            error_code=result.error_code,
        )
        return _reply(_refusal(result, languages))
    return _reply(_outcome(result.data, languages))


def _refusal(result: OperationResult[StatusChange], languages: Sequence[str]) -> str:
    match result.error_code:
        case ErrorCode.NOT_AN_INCIDENT:
            return _render(languages, "not_an_incident")
        case ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION:
            return _render(languages, "ambiguous")
        case ErrorCode.INCIDENT_RECORD_CONFLICT:
            return _render(languages, "conflict")
        case ErrorCode.INCIDENT_RECORD_UNREADABLE:
            return _render(languages, "unreadable")
    return _render(languages, "unavailable")


def _outcome(change: StatusChange, languages: Sequence[str]) -> str:
    lines = [_render(languages, "updated", status=change.incident.status.value)]
    lines += _stage_line("report", change.report, languages)
    lines += _stage_line("projection", change.projection, languages)
    lines += _stage_line("channel", change.channel, languages)
    return "\n".join(lines)


# The follower outcomes the reply names; a done write needs no line, and the list write is never skipped.
_STAGE_LINES = frozenset(
    {
        ("report", StageOutcome.SKIPPED),
        ("report", StageOutcome.FAILED),
        ("projection", StageOutcome.FAILED),
        ("channel", StageOutcome.SKIPPED),
        ("channel", StageOutcome.FAILED),
    }
)


def _stage_line(stage: str, result: StageResult, languages: Sequence[str]) -> list[str]:
    if (stage, result.outcome) not in _STAGE_LINES:
        return []
    return [_render(languages, f"{stage}_{result.outcome.value}")]


def _statuses() -> str:
    return ", ".join(status.value for status in _LISTED_STATUSES)


def _render(languages: Sequence[str], key: str, **variables: str) -> str:
    """Translate ``key`` in each reply language, one line each, for a private reply."""
    return "\n".join(_t(key, language, **variables) for language in languages)


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the status catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{STATUS_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)


def _reply(message: str) -> CommandResponse:
    return CommandResponse(message=message, ephemeral=True)
