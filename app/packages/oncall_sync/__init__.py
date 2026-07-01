"""On-call sync feature package.

Polls each configured on-call rotation every 5 minutes and updates the
matching messaging user group so it mirrors the current on-call user.
Missing user groups are created automatically. The job runs whenever at
least one rotation is configured in ``rotations.json``.

Business logic lives in ``service.py`` and is platform-neutral; concrete
vendor adapters live under ``adapters/``. Swapping OpsGenie or Slack is a
``providers.py`` change.
"""

from __future__ import annotations

from datetime import timedelta

from infrastructure.plugins import hookimpl

from packages.oncall_sync.settings import get_oncall_rotations

SYNC_INTERVAL = timedelta(minutes=5)


def _run_oncall_sync() -> None:
    """Entry point for the scheduled job."""
    from packages.oncall_sync.providers import get_oncall_sync_service

    get_oncall_sync_service().sync_all()


@hookimpl
def register_background_jobs(registry) -> None:
    """Register the recurring on-call sync job."""

    if not get_oncall_rotations():
        return

    registry.register_interval(
        job_name="oncall_sync",
        every=SYNC_INTERVAL,
        job=_run_oncall_sync,
    )


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective configuration at startup."""

    rotations = get_oncall_rotations()
    logger.info(
        "oncall_sync_settings_loaded",
        sync_interval_seconds=int(SYNC_INTERVAL.total_seconds()),
        rotation_count=len(rotations),
    )
    if not rotations:
        logger.warning(
            "oncall_sync_no_rotations",
            hint="Add entries to packages/oncall_sync/rotations.json to activate.",
        )


__all__ = ["register_background_jobs", "startup_warmup"]
