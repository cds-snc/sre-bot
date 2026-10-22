"""Importing the app's modules reads no settings and no host facts: only create_app does."""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

_MODULES = [
    "server.server",
    "main",
    "api.routes.system",
    "modules.incident.core",
    "modules.incident.incident_conversation",
    "modules.webhooks.aws_sns",
    "modules.webhooks.patterns.aws_sns_notification.api_key_detected",
    "modules.webhooks.slack",
    "modules.atip.atip",
    "modules.sre.platforms.slack",
    "modules.dev.platforms.slack",
]


@pytest.mark.parametrize("module", _MODULES)
def test_module_imports_with_no_configuration_and_no_host_info(module: str) -> None:
    """A clean interpreter with no ENVIRONMENT and no files installed imports the module."""
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": "."}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr[-2000:]
