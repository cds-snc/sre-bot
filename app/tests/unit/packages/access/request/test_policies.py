"""Unit tests for packages/access/request/policies.py.

All functions are pure — no mocks required for entitlement-mode and
approval-count tests.  DirectoryProvider tests use simple in-memory stubs.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from infrastructure.directory.models import DirectoryGroup, DirectoryMember
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig, PlatformPolicy
from packages.access.request.domain import AccessRequest, ApprovalDecision
from packages.access.request.policies import (
    check_entitlement_mode,
    is_auto_approvable,
    is_self_approval,
    meets_minimum_approver_count,
    resolve_approver_candidates,
)

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def make_config(
    platform: str = "aws",
    mode_overrides: dict | None = None,
) -> AccessRuntimeConfig:
    return AccessRuntimeConfig(
        dir_prefix="sg",
        dir_separator="-",
        platforms={
            platform: PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
                mode_overrides=mode_overrides or {},
            )
        },
    )


def make_directory_group(
    group_email: str = "sg-aws-admins@example.com",
    group_slug: str = "sg-aws-admins",
    provider_group_id: str = "gid-001",
) -> DirectoryGroup:
    return DirectoryGroup(
        group_email=group_email,
        group_slug=group_slug,
        provider_group_id=provider_group_id,
    )


def make_member(email: str, role: str = "MEMBER") -> DirectoryMember:
    return DirectoryMember(email=email, role=role)


def make_request(
    request_id: str = "req-001",
    user_email: str = "user@example.com",
    actor_email: str = "actor@example.com",
    actor_type: str = "self",
    status: str = "pending_approval",
    resolved_approvers: list[str] | None = None,
) -> AccessRequest:
    return AccessRequest(
        request_id=request_id,
        user_email=user_email,
        actor_email=actor_email,
        actor_type=actor_type,  # type: ignore[arg-type]
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        group_email="sg-aws-admins@example.com",
        provider_group_id="gid-001",
        entitlement_type="group",
        entitlement_id="admin",
        status=status,  # type: ignore[arg-type]
        justification="Need access for project X.",
        resolved_approvers=resolved_approvers or ["approver@example.com"],
    )


def make_decision(
    decision: str = "approved",
    actor_email: str = "approver@example.com",
) -> ApprovalDecision:
    return ApprovalDecision(
        request_id="req-001",
        actor_email=actor_email,
        decision=decision,  # type: ignore[arg-type]
        comment="",
        decided_at=datetime.now(tz=UTC),
    )


# ---------------------------------------------------------------------------
# check_entitlement_mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_entitlement_mode_returns_sync_managed_by_default():
    config = make_config(platform="aws")
    mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-admins")
    assert mode == "sync_managed"


@pytest.mark.unit
def test_check_entitlement_mode_returns_override_when_set():
    config = make_config(platform="aws", mode_overrides={"admins": "ephemeral"})
    mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-admins")
    assert mode == "ephemeral"


@pytest.mark.unit
def test_check_entitlement_mode_returns_deactivated_for_unknown_platform():
    config = make_config(platform="aws")
    mode = check_entitlement_mode(config, platform="gcp", group_slug="sg-gcp-admins")
    assert mode == "deactivated"


@pytest.mark.unit
def test_check_entitlement_mode_deactivated_override():
    config = make_config(platform="aws", mode_overrides={"admins": "deactivated"})
    mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-admins")
    assert mode == "deactivated"


@pytest.mark.unit
def test_check_entitlement_mode_other_slug_not_overridden():
    config = make_config(platform="aws", mode_overrides={"admins": "ephemeral"})
    mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-devs")
    assert mode == "sync_managed"


@pytest.mark.unit
def test_check_entitlement_mode_uses_token_keyed_override_semantics():
    config = make_config(platform="aws", mode_overrides={"admins": "ephemeral"})
    mode = check_entitlement_mode(config, platform="aws", group_slug="sg-aws-admins")
    assert mode == "ephemeral"


# ---------------------------------------------------------------------------
# resolve_approver_candidates
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_approver_candidates_returns_owners_first():
    directory = MagicMock()
    directory.get_group_members.return_value = OperationResult.success(
        data=[
            make_member("member@example.com", role="MEMBER"),
            make_member("owner@example.com", role="OWNER"),
            make_member("manager@example.com", role="MANAGER"),
        ]
    )
    group = make_directory_group()
    result = resolve_approver_candidates(group, "sg-org-admins", directory)
    assert "owner@example.com" in result
    assert "manager@example.com" in result
    assert "member@example.com" not in result


@pytest.mark.unit
def test_resolve_approver_candidates_falls_back_to_org_admins():
    directory = MagicMock()

    def get_group_members(group_key, include_member_types=None):
        if "sg-aws-admins" in group_key:
            return OperationResult.success(data=[make_member("member@example.com", role="MEMBER")])
        return OperationResult.success(data=[make_member("admin@example.com", role="OWNER")])

    directory.get_group_members.side_effect = get_group_members
    group = make_directory_group()
    result = resolve_approver_candidates(group, "sg-org-admins", directory)
    assert result == ["admin@example.com"]


@pytest.mark.unit
def test_resolve_approver_candidates_returns_empty_when_all_fail():
    directory = MagicMock()
    directory.get_group_members.return_value = OperationResult.success(data=[])
    group = make_directory_group()
    result = resolve_approver_candidates(group, "sg-org-admins", directory)
    assert result == []


@pytest.mark.unit
def test_resolve_approver_candidates_returns_empty_on_directory_error():

    directory = MagicMock()
    directory.get_group_members.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="Directory unavailable"
    )
    group = make_directory_group()
    result = resolve_approver_candidates(group, "sg-org-admins", directory)
    assert result == []


# ---------------------------------------------------------------------------
# is_auto_approvable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_is_auto_approvable_delegated_without_sensitive_types():
    assert is_auto_approvable(actor_type="delegated") is True


@pytest.mark.unit
def test_is_auto_approvable_self_actor_not_eligible():
    assert is_auto_approvable(actor_type="self") is False


@pytest.mark.unit
def test_is_auto_approvable_delegated_excluded_for_sensitive_type():
    assert (
        is_auto_approvable(
            actor_type="delegated",
            sensitive_entitlement_types=frozenset({"permission_set"}),
            entitlement_type="permission_set",
        )
        is False
    )


@pytest.mark.unit
def test_is_auto_approvable_delegated_allowed_for_non_sensitive_type():
    assert (
        is_auto_approvable(
            actor_type="delegated",
            sensitive_entitlement_types=frozenset({"permission_set"}),
            entitlement_type="group",
        )
        is True
    )


# ---------------------------------------------------------------------------
# is_self_approval
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_is_self_approval_same_actor_email():
    request = make_request(actor_email="actor@example.com")
    assert is_self_approval(request, "actor@example.com") is True


@pytest.mark.unit
def test_is_self_approval_case_insensitive():
    request = make_request(actor_email="Actor@Example.com")
    assert is_self_approval(request, "actor@example.com") is True


@pytest.mark.unit
def test_is_self_approval_different_users_not_self():
    request = make_request(actor_email="actor@example.com")
    assert is_self_approval(request, "approver@example.com") is False


# ---------------------------------------------------------------------------
# meets_minimum_approver_count
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_meets_minimum_approver_count_exactly_one():
    decisions = [make_decision("approved")]
    assert meets_minimum_approver_count(decisions, required_count=1) is True


@pytest.mark.unit
def test_meets_minimum_approver_count_not_enough():
    decisions = [make_decision("approved")]
    assert meets_minimum_approver_count(decisions, required_count=2) is False


@pytest.mark.unit
def test_meets_minimum_approver_count_rejections_not_counted():
    decisions = [
        make_decision("rejected"),
        make_decision("rejected"),
    ]
    assert meets_minimum_approver_count(decisions, required_count=1) is False


@pytest.mark.unit
def test_meets_minimum_approver_count_mixed_decisions():
    decisions = [
        make_decision("rejected"),
        make_decision("approved"),
        make_decision("approved"),
    ]
    assert meets_minimum_approver_count(decisions, required_count=2) is True


@pytest.mark.unit
def test_meets_minimum_approver_count_empty_decisions():
    assert meets_minimum_approver_count([], required_count=1) is False
