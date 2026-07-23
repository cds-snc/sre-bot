import threading
import time
from collections.abc import Callable
from typing import Any

import schedule
from structlog import get_logger

from infrastructure.plugins.manager import get_plugin_manager
from integrations import maxmind, opsgenie
from integrations.aws import identity_store
from integrations.google_workspace import google_drive
from jobs.models import BackgroundJobRegistry
from modules.aws import identity_center, spending
from modules.incident.notify_stale_incident_channels import (
    notify_stale_incident_channels,
)
from packages.access.sync.providers import (
    get_access_runtime_config,
    get_access_sync_coordinator,
)

logger = get_logger()
schedule_lib = schedule


class _ScheduleBackgroundJobRegistry(BackgroundJobRegistry):
    """Adapter that binds feature jobs to the schedule library."""

    def register(
        self,
        *,
        job_name: str,
        schedule: str,
        job: Callable[[], None],
    ) -> None:
        schedule_lib.every().day.at(schedule).do(safe_run(job))
        logger.info(
            "feature_background_job_scheduled",
            job_name=job_name,
            schedule=schedule,
        )


def safe_run(job: Callable[..., Any]) -> Callable[..., None]:
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            job(*args, **kwargs)
        except Exception as e:
            logger.error(
                "safe_run_error",
                error=str(e),
                module=job.__module__,
                function=job.__name__,
                arguments=kwargs,
                job_args=args,
            )

    return wrapper


def init(bot):
    """Initialize the scheduled tasks."""
    logger.info("initializing_scheduled_tasks", module="scheduled_tasks", function="init")

    schedule.every().day.at("16:00").do(notify_stale_incident_channels, client=bot.client)
    schedule.every(5).minutes.do(safe_run(scheduler_heartbeat))
    schedule.every(5).minutes.do(safe_run(integration_healthchecks))
    schedule.every(2).hours.do(safe_run(provision_aws_identity_center))
    schedule.every().day.at("00:00").do(safe_run(spending.generate_spending_data), logger=logger)

    registry = _ScheduleBackgroundJobRegistry()
    get_plugin_manager().hook.register_background_jobs(registry=registry)


def scheduler_heartbeat():
    logger.info("running_scheduler_heartbeat", module="scheduled_tasks", time=time.ctime())


def integration_healthchecks():
    """Run integration healthchecks."""
    logger.info("running_integration_healthchecks", module="scheduled_tasks", time=time.ctime())
    healthchecks: dict[str, Callable[[], bool]] = {
        "google_drive": google_drive.healthcheck,
        "maxmind": maxmind.healthcheck,
        "opsgenie": opsgenie.healthcheck,
        "aws": identity_store.healthcheck,
    }
    for key, healthcheck in healthchecks.items():
        if not healthcheck():
            logger.error(
                "integration_healthcheck_result",
                module="scheduled_tasks",
                integration=key,
                result="unhealthy",
            )
        else:
            logger.info(
                "integration_healthcheck_result",
                module="scheduled_tasks",
                integration=key,
                result="healthy",
            )


def provision_aws_identity_center():
    """Provision AWS Identity Center"""
    logger.info("provisioning_aws_identity_center", module="scheduled_tasks")
    identity_center.synchronize(
        enable_user_create=False,
        enable_membership_create=True,
        enable_membership_delete=True,
    )


def run_continuously(interval=1):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run. Please note that it is
    *intended behavior that run_continuously() does not run
    missed jobs*. For example, if you've registered a job that
    should run every minute and you set a continuous run
    interval of one hour then your job won't be run 60 times
    at each interval but only once.
    """
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def reconcile_access_sync() -> None:
    """Run full-platform Access Sync batch sync for all registered platforms."""
    logger.info("reconcile_access_sync_started", module="scheduled_tasks")
    coordinator = get_access_sync_coordinator()
    runtime_config = get_access_runtime_config()
    for platform in runtime_config.platforms:
        coordinator.sync_platform(platform=platform, dry_run=False)
