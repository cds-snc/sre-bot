"""Importing the app and the vendor readers builds no Notify, Trello, Opsgenie or MaxMind settings.

uvicorn imports the app before the app factory installs the configuration files, and a settings
slice built before then fails closed. The import runs in a fresh interpreter (the test process
has long since imported these modules) and reports the size of the four vendor settings caches,
which must still be empty.
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP_DIR = Path(__file__).resolve().parents[3]

PROBE = (
    "import server.server\n"
    "import modules.atip.atip, modules.incident.on_call\n"
    "import modules.webhooks.patterns.aws_sns_notification.api_key_detected\n"
    "import packages.oncall_sync.adapters.opsgenie, packages.geolocate.service, jobs.scheduled_tasks\n"
    "import api.v1.routes.geolocate\n"
    "from integrations.notify.settings import get_notify_settings\n"
    "from integrations.trello.settings import get_trello_settings\n"
    "from integrations.opsgenie.settings import get_opsgenie_settings\n"
    "from integrations.maxmind.settings import get_maxmind_settings\n"
    "print(*(g.cache_info().currsize for g in"
    " (get_notify_settings, get_trello_settings, get_opsgenie_settings, get_maxmind_settings)))\n"
)


def test_importing_app_and_vendor_readers_builds_no_vendor_settings() -> None:
    """Each vendor slice is read when a command, job or request runs, never while a module imports."""
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=APP_DIR, capture_output=True, text=True, check=True)  # noqa: S603

    assert result.stdout.strip().splitlines()[-1] == "0 0 0 0"
