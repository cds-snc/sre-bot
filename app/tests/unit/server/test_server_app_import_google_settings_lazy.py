"""Importing the app and the legacy Google readers builds no Google settings.

uvicorn imports the app before the app factory installs the configuration
files, and a settings slice built before then fails closed. The import runs in
a fresh interpreter (the test process has long since imported these modules)
and reports the size of both Google settings caches, which must still be empty.
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
    "from integrations.google_workspace.settings import get_google_resources_config, get_google_workspace_settings\n"
    "print(get_google_resources_config.cache_info().currsize, get_google_workspace_settings.cache_info().currsize)\n"
)


def test_importing_app_and_google_readers_builds_no_google_settings() -> None:
    """Every Google id and the delegation email are read when a command or job runs, never while a module imports."""
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=APP_DIR, capture_output=True, text=True, check=True)  # noqa: S603

    assert result.stdout.strip().splitlines()[-1] == "0 0"
