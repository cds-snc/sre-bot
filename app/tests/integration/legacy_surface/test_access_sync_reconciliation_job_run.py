"""Pins what the daily access sync reconciliation job asks the sync coordinator to do.

The job entry point is called directly. The runtime configuration is a real
``AccessRuntimeConfig`` listing the configured platforms, and the sync
coordinator is a recording fake patched at ``get_access_sync_coordinator``;
``sync_platform`` is the application API the HTTP route also uses. Assertions
are on the platform syncs the coordinator received and on what the job lets
escape, not on logging.
"""

from typing import Any

import pytest

from contracts.operations import OperationResult, OperationStatus
from packages.access.common.config.settings import AccessRuntimeConfig, PlatformPolicy
from packages.access.sync import _run_reconciliation_job as run_reconciliation_job

pytestmark = pytest.mark.integration


class RecordingCoordinator:
    """Coordinator double recording each ``sync_platform`` call and answering per platform."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.results: dict[str, OperationResult[Any] | Exception] = {}

    def sync_platform(self, platform: str, dry_run: bool = False, request_id: str = "") -> OperationResult[Any]:
        self.calls.append({"platform": platform, "dry_run": dry_run})
        outcome = self.results.get(platform, OperationResult.success())
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def coordinator(monkeypatch: pytest.MonkeyPatch) -> RecordingCoordinator:
    """Patch the coordinator provider where the sync package binds it and configure two platforms."""
    fake = RecordingCoordinator()
    monkeypatch.setattr("packages.access.sync.get_access_sync_coordinator", lambda: fake)
    configure_platforms(monkeypatch, "aws", "gcp")
    return fake


def configure_platforms(monkeypatch: pytest.MonkeyPatch, *platforms: str) -> None:
    config = AccessRuntimeConfig(
        dir_prefix="acc", dir_domain="example.org", platforms={name: PlatformPolicy() for name in platforms}
    )
    monkeypatch.setattr("packages.access.sync.get_access_runtime_config", lambda: config)


def test_every_configured_platform_is_reconciled_once_for_real(coordinator: RecordingCoordinator) -> None:
    """Each configured platform gets one sync_platform call and none of them is a dry run."""
    run_reconciliation_job()

    assert coordinator.calls == [
        {"platform": "aws", "dry_run": False},
        {"platform": "gcp", "dry_run": False},
    ]


def test_no_configured_platform_means_no_sync(monkeypatch: pytest.MonkeyPatch, coordinator: RecordingCoordinator) -> None:
    """An empty platform list leaves the coordinator untouched."""
    configure_platforms(monkeypatch)

    run_reconciliation_job()

    assert coordinator.calls == []


def test_failed_platform_result_does_not_stop_the_remaining_platforms(coordinator: RecordingCoordinator) -> None:
    """A failure result for the first platform is ignored and the next platform is still reconciled."""
    coordinator.results["aws"] = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="throttled", error_code="THROTTLED"
    )

    run_reconciliation_job()

    assert [call["platform"] for call in coordinator.calls] == ["aws", "gcp"]


def test_exception_from_a_platform_sync_escapes_before_the_next_platform(coordinator: RecordingCoordinator) -> None:
    """A raised error propagates to the scheduler wrapper and later platforms are not reconciled in that run."""
    coordinator.results["aws"] = RuntimeError("adapter exploded")

    with pytest.raises(RuntimeError, match="adapter exploded"):
        run_reconciliation_job()

    assert [call["platform"] for call in coordinator.calls] == ["aws"]
