"""Opsgenie schedule source: who is on call, over the async Opsgenie client.

The only module of the app besides the host's settings reads (``server/``) that imports
``integrations.opsgenie``. Atlassian ends Opsgenie support on 2027-04-05 (decisions/oncall.md);
replacing it touches this adapter and no consumer.

Failures are results, never exceptions: no tenant is ``CONFIG_NOT_CONFIGURED`` and no request is
made, a classified httpx or JSON failure carries ``classify_opsgenie_error``'s status and code, and
a body of the wrong shape is ``PERMANENT_ERROR`` ``INVALID_RESPONSE``. Unexpected exceptions
propagate. The source holds no schedule list: references come from the consumers' configuration.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from capabilities.oncall.domain import OnCallPerson, Schedule, ScheduleReference
from capabilities.oncall.interfaces import ScheduleSource
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from integrations.opsgenie import (
    OpsGenieSettings,
    build_opsgenie_client,
    classify_opsgenie_error,
    get_opsgenie_settings,
)

logger = structlog.get_logger()

# With no `date` param, Opsgenie anchors `finalTimeline` at "now", so the first period of the
# matching rotation is the active one, unless its startDate is in the future (a coverage gap).
_TIMELINE_PARAMS = {"identifierType": "id", "interval": "1", "intervalUnit": "days"}


def _now() -> datetime:
    return datetime.now(UTC)


class OpsgenieSource(ScheduleSource):
    """``ScheduleSource`` over the Opsgenie on-calls and timeline endpoints; every call is a GET."""

    def __init__(
        self,
        *,
        settings: Callable[[], OpsGenieSettings] = get_opsgenie_settings,
        client_factory: Callable[[OpsGenieSettings], httpx.AsyncClient] = build_opsgenie_client,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._clock = clock

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        """Return the schedule's on-call participants, or the user active now on the named rotation.

        Without ``rotation`` the /on-calls participants are returned; with it the /timeline period
        active now on that rotation, none for a coverage gap or a recipient that is not a user.
        """
        log = logger.bind(operation="oncall_opsgenie_on_call_now", schedule=reference.id)
        settings = self._settings()
        if settings.tenant is None:
            log.warning("oncall_opsgenie_not_configured")
            return OperationResult.permanent_error(
                "Opsgenie is not configured: [opsgenie.tenant] is unset", ErrorCode.CONFIG_NOT_CONFIGURED
            )
        if rotation is None:
            path, params = f"/v2/schedules/{reference.id}/on-calls", None
        else:
            path, params = f"/v2/schedules/{reference.id}/timeline", _TIMELINE_PARAMS
        try:
            async with self._client_factory(settings) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            status, error_code, retry_after = classify_opsgenie_error(exc)
            log.warning("oncall_opsgenie_request_failed", status=status.value, error_code=error_code)
            return OperationResult.error(status, f"Opsgenie request failed ({error_code})", error_code, retry_after)
        emails = _participant_names(body) if rotation is None else _active_names(body, rotation, self._clock())
        if emails is None:
            log.warning("oncall_opsgenie_request_failed", error_code=ErrorCode.INVALID_RESPONSE, reason="unexpected_shape")
            return OperationResult.permanent_error("Opsgenie response has an unexpected shape", ErrorCode.INVALID_RESPONSE)
        return OperationResult.success(tuple(OnCallPerson(email=email, account=None) for email in emails))

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        """Opsgenie schedules are read for who is on call only; the full schedule is unsupported."""
        return OperationResult.permanent_error("Opsgenie does not support reading a schedule", ErrorCode.UNSUPPORTED_OPERATION)

    async def list_schedules(self) -> OperationResult[tuple[ScheduleReference, ...]]:
        """Return no schedules: Opsgenie references come from the consumers' configuration."""
        return OperationResult.success(())


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


def _active_names(body: Any, rotation: str, now: datetime) -> list[str] | None:
    """The user active now on the named rotation (none for a gap), or ``None`` when the shape is unexpected."""
    data = body.get("data") if isinstance(body, dict) else None
    timeline = data.get("finalTimeline") if isinstance(data, dict) else None
    rotations = timeline.get("rotations") if isinstance(timeline, dict) else None
    if not isinstance(rotations, list):
        return None
    match = next((r for r in rotations if isinstance(r, dict) and r.get("name") == rotation), None)
    if match is None:
        return []
    periods = match.get("periods") or []
    if not isinstance(periods, list):
        return None
    if not periods:
        return []
    period = periods[0]
    start = period.get("startDate") if isinstance(period, dict) else None
    if not isinstance(start, str):
        return None
    try:
        started = datetime.fromisoformat(start)
    except ValueError:
        return None
    if started > now:
        return []
    recipient = period.get("recipient") or {}
    if not isinstance(recipient, dict) or recipient.get("type") != "user":
        return []
    name = recipient.get("name")
    if not isinstance(name, str):
        return None
    return [name]
