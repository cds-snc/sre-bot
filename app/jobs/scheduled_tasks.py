from jobs.revoke_aws_sso_access import revoke_aws_sso_access
from jobs.notify_stale_incident_channels import notify_stale_incident_channels
import threading
import time
import schedule
import logging

from integrations import google_drive, maxmind, opsgenie

logging.basicConfig(level=logging.INFO)


def init(bot):
    logging.info("Scheduled tasks initialized ...")

    schedule.every().day.at("16:00").do(
        notify_stale_incident_channels, client=bot.client
    )

    schedule.every(10).seconds.do(revoke_aws_sso_access, client=bot.client)
    schedule.every(5).minutes.do(scheduler_heartbeat)
    schedule.every(5).minutes.do(integration_healthchecks)


def scheduler_heartbeat():
    logging.info("Scheduler is running at %s", time.ctime())


def integration_healthchecks():
    logging.info("Running integration healthchecks ...")
    healthchecks = {
        "google_drive": google_drive.healthcheck,
        "maxmind": maxmind.healthcheck,
        "opsgenie": opsgenie.healthcheck,
    }
    for key, healthcheck in healthchecks.items():
        if not healthcheck():
            logging.error(f"Integration {key} is unhealthy 💀")
        else:
            logging.info(f"Integration {key} is healthy 🌈")


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
