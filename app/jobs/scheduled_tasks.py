import asyncio
import json
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import schedule
from structlog import get_logger

from contracts.scheduler.registry import BackgroundJobRegistry
from contracts.services import ServiceScopeOpener
from features.incident.core.adapters import google_docs as incident_drive
from infrastructure.coordination import get_lease_store, run_if_leased
from integrations import maxmind
from integrations.opsgenie import build_opsgenie_client, classify_opsgenie_error, get_opsgenie_settings
from integrations.slack.client import get_slack_web_client
from integrations.slack.settings import get_slack_settings
from jobs.settings import get_scheduler_settings
from modules.aws import identity_center, spending
from modules.incident.notify_stale_incident_channels import (
    notify_stale_incident_channels,
)
from packages.aws_platform.adapters.identity_center import build_identity_center_adapter

logger = get_logger()
schedule_lib = schedule


class _ScheduleBackgroundJobRegistry(BackgroundJobRegistry):
    """Adapter that binds every scheduled job, host-owned, legacy or a plugin's, to the schedule library."""

    def __init__(self, service_scopes: ServiceScopeOpener) -> None:
        self._service_scopes = service_scopes

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        """The service scope opener jobs use to resolve contracts per run."""
        return self._service_scopes

    def register_daily(
        self,
        *,
        job_name: str,
        schedule: str,
        job: Callable[[], None],
        lease_ttl: timedelta | None = None,
    ) -> None:
        job_to_run = _leased_or_plain(job_name, job, lease_ttl)
        schedule_lib.every().day.at(schedule).do(safe_run(job_to_run))
        logger.debug(
            "background_job_scheduled",
            job_name=job_name,
            cadence="daily",
            schedule=schedule,
            lease_ttl_seconds=_seconds(lease_ttl),
        )

    def register_interval(
        self,
        *,
        job_name: str,
        every: timedelta,
        job: Callable[[], None],
        lease_ttl: timedelta | None = None,
    ) -> None:
        job_to_run = _leased_or_plain(job_name, job, lease_ttl)
        seconds = int(every.total_seconds())
        schedule_lib.every(seconds).seconds.do(safe_run(job_to_run))
        logger.debug(
            "background_job_scheduled",
            job_name=job_name,
            cadence="interval",
            every_seconds=seconds,
            lease_ttl_seconds=_seconds(lease_ttl),
        )


def _seconds(ttl: timedelta | None) -> int | None:
    return None if ttl is None else int(ttl.total_seconds())


def _leased_or_plain(job_name: str, job: Callable[[], None], lease_ttl: timedelta | None) -> Callable[[], None]:
    """Return the job as is (Tier-1) or wrapped in a lease named scheduler:<job_name> (Tier-2).

    The TTL is the job's own, never the scheduler default; one under a second is
    rejected here, at registration, so a bad value fails startup instead of a run.
    """
    if lease_ttl is None:
        return job
    ttl_seconds = int(lease_ttl.total_seconds())
    if ttl_seconds < 1:
        raise ValueError(f"lease_ttl for {job_name} must be at least one second, got {lease_ttl}")
    lock_store = get_lease_store(ttl_seconds)

    def leased() -> None:
        run_if_leased(lock_store, f"scheduler:{job_name}", job)

    # safe_run logs the module and name of the job it wraps.
    leased.__module__ = job.__module__
    leased.__name__ = getattr(job, "__name__", "leased_job")
    return leased


def safe_run(job: Callable[..., Any]) -> Callable[..., None]:
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            job(*args, **kwargs)
        except Exception as e:
            # The one log of a failed run, traceback included (decisions/reliability.md).
            logger.error(
                "safe_run_error",
                exc_info=e,
                error=str(e),
                module=job.__module__,
                function=job.__name__,
                arguments=kwargs,
                job_args=args,
            )

    return wrapper


