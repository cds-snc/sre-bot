"""Pins what the five-minute on-call sync job writes to Slack user groups.

The job entry point is called directly. A real ``OnCallSyncService`` runs over
fakes of its three ports (on-call schedule source, user-group target and
user-rotations source), swapped in at ``providers.get_oncall_sync_service``,
the provider seam the job resolves its service through. Assertions are on the
user-group syncs the target received, never on logging.
"""

from collections.abc import Sequence

import pytest

from packages.oncall_sync import _run_oncall_sync as run_oncall_sync_job
from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.service import OnCallSyncService
from packages.oncall_sync.settings import OnCallRotation, OnCallRotationConfig, OnCallScheduleConfig
from packages.user_rotations.service import CurrentUserRotation

pytestmark = pytest.mark.integration


class FakeOnCallSource:
    """Schedule source keyed by Opsgenie rotation name; a missing key is a gap, an exception is a failure."""

    def __init__(self) -> None:
        self.on_call: dict[str, str | Exception | None] = {}

    def get_current_on_call_email(self, rotation: OnCallRotation) -> str | None:
        outcome = self.on_call.get(rotation.opsgenie_rotation_name)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingTarget:
    """User-group target recording email-based and Slack-id-based syncs by handle."""

    def __init__(self) -> None:
        self.email_syncs: dict[str, list[str]] = {}
        self.id_syncs: dict[str, list[str]] = {}
        self.fail_handles: set[str] = set()

    def sync_user_group(self, handle: str, name: str, description: str, emails: Sequence[str]) -> None:
        if handle in self.fail_handles:
            raise OnCallSyncError(f"cannot sync {handle}")
        self.email_syncs[handle] = list(emails)

    def sync_user_group_ids(self, handle: str, name: str, description: str, user_ids: Sequence[str]) -> None:
        if handle in self.fail_handles:
            raise OnCallSyncError(f"cannot sync {handle}")
        self.id_syncs[handle] = list(user_ids)


class FakeUserRotations:
    def __init__(self, *rotations: CurrentUserRotation) -> None:
        self.rotations = rotations

    def get_current_rotations(self) -> Sequence[CurrentUserRotation]:
        return self.rotations


class Edges:
    def __init__(self) -> None:
        self.source = FakeOnCallSource()
        self.target = RecordingTarget()
        self.user_rotations = FakeUserRotations()
        self.schedules: list[OnCallScheduleConfig] = []

    def service(self) -> OnCallSyncService:
        return OnCallSyncService(
            on_call=self.source, target=self.target, schedules=self.schedules, user_rotations=self.user_rotations
        )


@pytest.fixture
def edges(monkeypatch: pytest.MonkeyPatch) -> Edges:
    """Swap the service provider so the job runs a real service over the fake ports."""
    fakes = Edges()
    monkeypatch.setattr("packages.oncall_sync.providers.get_oncall_sync_service", fakes.service)
    return fakes


def rotation(name: str, handle: str) -> OnCallRotationConfig:
    return OnCallRotationConfig(opsgenie_rotation_name=name, slack_handle=handle, slack_name=handle.title())


def schedule(*rotations: OnCallRotationConfig, handle: str | None = "sre-oncall") -> OnCallScheduleConfig:
    return OnCallScheduleConfig(
        opsgenie_schedule_id="sched-1",
        slack_handle=handle,
        slack_name=handle.title() if handle else None,
        rotations=list(rotations),
    )


def test_each_rotation_group_gets_its_on_call_user_and_the_schedule_group_gets_all_of_them(edges: Edges) -> None:
    """Rotation groups hold their single on-call email and the schedule group holds the union."""
    edges.schedules = [schedule(rotation("primary", "oncall-primary"), rotation("secondary", "oncall-secondary"))]
    edges.source.on_call = {"primary": "ann@example.org", "secondary": "ben@example.org"}

    run_oncall_sync_job()

    assert edges.target.email_syncs == {
        "oncall-primary": ["ann@example.org"],
        "oncall-secondary": ["ben@example.org"],
        "sre-oncall": ["ann@example.org", "ben@example.org"],
    }


