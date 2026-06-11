"""Slack-OpsGenie sync feature package.

Polls OpsGenie schedules and updates the matching Slack user groups so they
mirror the current on-call membership. Missing Slack user groups are created
automatically. The sync runs every 5 minutes when at least one rotation is
configured.
"""

from datetime import timedelta

from infrastructure.plugins import hookimpl
from modules.slack_opsgenie_sync.sync import sync_all_rotations

_SYNC_INTERVAL = timedelta(minutes=5)


@hookimpl
def register_background_jobs(registry) -> None:
    """Register the on-call sync job through the scheduler boundary."""
    from infrastructure.configuration.features.slack_opsgenie_sync import (
        get_slack_opsgenie_sync_settings,
    )

    if not get_slack_opsgenie_sync_settings().rotations:
        return

    registry.register_interval(
        job_name="slack_opsgenie_sync",
        every=_SYNC_INTERVAL,
        job=sync_all_rotations,
    )


@hookimpl
def startup_warmup(logger) -> None:
    """Log feature configuration at startup."""
    from infrastructure.configuration.features.slack_opsgenie_sync import (
        get_slack_opsgenie_sync_settings,
    )

    settings = get_slack_opsgenie_sync_settings()
    logger.info(
        "slack_opsgenie_sync_settings_loaded",
        rotation_count=len(settings.rotations),
    )


__all__ = ["register_background_jobs", "startup_warmup", "sync_all_rotations"]
