import threading
import time
import schedule
import logging

from integrations import maxmind, opsgenie
from integrations.google_workspace import google_drive

from integrations.aws import identity_store
from modules.aws import identity_center, spending
from modules.incident.notify_stale_incident_channels import (
    notify_stale_incident_channels,
)

logging.basicConfig(level=logging.INFO)


def safe_run(job):
    def wrapper(*args, **kwargs):
        try:
            job(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error running job `{job.__name__}`: {e}")

    return wrapper


def init(bot):
    logging.info("Scheduled tasks initialized ...")

    schedule.every().day.at("16:00").do(
        notify_stale_incident_channels, client=bot.client
    )
    # Commenting out the following line to avoid running the task every 10 seconds. Will be enabled at the time of deployment.
    # schedule.every(10).seconds.do(revoke_aws_sso_access, client=bot.client)
    schedule.every(5).minutes.do(safe_run(scheduler_heartbeat))
    schedule.every(5).minutes.do(safe_run(integration_healthchecks))
    schedule.every(2).hours.do(safe_run(provision_aws_identity_center))
    schedule.every().day.at("00:00").do(
        safe_run(spending.generate_spending_data), logger=logging
    )


def scheduler_heartbeat():
    logging.info("Scheduler is running at %s", time.ctime())


def integration_healthchecks():
    logging.info("Running integration healthchecks ...")
    healthchecks = {
        "google_drive": google_drive.healthcheck,
        "maxmind": maxmind.healthcheck,
        "opsgenie": opsgenie.healthcheck,
        "aws": identity_store.healthcheck,
    }
    for key, healthcheck in healthchecks.items():
        if not healthcheck():
            logging.error(f"Integration {key} is unhealthy 💀")
        else:
            logging.info(f"Integration {key} is healthy 🌈")


def provision_aws_identity_center():
    logging.info("Provisioning AWS Identity Center")
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
