"""Slack block-action listeners for the incident scribe status-updates modal.

The Draft button is a native Bolt listener registered through the command
registrar. It acks, makes one call to the status-update service and updates the
modal with the result or a localized error. The service calls back just before
a model call so the modal shows a drafting state only then. For a security or
unknown-flag incident the service refuses until the responder confirms, so the
modal shows a confirmation view whose Confirm and draft button calls the
service again with confirmation; Cancel is the view's close button. Slack API
failures are logged and never raised; nothing is posted to the channel. Wording and views come from ``platforms.slack``, the only module that
translates.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import structlog

from contracts.operations.codes import ErrorCode
from contracts.slack.registrar import SlackCommandRegistrar
from packages.incident.scribe.platforms.slack import (
    CONFIRM_ACTION_ID,
    DRAFT_ACTION_ID,
    build_draft_error_view,
    build_drafting_view,
    build_no_new_information_wording,
    build_result_view,
    build_security_confirmation_view,
)
from packages.incident.scribe.status_update import draft_status_update

logger = structlog.get_logger()


def register(registrar: SlackCommandRegistrar) -> None:
    """Register the Draft and Confirm and draft buttons' block-action listeners.

    Args:
        registrar: Slack command registrar.
    """
    registrar.register_block_action(DRAFT_ACTION_ID, handle_draft_action)
    registrar.register_block_action(CONFIRM_ACTION_ID, handle_draft_confirmed_action)


def handle_draft_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the Draft button in the status-updates modal.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    _run_draft(body, client, security_confirmed=False)


def handle_draft_confirmed_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Confirm and draft in the security confirmation view.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    _run_draft(body, client, security_confirmed=True)


class _ModalCursor:
    """The modal's view id and latest hash; updates log Slack errors and never raise."""

    def __init__(self, client: Any, view_id: str, view_hash: str | None, log: structlog.stdlib.BoundLogger) -> None:
        self._client = client
        self._view_id = view_id
        self._hash = view_hash
        self._log = log

    def update(self, view: dict[str, Any], *, failure_event: str) -> None:
        """Replace the modal's view and remember the new hash; log ``failure_event`` on a Slack error."""
        try:
            if self._hash:
                response = self._client.views_update(view_id=self._view_id, hash=self._hash, view=view)
            else:
                response = self._client.views_update(view_id=self._view_id, view=view)
            self._hash = _response_hash(response)
        except Exception:
            self._log.warning(failure_event, exc_info=True)


def _run_draft(body: dict[str, Any], client: Any, *, security_confirmed: bool) -> None:
    """Draft through the service and update the modal with the confirmation, result or error."""
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    channel_id = str(metadata.get("channel_id", ""))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps({"channel_id": channel_id, "locale": locale})
    log = logger.bind(
        action="incident_status_update_draft",
        user_id=user_id,
        channel_id=channel_id,
        view_id=view_id,
        confirmed=security_confirmed,
    )
    modal = _ModalCursor(client, view_id, view.get("hash"), log)

    def show_drafting() -> None:
        modal.update(build_drafting_view(locale, private_metadata), failure_event="incident_status_update_drafting_update_failed")

    result = asyncio.run(
        draft_status_update(
            channel_id,
            author=user_id,
            wording=build_no_new_information_wording(),
            on_started=show_drafting,
            security_confirmed=security_confirmed,
        )
    )
    if result.is_success and result.data is not None:
        result_view = build_result_view(result.data, locale, private_metadata)
        failure_event = "incident_status_update_result_update_failed"
    elif result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED:
        log.info("incident_status_update_security_confirmation_shown")
        result_view = build_security_confirmation_view(locale, private_metadata)
        failure_event = "incident_status_update_confirmation_update_failed"
    else:
        log.warning("incident_status_update_draft_failed", status=result.status, error_code=result.error_code)
        result_view = build_draft_error_view(result.error_code, locale, private_metadata)
        failure_event = "incident_status_update_result_update_failed"
    modal.update(result_view, failure_event=failure_event)


def _parse_metadata(raw: Any) -> dict[str, Any]:
    """Decode the view's private metadata; empty when missing or malformed."""
    try:
        parsed = json.loads(raw) if raw else {}
    except TypeError, ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _response_hash(response: Any) -> str | None:
    """Return the new view hash from a views.update response, when present."""
    try:
        value = response["view"]["hash"]
    except KeyError, TypeError, IndexError:
        return None
    return value if isinstance(value, str) else None
