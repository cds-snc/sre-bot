"""Pins what the two-hourly Identity Center provisioning job writes to AWS.

The job entry point is called directly. Only its two external edges are
faked: the Google directory provider (groups with members, users) and the
Identity Center adapter (identity-store users and groups with memberships),
each patched where the legacy modules look them up. The adapter fake keeps
membership state, so a second run sees what the first run wrote. Assertions
are on the writes the adapter received, never on logging or helper calls.
"""

from typing import Any

import pytest

from contracts.operations import OperationResult, OperationStatus
from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryGroupsWithMembers,
    DirectoryGroupWithMembers,
    DirectoryMember,
    DirectoryUser,
)
from integrations.sentinel import client as sentinel_client
from jobs.scheduled_tasks import provision_aws_identity_center as run_identity_center_job
from modules.aws import identity_center
from modules.provisioning import groups as provisioning_groups
from modules.provisioning import users as provisioning_users
from modules.provisioning.groups import DirectoryGroupsUnavailableError
from modules.provisioning.users import DirectoryUsersUnavailableError

pytestmark = pytest.mark.integration

AWS_USERS = {"alice": "id-alice", "bob": "id-bob", "carol": "id-carol"}


def aws_user(name: str) -> dict[str, Any]:
    return {"UserId": AWS_USERS[name], "UserName": f"{name}@example.org"}


def membership(name: str, membership_id: str | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"MemberId": {"UserId": AWS_USERS[name], "UserName": f"{name}@example.org"}}
    if membership_id is not None:
        entry["MembershipId"] = membership_id
    return entry


def google_group(name: str, *members: str) -> DirectoryGroupWithMembers:
    return DirectoryGroupWithMembers(
        group=DirectoryGroup(
            group_email=f"{name.lower()}@example.org", group_slug=name.lower(), provider_group_id=f"g-{name}", name=name
        ),
        members=tuple(DirectoryMember(email=f"{member}@example.org") for member in members),
    )


class FakeGoogleDirectory:
    """Directory provider double answering the two listings the job makes."""

    def __init__(self) -> None:
        self.groups: tuple[DirectoryGroupWithMembers, ...] = ()
        self.users: list[DirectoryUser] = []
        self.fail_groups = False

    def list_groups_with_members(self, query: str = "") -> OperationResult[DirectoryGroupsWithMembers]:
        if self.fail_groups:
            return OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="directory down", error_code="DOWN")
        return OperationResult.success(DirectoryGroupsWithMembers(groups=self.groups))

    def list_users(self) -> OperationResult[list[DirectoryUser]]:
        return OperationResult.success(self.users)


class FakeIdentityCenter:
    """Identity Center adapter double holding groups with memberships and recording every write."""

    def __init__(self) -> None:
        self.users: list[dict[str, Any]] = []
        self.groups: list[dict[str, Any]] = []
        self.fail_users = False
        self.created_memberships: list[tuple[str, str]] = []
        self.deleted_memberships: list[str] = []
        self.created_users: list[str] = []
        self.deleted_users: list[str] = []

    def writes(self) -> int:
        return len(self.created_memberships) + len(self.deleted_memberships) + len(self.created_users) + len(self.deleted_users)

    def list_users(self) -> OperationResult[list[dict[str, Any]]]:
        if self.fail_users:
            return OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="store down", error_code="DOWN")
        return OperationResult.success(self.users)

    def list_groups_with_memberships(self, groups_filters: Any = None, tolerate_errors: bool = False) -> OperationResult[Any]:
        return OperationResult.success(self.groups)

    def create_group_membership(self, group_id: str, user_id: str) -> OperationResult[str]:
        self.created_memberships.append((group_id, user_id))
        new_id = f"m-{group_id}-{user_id}"
        user = next(user for user in self.users if user["UserId"] == user_id)
        group = next(group for group in self.groups if group["GroupId"] == group_id)
        group["GroupMemberships"].append({"MembershipId": new_id, "MemberId": {"UserId": user_id, "UserName": user["UserName"]}})
        return OperationResult.success(new_id)

    def delete_group_membership(self, membership_id: str) -> OperationResult[bool]:
        self.deleted_memberships.append(membership_id)
        for group in self.groups:
            group["GroupMemberships"] = [m for m in group["GroupMemberships"] if m.get("MembershipId") != membership_id]
        return OperationResult.success(True)

    def create_user(self, email: str, first_name: str, family_name: str) -> OperationResult[str]:
        self.created_users.append(email)
        return OperationResult.success(f"id-{email}")

    def delete_user(self, user_id: str) -> OperationResult[bool]:
        self.deleted_users.append(user_id)
        return OperationResult.success(True)


class Edges:
    def __init__(self, google: FakeGoogleDirectory, aws: FakeIdentityCenter) -> None:
        self.google = google
        self.aws = aws


@pytest.fixture
def edges(monkeypatch: pytest.MonkeyPatch) -> Edges:
    """Patch the directory provider and the adapter builder where each legacy module binds them."""
    google, aws = FakeGoogleDirectory(), FakeIdentityCenter()
    google.users = [
        DirectoryUser(email=f"{name}@example.org", provider_user_id=f"gu-{name}", given_name=name.title(), family_name="Test")
        for name in ("alice", "bob", "carol", "dave")
    ]
    aws.users = [aws_user("alice"), aws_user("bob"), aws_user("carol")]
    for module in (provisioning_groups, provisioning_users):
        monkeypatch.setattr(module, "get_directory_provider", lambda: google)
    for module in (identity_center, provisioning_groups, provisioning_users):
        monkeypatch.setattr(module, "build_identity_center_adapter", lambda: aws)
    monkeypatch.setattr(sentinel_client, "send_event", lambda payload: True)
    return Edges(google, aws)


