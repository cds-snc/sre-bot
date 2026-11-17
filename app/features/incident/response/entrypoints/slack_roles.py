"""Slack entry point for ``/sre incident roles manage`` and its modal.

``roles`` is a grouping node: the bare command and ``roles show`` answer its
generated help. ``roles manage`` opens the roles modal on the channel's incident:
five user pickers (incident commander and operations lead required, the
communications lead, policy lead and postmortem owner optional) preselected from
the record, or for an incident with no role on the record from the legacy report
(``read_incident_roles``). The modal opens with the command's trigger id, so the
incident is read first and a refusal is answered privately without a view.

The submission acks first (the view closes), then ``assign_roles`` writes the
five roles to the record, announces each role whose holder changed and rewrites
the purpose's ``IC: ... / OL: ...`` line. A refused or failed record write and a
follower that failed or was skipped are told to the submitter privately.
Handlers open one service scope and run the service in one event loop
(``asyncio.run``, the sync Bolt edge). Every string goes through the
``incident_response`` catalogue in the invoker's locale.
"""

import asyncio
import json
from collections.abc import Callable, Mapping
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.services import ServiceScopeOpener
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.api import (
    ConversationReference,
    IncidentStore,
    LegacyRolesReader,
    find_incident_for_conversation,
    read_incident_roles,
)
from features.incident.core.api import translate as t
from features.incident.response import providers
from features.incident.response.entrypoints.scope import incident_scope
from features.incident.response.service.roles import RolesChange, assign_roles
from features.incident.response.service.status import StageOutcome

logger = structlog.get_logger()

ROLES_DOMAIN = "incident_response.roles"
ROLES_CALLBACK_ID = "incident.response.roles"
ROLES_ACTION_ID = "incident.response.roles.select"

# The pickers' order in the modal and the order announcements are posted in.
_ROLES = tuple(IncidentRole)
_REQUIRED = frozenset({IncidentRole.INCIDENT_COMMANDER, IncidentRole.OPERATIONS_LEAD})
_CHANNEL_NAME_PREFIXES = ("incident-", "dev-")


def register_roles(registrar: SlackCommandRegistrar, scopes: ServiceScopeOpener) -> None:
    """Register ``/sre incident roles``, ``roles manage`` and the roles modal's submission.

    Args:
        registrar: Slack command registrar.
        scopes: Opens the service scope the incident store is built in.
    """

    def _dispatch_manage(payload: CommandPayload) -> CommandResponse:
        return handle_roles_manage_command(payload, registrar.reply, scopes)

    def _submit(ack: Callable[..., Any], body: dict[str, Any], client: Any) -> None:
        handle_roles_submission(ack, body, client, scopes)

    registrar.register_command(
        command="roles",
        handler=None,
        parent="sre.incident",
        description="Manage this incident's roles",
        description_key=f"{ROLES_DOMAIN}.description",
    )
    registrar.register_command(
        command="manage",
        handler=_dispatch_manage,
        parent="sre.incident.roles",
        description="Assign this incident's roles",
        description_key=f"{ROLES_DOMAIN}.manage.description",
        usage_hint="",
        examples=[""],
        example_keys=[f"{ROLES_DOMAIN}.manage.examples.default"],
    )
    registrar.register_view_submission(ROLES_CALLBACK_ID, _submit)


def handle_roles_manage_command(payload: CommandPayload, reply: SlackReplySender, scopes: ServiceScopeOpener) -> CommandResponse:
    """Handle ``/sre incident roles manage`` by opening the roles modal on the channel's incident.

    Args:
        payload: Command payload; ``platform_metadata["trigger_id"]`` opens the view and
            ``platform_metadata["channel_name"]`` names it.
        reply: Interface used to open the modal.
        scopes: Opens the service scope the incident store is built in.

    Returns:
        An empty ephemeral response once the modal opened; a localized private
        notice when there is no trigger id or channel, the channel is no
        incident or its roles cannot be read, or the view could not open.
    """
    locale = payload.user_locale or "en-US"
    log = logger.bind(command="incident_roles_manage", user_id=payload.user_id, channel_id=payload.channel_id)
    trigger_id = str(payload.platform_metadata.get("trigger_id", ""))
    if not trigger_id or not payload.channel_id:
        log.warning("incident_roles_manage_no_trigger_or_channel")
        return _reply(_t("open_failed", locale))

    with incident_scope(scopes, payload.channel_id) as (incidents, conversation):
        shown = asyncio.run(_shown_roles(incidents, providers.legacy_roles_reader(), conversation))
    if not shown.is_success or shown.data is None:
        log.warning("incident_roles_manage_refused", operation_status=shown.status.value, error_code=shown.error_code)
        return _reply(_refusal(shown, locale))

    channel_name = str(payload.platform_metadata.get("channel_name") or payload.channel_id)
    view = build_roles_view(shown.data, locale, payload.channel_id, channel_name)
    opened = reply.open_view(trigger_id=trigger_id, view=view)
    if not opened.is_success:
        log.warning("incident_roles_manage_open_failed", error=opened.message, error_code=opened.error_code)
        return _reply(_t("open_failed", locale))
    return CommandResponse(message="", ephemeral=True)


