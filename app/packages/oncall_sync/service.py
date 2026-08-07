"""Platform-neutral on-call sync orchestrator.

Iterates the configured schedules. For each schedule, syncs each rotation's
user group to its single on-call user, then syncs the schedule's aggregate
user group to the union of all on-call users. If any rotation fails, the
schedule group update is skipped and an error is logged.
"""

from __future__ import annotations

from collections.abc import Iterable

import structlog

from packages.oncall_sync.ports import (
    OnCallScheduleProvider,
    OnCallSyncError,
    UserGroupSyncTarget,
)
from packages.oncall_sync.settings import (
    OnCallRotation,
    OnCallRotationConfig,
    OnCallScheduleConfig,
)

logger = structlog.get_logger()


class OnCallSyncService:
    """Coordinates on-call -> user-group sync across all configured schedules."""

    def __init__(
        self,
        *,
        on_call: OnCallScheduleProvider,
        target: UserGroupSyncTarget,
        schedules: Iterable[OnCallScheduleConfig],
    ) -> None:
        self._on_call = on_call
        self._target = target
        self._schedules = list(schedules)

    def sync_all(self) -> None:
        """Sync every configured schedule; isolate per-schedule failures."""
        for schedule in self._schedules:
            self._sync_schedule(schedule)

    def _sync_schedule(self, schedule: OnCallScheduleConfig) -> None:
        on_call_emails: list[str] = []
        any_rotation_failed = False

        for rotation_config in schedule.rotations:
            rotation = _resolve_rotation(schedule, rotation_config)
            email, failed = self._sync_rotation(rotation)
            if failed:
                any_rotation_failed = True
            elif email is not None:
                on_call_emails.append(email)

        if any_rotation_failed:
            logger.error(
                "oncall_sync_schedule_group_skipped",
                slack_handle=schedule.slack_handle,
                reason="one_or_more_rotations_failed",
            )
            return

        if not on_call_emails:
            logger.info(
                "oncall_sync_schedule_group_empty",
                slack_handle=schedule.slack_handle,
            )
            return

        log = logger.bind(slack_handle=schedule.slack_handle)
        try:
            self._target.sync_schedule_user_group(schedule, on_call_emails)
        except OnCallSyncError as exc:
            cause = exc.__cause__
            log.error(
                "oncall_sync_schedule_group_failed",
                error=str(exc),
                error_type=type(cause).__name__ if cause is not None else None,
            )
            return
        log.info("oncall_sync_schedule_group_synced")

    def _sync_rotation(self, rotation: OnCallRotation) -> tuple[str | None, bool]:
        """Sync one rotation group.

        Returns ``(email, failed)`` where ``email`` is the on-call address
        (or ``None`` if the rotation is empty) and ``failed`` is ``True``
        when an ``OnCallSyncError`` was raised by either the provider or the
        target.
        """
        log = logger.bind(
            slack_handle=rotation.slack_handle,
            opsgenie_schedule_id=rotation.opsgenie_schedule_id,
            opsgenie_rotation_name=rotation.opsgenie_rotation_name,
        )
        try:
            email = self._on_call.get_current_on_call_email(rotation)
        except OnCallSyncError as exc:
            cause = exc.__cause__
            log.error(
                "oncall_sync_rotation_failed",
                error=str(exc),
                error_type=type(cause).__name__ if cause is not None else None,
            )
            return None, True

        if email is None:
            log.info("oncall_sync_rotation_empty")
            return None, False

        try:
            self._target.sync_user_group(rotation, email)
        except OnCallSyncError as exc:
            cause = exc.__cause__
            log.error(
                "oncall_sync_rotation_failed",
                error=str(exc),
                error_type=type(cause).__name__ if cause is not None else None,
            )
            return None, True

        log.info("oncall_sync_rotation_synced")
        return email, False


def _resolve_rotation(
    schedule: OnCallScheduleConfig,
    rotation: OnCallRotationConfig,
) -> OnCallRotation:
    """Produce the flat adapter type by copying the schedule ID onto the rotation."""
    return OnCallRotation(
        opsgenie_schedule_id=schedule.opsgenie_schedule_id,
        opsgenie_rotation_name=rotation.opsgenie_rotation_name,
        slack_handle=rotation.slack_handle,
        slack_name=rotation.slack_name,
        slack_description=rotation.slack_description,
    )