def test_rotation_without_a_current_participant_leaves_its_group_untouched(edges: Edges) -> None:
    """A gap in coverage skips that rotation's group and keeps it out of the schedule group."""
    edges.schedules = [schedule(rotation("primary", "oncall-primary"), rotation("secondary", "oncall-secondary"))]
    edges.source.on_call = {"primary": "ann@example.org", "secondary": None}

    run_oncall_sync_job()

    assert edges.target.email_syncs == {
        "oncall-primary": ["ann@example.org"],
        "sre-oncall": ["ann@example.org"],
    }


def test_schedule_with_no_one_on_call_syncs_no_groups(edges: Edges) -> None:
    """When every rotation is a gap, neither rotation nor schedule groups are touched."""
    edges.schedules = [schedule(rotation("primary", "oncall-primary"))]

    run_oncall_sync_job()

    assert edges.target.email_syncs == {}


def test_failed_rotation_skips_the_schedule_group_but_not_the_other_rotations(edges: Edges) -> None:
    """A rotation lookup failure leaves the schedule group stale while the healthy rotation still syncs."""
    edges.schedules = [schedule(rotation("primary", "oncall-primary"), rotation("secondary", "oncall-secondary"))]
    edges.source.on_call = {"primary": OnCallSyncError("opsgenie down"), "secondary": "ben@example.org"}

    run_oncall_sync_job()

    assert edges.target.email_syncs == {"oncall-secondary": ["ben@example.org"]}


def test_failed_rotation_group_write_skips_the_schedule_group(edges: Edges) -> None:
    """A user-group write failure on a rotation also withholds the schedule aggregate."""
    edges.schedules = [schedule(rotation("primary", "oncall-primary"), rotation("secondary", "oncall-secondary"))]
    edges.source.on_call = {"primary": "ann@example.org", "secondary": "ben@example.org"}
    edges.target.fail_handles = {"oncall-primary"}

    run_oncall_sync_job()

    assert edges.target.email_syncs == {"oncall-secondary": ["ben@example.org"]}


def test_failure_in_one_schedule_does_not_abort_the_next_schedule(edges: Edges) -> None:
    """Schedules are isolated: the second one syncs although the first failed."""
    first = schedule(rotation("primary", "oncall-primary"), handle="first-oncall")
    second = OnCallScheduleConfig(
        opsgenie_schedule_id="sched-2",
        slack_handle="second-oncall",
        slack_name="Second",
        rotations=[rotation("other", "oncall-other")],
    )
    edges.schedules = [first, second]
    edges.source.on_call = {"primary": OnCallSyncError("opsgenie down"), "other": "cy@example.org"}

    run_oncall_sync_job()

    assert edges.target.email_syncs == {"oncall-other": ["cy@example.org"], "second-oncall": ["cy@example.org"]}


def test_schedule_without_slack_group_details_still_syncs_its_rotations(edges: Edges) -> None:
    """Without a schedule handle and name only the rotation groups are written."""
    edges.schedules = [schedule(rotation("primary", "oncall-primary"), handle=None)]
    edges.source.on_call = {"primary": "ann@example.org"}

    run_oncall_sync_job()

    assert edges.target.email_syncs == {"oncall-primary": ["ann@example.org"]}


def test_user_rotations_are_synced_by_slack_user_id(edges: Edges) -> None:
    """Self-managed rotations set their group to the current Slack user id, not an email."""
    edges.user_rotations = FakeUserRotations(
        CurrentUserRotation(slack_usergroup_handle="triage", slack_usergroup_name="Triage", slack_user_id="U0TRIAGE"),
        CurrentUserRotation(slack_usergroup_handle="review", slack_usergroup_name="Review", slack_user_id="U0REVIEW"),
    )

    run_oncall_sync_job()

    assert edges.target.id_syncs == {"triage": ["U0TRIAGE"], "review": ["U0REVIEW"]}
    assert edges.target.email_syncs == {}


def test_failed_user_rotation_write_does_not_stop_the_next_one(edges: Edges) -> None:
    """A failure writing one user-rotation group is absorbed and the next rotation still syncs."""
    edges.user_rotations = FakeUserRotations(
        CurrentUserRotation(slack_usergroup_handle="triage", slack_usergroup_name="Triage", slack_user_id="U0TRIAGE"),
        CurrentUserRotation(slack_usergroup_handle="review", slack_usergroup_name="Review", slack_user_id="U0REVIEW"),
    )
    edges.target.fail_handles = {"triage"}

    run_oncall_sync_job()

    assert edges.target.id_syncs == {"review": ["U0REVIEW"]}