def handle_roles_submission(ack: Callable[..., Any], body: dict[str, Any], client: Any, scopes: ServiceScopeOpener) -> None:
    """Handle the roles modal's submission: write the five roles, announce the changes, rewrite the purpose.

    A missing commander or lead acks with a field error and writes nothing.
    Otherwise the ack closes the view inside Slack's window and the work runs after it.

    Args:
        ack: Bolt ack callable, called exactly once.
        body: View-submission payload; carries the view, its state and the submitting user.
        client: Bolt Slack web client, used for the submitter's private notice.
        scopes: Opens the service scope the incident store is built in.
    """
    view = body.get("view") or {}
    metadata = _parse_metadata(view.get("private_metadata"))
    locale = str(metadata.get("locale") or "en-US")
    channel_id = str(metadata.get("channel_id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    selected = _selected_roles(view)

    missing = {_block_id(role): _t("required", locale) for role in _REQUIRED if selected[role] is None}
    if missing:
        ack(response_action="errors", errors=missing)
        return
    ack()

    log = logger.bind(operation="incident_roles_submission", user_id=user_id, channel_id=channel_id)
    with incident_scope(scopes, channel_id) as (incidents, conversation):
        result = asyncio.run(
            assign_roles(
                incidents,
                providers.incident_conversation(),
                providers.legacy_roles_reader(),
                conversation,
                selected,
                announce=lambda role, holder: _t(
                    "announcement", locale, user=f"<@{holder}>", role=_t(f"name.{role.value}", locale)
                ),
            )
        )
    if not result.is_success or result.data is None:
        log.warning("incident_roles_refused", operation_status=result.status.value, error_code=result.error_code)
        notice = _refusal(result, locale)
    else:
        notice = _outcome(result.data, locale)
    if notice:
        _tell_submitter(client, channel_id, user_id, notice, log)


def build_roles_view(shown: Mapping[IncidentRole, str | None], locale: str, channel_id: str, channel_name: str) -> dict[str, Any]:
    """Build the roles modal: a header naming the incident and one user picker per role, preselected from ``shown``."""
    name = channel_name
    for prefix in _CHANNEL_NAME_PREFIXES:
        name = name.removeprefix(prefix)
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": _t("modal.header", locale, name=name)}}
    ]
    for role in _ROLES:
        element: dict[str, Any] = {
            "type": "users_select",
            "placeholder": {"type": "plain_text", "text": _t(f"placeholder.{role.value}", locale)},
            "action_id": ROLES_ACTION_ID,
        }
        if shown.get(role):
            element["initial_user"] = shown[role]
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "input",
                "block_id": _block_id(role),
                "optional": role not in _REQUIRED,
                "element": element,
                "label": {"type": "plain_text", "text": _t(f"label.{role.value}", locale)},
            }
        )
    return {
        "type": "modal",
        "callback_id": ROLES_CALLBACK_ID,
        "title": {"type": "plain_text", "text": _t("modal.title", locale)},
        "submit": {"type": "plain_text", "text": _t("modal.submit", locale)},
        "private_metadata": json.dumps({"channel_id": channel_id, "channel_name": channel_name, "locale": locale}),
        "blocks": blocks,
    }


# Resolve the conversation's incident and return the roles the modal shows for it.
async def _shown_roles(
    incidents: IncidentStore, legacy: LegacyRolesReader, conversation: ConversationReference
) -> OperationResult[Mapping[IncidentRole, str | None]]:
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return OperationResult.error(
            status=found.status, message=found.message or "", error_code=found.error_code, retry_after=found.retry_after
        )
    return OperationResult.success(await read_incident_roles(found.data, legacy))


def _selected_roles(view: Mapping[str, Any]) -> dict[IncidentRole, str | None]:
    """Read each picker's selected user from the view state; an empty or missing picker is ``None``."""
    values = (view.get("state") or {}).get("values") or {}
    selected: dict[IncidentRole, str | None] = {}
    for role in _ROLES:
        picked = (values.get(_block_id(role)) or {}).get(ROLES_ACTION_ID) or {}
        selected[role] = str(picked["selected_user"]) if picked.get("selected_user") else None
    return selected


def _block_id(role: IncidentRole) -> str:
    return f"{ROLES_CALLBACK_ID}.{role.value}"


def _parse_metadata(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
    except TypeError, ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tell_submitter(client: Any, channel_id: str, user_id: str, text: str, log: structlog.stdlib.BoundLogger) -> None:
    try:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=text)
    except Exception:
        log.exception("incident_roles_notice_failed")


def _refusal(result: OperationResult[Any], locale: str) -> str:
    match result.error_code:
        case ErrorCode.NOT_AN_INCIDENT:
            return _t("not_an_incident", locale)
        case ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION:
            return _t("ambiguous", locale)
        case ErrorCode.INCIDENT_RECORD_CONFLICT:
            return _t("conflict", locale)
        case ErrorCode.INCIDENT_RECORD_UNREADABLE:
            return _t("unreadable", locale)
    return _t("unavailable", locale)


def _outcome(change: RolesChange, locale: str) -> str:
    """The private lines for a follower that was skipped or failed; empty when every follower was done."""
    lines = []
    if change.announcements.outcome is StageOutcome.SKIPPED:
        lines.append(_t("channel_skipped", locale))
    if change.announcements.outcome is StageOutcome.FAILED:
        lines.append(_t("announcements_failed", locale))
    if change.purpose.outcome is StageOutcome.FAILED:
        lines.append(_t("purpose_failed", locale))
    return "\n".join(lines)


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the roles catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{ROLES_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)


def _reply(message: str) -> CommandResponse:
    return CommandResponse(message=message, ephemeral=True)
