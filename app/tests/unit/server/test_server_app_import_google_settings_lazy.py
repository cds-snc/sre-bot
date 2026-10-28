"""Importing the app and the legacy Google readers builds no Google settings.

The Google document ids live on their owners' slices ([incident_core], [incident_response],
[incident_postmortem], [cloud_operations_spending], [talent]), so the probe reads every
one of those caches beside the Google Workspace slice's.

uvicorn imports the app before the app factory installs the configuration
files, and a settings slice built before then fails closed. The import runs in
a fresh interpreter (the test process has long since imported these modules)
and reports the size of each settings cache, which must still be empty.
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP_DIR = Path(__file__).resolve().parents[3]

PROBE = (
    "import server.server\n"
    "import modules.incident.incident, modules.incident.incident_document, modules.incident.incident_folder\n"
    "import modules.incident.incident_helper, modules.incident.schedule_retro\n"
    "import modules.role.role, modules.dev.incident\n"
    "import features.incident.drive.adapters.google_drive, packages.talent.adapters.google_drive\n"
    "import modules.aws.spending, features.incident.scribe.adapters.google_docs\n"
    "from features.cloud_operations.spending.settings import get_cloud_operations_spending_settings\n"
    "from features.incident.common.settings import get_incident_core_settings\n"
    "from features.incident.postmortem.settings import get_incident_postmortem_settings\n"
    "from features.incident.response.settings import get_incident_response_settings\n"
    "from features.talent.settings import get_talent_settings\n"
    "from integrations.google_workspace.settings import get_google_workspace_settings\n"
    "getters = (get_incident_core_settings, get_incident_response_settings, get_incident_postmortem_settings,\n"
    "           get_cloud_operations_spending_settings, get_talent_settings, get_google_workspace_settings)\n"
    "print(sum(getter.cache_info().currsize for getter in getters))\n"
)


def test_importing_app_and_google_readers_builds_no_google_settings() -> None:
    """Every Google id and the delegation email are read when a command or job runs, never while a module imports."""
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=APP_DIR, capture_output=True, text=True, check=True)  # noqa: S603

    assert result.stdout.strip().splitlines()[-1] == "0"
