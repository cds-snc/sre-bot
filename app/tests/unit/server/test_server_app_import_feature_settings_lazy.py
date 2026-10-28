"""Importing the app and the feature readers builds no incident, SRE ops or AWS ops settings.

uvicorn imports the app before the app factory installs the configuration files, and a settings
slice built before then fails closed. The import runs in a fresh interpreter (the test process
has long since imported these modules) and reports the size of the three feature settings caches,
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
    "import modules.incident.core, modules.incident.incident, modules.ops.notifications\n"
    "import modules.aws.groups, modules.aws.users\n"
    "from features.incident.response.settings import get_incident_response_settings\n"
    "from integrations.sentinel.settings import get_sentinel_settings\n"
    "from infrastructure.configuration.features.sre_ops import get_sre_ops_settings\n"
    "from infrastructure.configuration.features.aws_ops import get_aws_feature_settings\n"
    "import modules.atip.atip\n"
    "from modules.atip.settings import get_atip_settings\n"
    "print(*(g.cache_info().currsize for g in (get_incident_response_settings, get_sre_ops_settings, get_aws_feature_settings, get_atip_settings, get_sentinel_settings)))\n"
)


def test_importing_app_and_feature_readers_builds_no_feature_settings() -> None:
    """Each feature slice is read when a command or the startup message runs, never while a module imports."""
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=APP_DIR, capture_output=True, text=True, check=True)  # noqa: S603

    assert result.stdout.strip().splitlines()[-1] == "0 0 0 0 0"
