"""Importing the legacy sre and dev Slack platforms builds no Slack settings.

uvicorn imports the app before the app factory runs, so a settings slice built
at import time validates, and logs, before the configuration phase has
configured logging. The import runs in a fresh interpreter (the test process
has long since imported these modules) and reports the size of the Slack
settings cache, which must still be empty.
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP_DIR = Path(__file__).resolve().parents[3]

PROBE = (
    "import modules.sre.platforms.slack, modules.dev.platforms.slack\n"
    "from integrations.slack.settings import get_slack_settings\n"
    "print(get_slack_settings.cache_info().currsize)\n"
)


def test_importing_legacy_slack_platforms_builds_no_slack_settings() -> None:
    """The Web client is built when a command runs, never while the module imports."""
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=APP_DIR, capture_output=True, text=True, check=True)  # noqa: S603

    assert result.stdout.strip().splitlines()[-1] == "0"
