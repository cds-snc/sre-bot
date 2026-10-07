"""Slack block-action listeners for the incident scribe status-updates modal.

The Draft button is a native Bolt listener registered through the command
registrar. It acks, shows a drafting state in the same modal, makes one call to
the status-update service and updates the modal with the result or a localized
error. Slack API failures are logged and never raised; nothing is posted to the
channel. Wording and views come from ``platforms.slack``, the only module that
translates.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import structlog

from contracts.slack.registrar import SlackCommandRegistrar
from packages.incident.scribe.platforms.slack import (
    DRAFT_ACTION_ID,
    build_draft_error_view,
    build_drafting_view,
    build_no_new_information_wording,
    build_result_view,
)
from packages.incident.scribe.status_update import draft_status_update

logger = structlog.get_logger()


def register(registrar: SlackCommandRegistrar) -> None:
    """Register the Draft button's block-action listener.

    Args:
        registrar: Slack command registrar.
    """
    registrar.register_block_action(DRAFT_ACTION_ID, handle_draft_action)


def handle_draft_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the Draft button in the status-updates modal.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    channel_id = str(metadata.get("channel_id", ""))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps({"channel_id": channel_id, "locale": locale})
    log = logger.bind(
        action="incident_status_update_draft", user_id=user_id, channel_id=channel_id, view_id=view_id
    )

    new_hash: str | None = None
    try:
        response = client.views_update(
            view_id=view_id,
            hash=view.get("hash"),
            view=build_drafting_view(locale, private_metadata),
        )
        new_hash = _response_hash(response)
    except Exception:
        log.warning("incident_status_update_drafting_update_failed", exc_info=True)

    result = asyncio.run(
        draft_status_update(channel_id, author=user_id, wording=build_no_new_information_wording(), on_started=None)
    )
    if result.is_success and result.data is not None:
        result_view = build_result_view(result.data, locale, private_metadata)
    else:
        log.warning("incident_status_update_draft_failed", status=result.status, error_code=result.error_code)
        result_view = build_draft_error_view(result.error_code, locale, private_metadata)

    try:
        if new_hash:
            client.views_update(view_id=view_id, hash=new_hash, view=result_view)
        else:
            client.views_update(view_id=view_id, view=result_view)
    except Exception:
        log.warning("incident_status_update_result_update_failed", exc_info=True)


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
