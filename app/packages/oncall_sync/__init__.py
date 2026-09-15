"""On-call sync feature package.

Polls each configured on-call schedule every 5 minutes and updates the
matching messaging user groups so they mirror the current on-call users.
For each schedule, each rotation gets its own single-user group, and the
schedule itself gets an aggregate group containing all on-call users across
its rotations. Missing user groups are created automatically. The job runs
whenever at least one schedule is configured in ``rotations.json``.

Business logic lives in ``service.py`` and is platform-neutral; concrete
vendor adapters live under ``adapters/``. Swapping OpsGenie or Slack is a
``providers.py`` change.
"""

from __future__ import annotations

from datetime import timedelta

from infrastructure.plugins import hookimpl
from packages.oncall_sync.settings import get_oncall_schedules
from packages.user_rotations.settings import get_rotations

SYNC_INTERVAL = timedelta(minutes=5)


def _run_oncall_sync() -> None:
    """Entry point for the scheduled job."""
    from packages.oncall_sync.providers import get_oncall_sync_service

    get_oncall_sync_service().sync_all()


@hookimpl
def register_background_jobs(registry) -> None:
    """Register the recurring on-call sync job."""

    if not get_oncall_schedules() and not get_rotations():
        return

    registry.register_interval(
        job_name="oncall_sync",
        every=SYNC_INTERVAL,
        job=_run_oncall_sync,
    )


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective configuration at startup."""

    schedules = get_oncall_schedules()
    user_rotations = get_rotations()
    rotation_count = sum(len(s.rotations) for s in schedules)
    logger.info(
        "oncall_sync_settings_loaded",
        sync_interval_seconds=int(SYNC_INTERVAL.total_seconds()),
        schedule_count=len(schedules),
        rotation_count=rotation_count,
        user_rotation_count=len(user_rotations),
    )
    if not schedules and not user_rotations:
        logger.warning(
            "oncall_sync_no_schedules",
            hint="Add on-call schedules or user rotations to activate.",
        )


__all__ = ["register_background_jobs", "startup_warmup"]
