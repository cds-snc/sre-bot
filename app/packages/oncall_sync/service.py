"""Platform-neutral on-call sync orchestrator.

Iterates the configured rotations, asks the on-call provider who is
currently on call, and tells the user-group target to mirror that user.
Per-rotation failures are isolated so one bad rotation does not block
the others.
"""

from __future__ import annotations

from typing import Iterable

import structlog

from packages.oncall_sync.ports import (
    OnCallScheduleProvider,
    OnCallSyncError,
    UserGroupSyncTarget,
)
from packages.oncall_sync.settings import OnCallRotation

logger = structlog.get_logger()


class OnCallSyncService:
    """Coordinates on-call -> user-group sync across all configured rotations."""

    def __init__(
        self,
        *,
        on_call: OnCallScheduleProvider,
        target: UserGroupSyncTarget,
        rotations: Iterable[OnCallRotation],
    ) -> None:
        self._on_call = on_call
        self._target = target
        self._rotations = list(rotations)

    def sync_all(self) -> None:
        """Sync every configured rotation; isolate per-rotation failures."""
        for rotation in self._rotations:
            self._sync_one(rotation)

    def _sync_one(self, rotation: OnCallRotation) -> None:
        log = logger.bind(
            slack_handle=rotation.slack_handle,
            opsgenie_schedule_id=rotation.opsgenie_schedule_id,
            opsgenie_rotation_name=rotation.opsgenie_rotation_name,
        )
        try:
            email = self._on_call.get_current_on_call_email(rotation)
            if email is None:
                log.info("oncall_sync_rotation_empty")
                return
            self._target.sync_user_group(rotation, email)
        except OnCallSyncError as exc:
            cause = exc.__cause__
            log.error(
                "oncall_sync_rotation_failed",
                error=str(exc),
                error_type=type(cause).__name__ if cause is not None else None,
            )
            return
        log.info("oncall_sync_rotation_synced")