def aws_group(group_id: str, display_name: str, *memberships: dict[str, Any]) -> dict[str, Any]:
    return {"GroupId": group_id, "DisplayName": display_name, "GroupMemberships": list(memberships)}


def test_google_member_missing_from_the_aws_group_is_added_to_it(edges: Edges) -> None:
    """A Google member who exists in AWS but not in the matching AWS group is added to that group."""
    edges.google.groups = (google_group("AWS-Admins", "alice", "bob"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("bob", "m-bob"))]

    run_identity_center_job()

    assert edges.aws.created_memberships == [("G-admins", "id-alice")]


def test_aws_group_member_absent_from_the_google_group_is_removed(edges: Edges) -> None:
    """A membership in the AWS group whose user is not in the Google group is deleted by membership id."""
    edges.google.groups = (google_group("AWS-Admins", "alice"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("alice", "m-alice"), membership("carol", "m-carol"))]

    run_identity_center_job()

    assert edges.aws.deleted_memberships == ["m-carol"]
    assert edges.aws.created_memberships == []


def test_google_member_without_an_aws_user_is_neither_created_nor_added(edges: Edges) -> None:
    """Users are never created: a Google member unknown to AWS is skipped for the group."""
    edges.google.groups = (google_group("AWS-Admins", "alice", "dave"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("alice", "m-alice"))]

    run_identity_center_job()

    assert edges.aws.created_users == []
    assert edges.aws.created_memberships == []


def test_aws_users_are_never_deleted(edges: Edges) -> None:
    """An AWS user with no Google counterpart stays; only memberships can be deleted."""
    edges.google.groups = (google_group("AWS-Admins", "alice"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("alice", "m-alice"), membership("carol", "m-carol"))]

    run_identity_center_job()

    assert edges.aws.deleted_users == []


def test_google_groups_without_the_aws_prefix_do_not_change_aws_groups(edges: Edges) -> None:
    """A Google group named Engineering is not a source, so the AWS group of that name keeps its members."""
    edges.google.groups = (google_group("Engineering", "alice"),)
    edges.aws.groups = [aws_group("G-eng", "Engineering", membership("carol", "m-carol"))]

    run_identity_center_job()

    assert edges.aws.writes() == 0


def test_aws_groups_without_a_google_match_are_untouched(edges: Edges) -> None:
    """An AWS group with no AWS- Google group of the same name keeps its memberships."""
    edges.google.groups = (google_group("AWS-Admins", "alice"),)
    edges.aws.groups = [
        aws_group("G-admins", "Admins", membership("alice", "m-alice")),
        aws_group("G-orphans", "Orphans", membership("carol", "m-orphan")),
    ]

    run_identity_center_job()

    assert edges.aws.deleted_memberships == []


def test_membership_without_a_membership_id_is_not_deleted(edges: Edges) -> None:
    """A surplus AWS membership that carries no MembershipId cannot be deleted and is skipped."""
    edges.google.groups = (google_group("AWS-Admins", "alice"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("alice", "m-alice"), membership("carol", None))]

    run_identity_center_job()

    assert edges.aws.deleted_memberships == []


def test_memberships_are_reconciled_per_group(edges: Edges) -> None:
    """Each matching group gets its own additions and removals."""
    edges.google.groups = (google_group("AWS-Admins", "alice"), google_group("AWS-Readers", "bob", "carol"))
    edges.aws.groups = [
        aws_group("G-admins", "Admins", membership("bob", "m-admins-bob")),
        aws_group("G-readers", "Readers", membership("carol", "m-readers-carol")),
    ]

    run_identity_center_job()

    assert sorted(edges.aws.created_memberships) == [("G-admins", "id-alice"), ("G-readers", "id-bob")]
    assert edges.aws.deleted_memberships == ["m-admins-bob"]


def test_second_run_over_converged_state_writes_nothing(edges: Edges) -> None:
    """After the first run the stateful adapter matches Google, so running again makes no writes."""
    edges.google.groups = (google_group("AWS-Admins", "alice", "bob"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("bob", "m-bob"), membership("carol", "m-carol"))]
    run_identity_center_job()
    assert edges.aws.writes() == 2

    run_identity_center_job()

    assert edges.aws.writes() == 2


def test_directory_listing_failure_aborts_the_run_without_any_write(edges: Edges) -> None:
    """When the Google group listing fails the job raises and AWS receives no writes."""
    edges.google.groups = (google_group("AWS-Admins", "alice"),)
    edges.google.fail_groups = True
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("carol", "m-carol"))]

    with pytest.raises(DirectoryGroupsUnavailableError):
        run_identity_center_job()

    assert edges.aws.writes() == 0


def test_identity_store_user_listing_failure_aborts_the_run_without_any_write(edges: Edges) -> None:
    """When the identity-store user listing fails the job raises and AWS receives no writes."""
    edges.google.groups = (google_group("AWS-Admins", "alice"),)
    edges.aws.groups = [aws_group("G-admins", "Admins", membership("carol", "m-carol"))]
    edges.aws.fail_users = True

    with pytest.raises(DirectoryUsersUnavailableError):
        run_identity_center_job()

    assert edges.aws.writes() == 0
