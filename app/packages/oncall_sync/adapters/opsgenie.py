"""OpsGenie adapter — implements ``OnCallScheduleProvider``."""

from __future__ import annotations

from integrations.opsgenie import (
    OpsGenieAPIError,
    get_on_call_user_for_rotation,
)
from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation


class OpsGenieScheduleProvider:
    """Look up the current on-call user via the OpsGenie /timeline endpoint."""

    def get_current_on_call_email(self, rotation: OnCallRotation) -> str | None:
        try:
            return get_on_call_user_for_rotation(
                rotation.opsgenie_schedule_id,
                rotation.opsgenie_rotation_name,
            )
        except OpsGenieAPIError as exc:
            raise OnCallSyncError(str(exc)) from exc
