"""Opsgenie adapter: implements ``OnCallScheduleProvider`` over the async Opsgenie client.

Reads the schedule's timeline for today and returns the user active now on the named rotation.
Classified client failures, a response of the wrong shape and Opsgenie not configured become
``OnCallSyncError`` (cause kept); unexpected exceptions propagate. TASK-146.1 moves these reads
into the on-call capability and TASK-146.2 deletes this adapter.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from contracts.operations.codes import ErrorCode
from integrations.opsgenie import (
    OpsGenieSettings,
    build_opsgenie_client,
    classify_opsgenie_error,
    get_opsgenie_settings,
)
from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation

# With no `date` param, Opsgenie anchors `finalTimeline` at "now", so the first period of the
# matching rotation is the active one, unless its startDate is in the future (a coverage gap).
_TIMELINE_PARAMS = {"identifierType": "id", "interval": "1", "intervalUnit": "days"}


class OpsGenieScheduleProvider:
    """Look up the current on-call user through the Opsgenie /timeline endpoint."""

    def __init__(
        self,
        *,
        settings: Callable[[], OpsGenieSettings] = get_opsgenie_settings,
        client_factory: Callable[[OpsGenieSettings], httpx.AsyncClient] = build_opsgenie_client,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    async def get_current_on_call_email(self, rotation: OnCallRotation) -> str | None:
        settings = self._settings()
        if settings.tenant is None:
            raise OnCallSyncError(f"Opsgenie is not configured ({ErrorCode.CONFIG_NOT_CONFIGURED})")
        path = f"/v2/schedules/{rotation.opsgenie_schedule_id}/timeline"
        try:
            async with self._client_factory(settings) as client:
                response = await client.get(path, params=_TIMELINE_PARAMS)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            _, error_code, _ = classify_opsgenie_error(exc)
            raise OnCallSyncError(
                f"Opsgenie timeline request failed for schedule {rotation.opsgenie_schedule_id!r} ({error_code})"
            ) from exc
        return _active_user(body, rotation)


def _active_user(body: Any, rotation: OnCallRotation) -> str | None:
    """The user active now on the rotation, ``None`` for nobody; raise on an unexpected shape."""
    invalid = OnCallSyncError(
        f"Opsgenie timeline for schedule {rotation.opsgenie_schedule_id!r} has an unexpected shape ({ErrorCode.INVALID_RESPONSE})"
    )
    data = body.get("data") if isinstance(body, dict) else None
    timeline = data.get("finalTimeline") if isinstance(data, dict) else None
    rotations = timeline.get("rotations") if isinstance(timeline, dict) else None
    if not isinstance(rotations, list):
        raise invalid
    match = next((r for r in rotations if isinstance(r, dict) and r.get("name") == rotation.opsgenie_rotation_name), None)
    if match is None:
        return None
    periods = match.get("periods") or []
    if not isinstance(periods, list):
        raise invalid
    if not periods:
        return None
    period = periods[0]
    start = period.get("startDate") if isinstance(period, dict) else None
    if not isinstance(start, str):
        raise invalid
    try:
        started = datetime.fromisoformat(start)
    except ValueError:
        raise invalid from None
    if started > datetime.now(UTC):
        return None
    recipient = period.get("recipient") or {}
    if not isinstance(recipient, dict) or recipient.get("type") != "user":
        return None
    name = recipient.get("name")
    if not isinstance(name, str):
        raise invalid
    return name
