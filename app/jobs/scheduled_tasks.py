import threading
import time
import schedule

from structlog import get_logger
from integrations import maxmind, opsgenie
from integrations.google_workspace import google_drive

from integrations.aws import identity_store
from modules.aws import identity_center, spending
from modules.incident.notify_stale_incident_channels import (
    notify_stale_incident_channels,
)
from modules.groups.reconciliation import worker as reconciliation_worker


logger = get_logger()


def safe_run(job):
    def wrapper(*args, **kwargs):
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
    logger.info(
        "initializing_scheduled_tasks", module="scheduled_tasks", function="init"
    )

    schedule.every().day.at("16:00").do(
        notify_stale_incident_channels, client=bot.client
    )
    schedule.every(5).minutes.do(safe_run(scheduler_heartbeat))
    schedule.every(5).minutes.do(safe_run(integration_healthchecks))
    schedule.every(5).minutes.do(
        safe_run(reconciliation_worker.process_reconciliation_batch)
    )
    schedule.every(2).hours.do(safe_run(provision_aws_identity_center))
    schedule.every().day.at("00:00").do(
        safe_run(spending.generate_spending_data), logger=logger
    )


def scheduler_heartbeat():
    logger.info(
        "running_scheduler_heartbeat", module="scheduled_tasks", time=time.ctime()
    )


def integration_healthchecks():
    """Run integration healthchecks."""
    logger.info(
        "running_integration_healthchecks", module="scheduled_tasks", time=time.ctime()
    )
    healthchecks = {
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
