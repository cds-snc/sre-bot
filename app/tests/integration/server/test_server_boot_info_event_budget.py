"""Integration test: a ci boot keeps to the startup logging rule's INFO budget.

The real create_app and lifespan run in a subprocess on ENVIRONMENT=ci with fake AWS
credentials, because pytest suppresses logging in its own process. The probe prints one
row per log record; the test reads the rows after the marker line. The bound is the
decisions/observability.md Startup logging rule: at most one INFO event per phase beside
the generated configuration events, and a new phase event raises the bound deliberately.
"""

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tests.integration.server.boot_probe import MARKER

pytestmark = pytest.mark.integration

APP_DIR = Path(__file__).resolve().parents[3]
BOOT_TIMEOUT_SECONDS = 120
MAX_INFO_EVENTS_BESIDE_CONFIGURATION_SLICES = 10
PHASE_EVENTS = {
    "application_startup",
    "core_services_initialized",
    "security_services_initialized",
    "directory_provider_initialized",
    "feature_plugins_loaded",
    "i18n_initialized",
    "feature_integrations_registered",
    "plugin_configuration_summary",
    "scheduled_tasks_skipped",
}
DEMOTED_EVENTS = {
    "core_service_resolved",
    "configured_systems_built",
    "initialized_record_store",
    "slack_provider_initialized",
    "plugin_manager_created",
    "plugin_requirements_resolved",
    "i18n_resources_collected",
    "initialized_yaml_loader",
    "loaded_translations",
    "i18n_initialization_completed_and_healthy",
    "slack_commands_registered",
    "feature_routes_registered",
    "feature_startup_warmup_completed",
    "legacy_slack_commands_registered",
    "security_services_initialization_started",
    "directory_provider_initialization_started",
}


@pytest.fixture(scope="module")
def boot_rows() -> list[dict[str, Any]]:
    env = {**os.environ, "PYTHONPATH": str(APP_DIR), "PYTHONWARNINGS": "ignore"}
    env.update({"AWS_ACCESS_KEY_ID": "boot-probe", "AWS_SECRET_ACCESS_KEY": "boot-probe", "AWS_EC2_METADATA_DISABLED": "true"})
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tests.integration.server.boot_probe"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=BOOT_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    marked = [line for line in result.stdout.splitlines() if line.startswith(MARKER)]
    assert len(marked) == 1, result.stdout[-2000:]
    return json.loads(marked[0].removeprefix(MARKER))


def _info_events(rows: list[dict[str, Any]]) -> list[str]:
    return [row["event"] for row in rows if row["level"] == "INFO" and row["event"] != "configuration_slice"]


def test_a_ci_boot_logs_at_most_the_budgeted_info_events(boot_rows: list[dict[str, Any]]) -> None:
    """INFO events other than configuration_slice stay within one per phase plus the generated summaries."""
    events = _info_events(boot_rows)

    assert len(events) <= MAX_INFO_EVENTS_BESIDE_CONFIGURATION_SLICES, sorted(events)


def test_a_ci_boot_logs_each_phase_event_at_info(boot_rows: list[dict[str, Any]]) -> None:
    """Every lifespan phase event is present at INFO with its stable name."""
    assert set(_info_events(boot_rows)) >= PHASE_EVENTS


def test_a_ci_boot_logs_no_info_event_name_twice(boot_rows: list[dict[str, Any]]) -> None:
    """Only configuration_slice repeats at INFO, one per slice."""
    repeated = {event: count for event, count in Counter(_info_events(boot_rows)).items() if count > 1}

    assert repeated == {}


def test_a_ci_boot_logs_per_item_events_below_info(boot_rows: list[dict[str, Any]]) -> None:
    """Per-item registration and construction events never reach INFO."""
    assert not DEMOTED_EVENTS & {row["event"] for row in boot_rows if row["level"] == "INFO"}


def test_a_ci_boot_logs_one_configuration_slice_event_per_summarised_slice(boot_rows: list[dict[str, Any]]) -> None:
    """The host configuration_slice events are exactly the slices the configuration_summary names."""
    summaries = [row for row in boot_rows if row["event"] == "configuration_summary"]
    slices = [row for row in boot_rows if row["event"] == "configuration_slice" and row["phase"] == "configuration"]

    assert len(summaries) == 1
    assert len(slices) == len(summaries[0]["slices"])


def test_a_ci_boot_names_the_phase_on_every_info_event(boot_rows: list[dict[str, Any]]) -> None:
    """Each info event from the application carries a phase field, as the Startup logging rule requires."""
    unnamed = [
        row["event"]
        for row in boot_rows
        if row["level"] == "INFO" and row["phase"] is None and row["logger"].split(".")[0] not in {"botocore", "uvicorn"}
    ]

    assert unnamed == []