def init(register_plugin_jobs: Callable[[BackgroundJobRegistry], None], service_scopes: ServiceScopeOpener) -> None:
    """Initialize the scheduled tasks.

    Every job, host-owned, legacy or a plugin's, registers through one registry, which
    applies the safe_run boundary and, for a Tier-2 job, the lease.

    Args:
        register_plugin_jobs: Called once with the scheduler registry so feature
            plugins register their recurring jobs.
        service_scopes: Opener the registry exposes so jobs open a service scope per run.
    """
    logger.debug("initializing_scheduled_tasks", module="scheduled_tasks", function="init")

    registry = _ScheduleBackgroundJobRegistry(service_scopes)
    registry.register_interval(job_name="scheduler_heartbeat", every=timedelta(minutes=5), job=scheduler_heartbeat)
    registry.register_interval(job_name="integration_healthchecks", every=timedelta(minutes=5), job=integration_healthchecks)

    # Legacy Tier-2 jobs share the scheduler's default TTL until TASK-65 moves each to its feature.
    # Each body is idempotent; the lease only avoids duplicate cross-replica runs.
    legacy_lease_ttl = timedelta(seconds=get_scheduler_settings().default_tier2_lease_ttl_seconds)
    registry.register_interval(
        job_name="provision_aws_identity_center",
        every=timedelta(hours=2),
        job=provision_aws_identity_center,
        lease_ttl=legacy_lease_ttl,
    )
    # A vendor's tenant entry enables its client (decisions/configuration.md).
    if get_slack_settings().tenant is not None:
        registry.register_daily(
            job_name="notify_stale_incident_channels",
            schedule="16:00",
            job=notify_stale_incident_channels_job,
            lease_ttl=legacy_lease_ttl,
        )
    else:
        logger.debug("scheduled_job_skipped", job_name="notify_stale_incident_channels", reason="slack_not_configured")
    registry.register_daily(
        job_name="spending_generate_spending_data",
        schedule="00:00",
        job=spending.execute_spending_data_update_job,
        lease_ttl=legacy_lease_ttl,
    )

    register_plugin_jobs(registry)


def notify_stale_incident_channels_job() -> None:
    """Run the legacy stale-channel notice on the outbound Slack Web API client, built per run."""
    notify_stale_incident_channels(client=get_slack_web_client())


def scheduler_heartbeat():
    logger.info("running_scheduler_heartbeat", module="scheduled_tasks", time=time.ctime())


def _opsgenie_healthcheck() -> bool:
    """Probe Opsgenie with one services listing; the scheduler thread runs it with one asyncio.run.

    Not configured or a classified failure is unhealthy; unexpected exceptions propagate to the
    per-check handler. TASK-127 decides whether this probe survives.
    """
    return asyncio.run(_probe_opsgenie())


async def _probe_opsgenie() -> bool:
    settings = get_opsgenie_settings()
    if settings.tenant is None:
        logger.warning("opsgenie_not_configured")
        return False
    try:
        async with build_opsgenie_client(settings) as client:
            response = await client.get("/v1/services")
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        status, error_code, _ = classify_opsgenie_error(exc)
        logger.error("opsgenie_healthcheck_error", status=status.value, error_code=error_code)
        return False
    healthy = isinstance(body, dict) and "data" in body
    logger.info("opsgenie_healthcheck_success", status="healthy" if healthy else "unhealthy")
    return healthy


def integration_healthchecks():
    """Run integration healthchecks."""
    logger.info("running_integration_healthchecks", module="scheduled_tasks", time=time.ctime())
    healthchecks: dict[str, Callable[[], bool]] = {
        "google_drive": incident_drive.incident_drive_healthcheck,
        "maxmind": lambda: maxmind.get_maxmind_client().healthcheck().is_success,
        "opsgenie": _opsgenie_healthcheck,
        "aws": lambda: build_identity_center_adapter().healthcheck().is_success,
    }
    for key, healthcheck in healthchecks.items():
        try:
            healthy = healthcheck()
        except Exception as exc:
            logger.error(
                "integration_healthcheck_result",
                module="scheduled_tasks",
                integration=key,
                result="unhealthy",
                error=str(exc),
            )
            continue
        if not healthy:
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


def job_count() -> int:
    """Return how many jobs the scheduler currently holds."""
    return len(schedule.get_jobs())


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
