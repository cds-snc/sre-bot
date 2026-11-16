"""Manage on call users"""

import asyncio
import json
from typing import Any

import httpx
from slack_sdk import WebClient
from structlog import get_logger

from integrations.opsgenie import build_opsgenie_client, classify_opsgenie_error, get_opsgenie_settings
from modules.incident.incident_folder import get_folder_metadata

logger = get_logger()


def get_on_call_users(schedule: str) -> list[str]:
    """Return the names (emails) of the people on call for an Opsgenie schedule now.

    Legacy declare and recreate are sync Bolt handlers, so this runs the async lookup with one
    ``asyncio.run``. A missing or failing source invites nobody and says so, never failing the
    declare (decisions/oncall.md): Opsgenie not configured, a classified failure and a response of
    the wrong shape all return ``[]`` with a warning. Unexpected exceptions propagate.
    Deleted with the legacy declare (TASK-145.7.10).
    """
    return asyncio.run(_get_on_call_users(schedule))


async def _get_on_call_users(schedule: str) -> list[str]:
    log = logger.bind(operation="get_on_call_users", schedule=schedule)
    settings = get_opsgenie_settings()
    if settings.tenant is None:
        log.warning("opsgenie_not_configured")
        return []
    try:
        async with build_opsgenie_client(settings) as client:
            response = await client.get(f"/v2/schedules/{schedule}/on-calls")
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        status, error_code, _ = classify_opsgenie_error(exc)
        log.warning("opsgenie_on_call_lookup_failed", status=status.value, error_code=error_code)
        return []
    names = _participant_names(body)
    if names is None:
        log.warning("opsgenie_on_call_lookup_failed", error_code="INVALID_RESPONSE", reason="unexpected_shape")
        return []
    return names


def _participant_names(body: Any) -> list[str] | None:
    """The participants' names from an on-calls response, or ``None`` when the shape is unexpected."""
    data = body.get("data") if isinstance(body, dict) else None
    participants = data.get("onCallParticipants") if isinstance(data, dict) else None
    if not isinstance(participants, list):
        return None
    names: list[str] = []
    for participant in participants:
        name = participant.get("name") if isinstance(participant, dict) else None
        if not isinstance(name, str):
            return None
        names.append(name)
    return names


def get_on_call_users_from_folder(client: WebClient, folder: str) -> list:
    """Get the on call users for a given folder

    Args:
        client (WebClient): Slack WebClient
        folder (str): Google Drive folder ID
    Returns:
        list: List of on call users. If users are found, they will be Slack user objects.
    """
    log = logger.bind(operation="get_on_call_users_from_folder", folder_id=folder)
    oncall = []
    folder_metadata = get_folder_metadata(folder)
    if isinstance(folder_metadata, dict):
        folder_metadata = folder_metadata.get("appProperties", {})
    elif isinstance(folder_metadata, tuple) and len(folder_metadata) > 0:
        folder_metadata = folder_metadata[0].get("appProperties", {})
    else:
        folder_metadata = {}

    # Get OpsGenie data
    if "genie_schedule" in folder_metadata:
        for email in get_on_call_users(folder_metadata["genie_schedule"]):
            try:
                r = client.users_lookupByEmail(email=email)
                if r.get("ok"):
                    oncall.append(r["user"])
            except Exception as e:
                log.error("error_lookup_user_by_email", email=email, error=str(e))
    log.info("oncall_users_resolved", count=len(oncall))
    return oncall
