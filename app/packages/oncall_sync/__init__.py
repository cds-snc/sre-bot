"""On-call sync feature package.

Polls each configured on-call rotation and updates the matching messaging
user group so it mirrors the current on-call user. Missing user groups
are created automatically. The sync runs on a fixed cadence when the
feature is enabled and at least one rotation is configured.

Business logic lives in ``service.py`` and is platform-neutral; concrete
vendor adapters live under ``adapters/``. Swapping OpsGenie or Slack is a
``providers.py`` change.
"""

from __future__ import annotations

from datetime import timedelta

from infrastructure.plugins import hookimpl


def _run_oncall_sync() -> None:
    """Entry point for the scheduled job."""
    from packages.oncall_sync.providers import get_oncall_sync_service

    get_oncall_sync_service().sync_all()


@hookimpl
def register_background_jobs(registry) -> None:
    """Register the recurring on-call sync job."""
    from packages.oncall_sync.settings import (
        get_oncall_rotations,
        get_oncall_sync_settings,
    )

    settings = get_oncall_sync_settings()
    if not settings.ENABLED or not get_oncall_rotations():
        return

    registry.register_interval(
        job_name="oncall_sync",
        every=timedelta(seconds=settings.SYNC_INTERVAL_SECONDS),
        job=_run_oncall_sync,
    )


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective configuration at startup."""
    from packages.oncall_sync.settings import (
        get_oncall_rotations,
        get_oncall_sync_settings,
    )

    settings = get_oncall_sync_settings()
    logger.info(
        "oncall_sync_settings_loaded",
        enabled=settings.ENABLED,
        sync_interval_seconds=settings.SYNC_INTERVAL_SECONDS,
        rotation_count=len(get_oncall_rotations()),
    )
    if not settings.ENABLED:
        logger.warning(
            "oncall_sync_disabled",
            hint="Set ONCALL_SYNC_ENABLED=true to enable the feature.",
        )


__all__ = ["register_background_jobs", "startup_warmup"]
