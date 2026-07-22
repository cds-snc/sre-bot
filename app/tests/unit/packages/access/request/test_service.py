"""Unit tests for packages/access/request/service.py.

Uses in-memory stubs for repository, directory, and dispatcher.
Tests cover the main orchestration paths and error branches.
"""

from dataclasses import replace
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    MembershipCheckResult,
)
from infrastructure.events import Event
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig, PlatformPolicy
from packages.access.common.events import SYNC_COMPLETED, SYNC_FAILED
from packages.access.request.domain import AccessRequest, ApprovalDecision
from packages.access.request.service import AccessRequestService

# ---------------------------------------------------------------------------
# Stubs / factories
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
    email: str = "sg-aws-admins@example.com",
    slug: str = "sg-aws-admins",
    provider_id: str = "gid-001",
) -> DirectoryGroup:
    return DirectoryGroup(
        group_email=email,
        group_slug=slug,
        provider_group_id=provider_id,
    )


def make_membership(
    is_member: bool, group_email: str = "sg-aws-admins@example.com"
) -> MembershipCheckResult:
    return MembershipCheckResult(
        group_email=group_email,
        group_slug="sg-aws-admins",
        provider_group_id="gid-001",
        user_email="user@example.com",
        is_member=is_member,
    )


class FakeRepository:
    """In-memory repository stub."""

    def __init__(self) -> None:
        self._store: dict[str, AccessRequest] = {}
        self._decisions: dict[str, List[ApprovalDecision]] = {}
        self._audit: list = []

    def save_request(self, request: AccessRequest) -> None:
        self._store[request.request_id] = request

    def get_request(self, request_id: str) -> Optional[AccessRequest]:
        return self._store.get(request_id)

    def save_decision(self, decision: ApprovalDecision) -> None:
        self._decisions.setdefault(decision.request_id, []).append(decision)

    def get_decisions(self, request_id: str) -> List[ApprovalDecision]:
        return self._decisions.get(request_id, [])

    def save_audit_event(self, event) -> None:
        self._audit.append(event)

    def get_request_with_decisions(
        self, request_id: str
    ) -> tuple[Optional[AccessRequest], List[ApprovalDecision]]:
        return (
            self._store.get(request_id),
            self._decisions.get(request_id, []),
        )


class FakeDispatcher:
    """Records dispatched events."""

    def __init__(self) -> None:
        self.dispatched: List[Event] = []

    def dispatch_background(self, event: Event) -> None:
        self.dispatched.append(event)

    def dispatch(self, event: Event) -> List:
        self.dispatched.append(event)
        return []


def make_service(
    config: Optional[AccessRuntimeConfig] = None,
    directory: Optional[MagicMock] = None,
    repo: Optional[FakeRepository] = None,
    dispatcher: Optional[FakeDispatcher] = None,
    fallback_approver_slug: str = "sg-org-admins",
    min_approver_count: int = 1,
) -> tuple[AccessRequestService, FakeRepository, FakeDispatcher]:

    repo = repo or FakeRepository()
    dispatcher = dispatcher or FakeDispatcher()
    if directory is None:
        directory = MagicMock()
        directory.get_group.return_value = OperationResult.success(
            data=make_directory_group()
        )

        def _check_membership(group_key: str, user_email: str) -> OperationResult:
            # Target group check: user is not yet a member by default.
            return OperationResult.success(data=make_membership(is_member=False))

        directory.check_membership.side_effect = _check_membership
        # Default group members: approver@example.com and manager@example.com
        # are both OWNERs so delegated actor authorization passes by default.
        directory.get_group_members.return_value = OperationResult.success(
            data=[
                DirectoryMember(email="approver@example.com", role="OWNER"),
                DirectoryMember(email="manager@example.com", role="OWNER"),
            ]
        )
        directory.add_group_member.return_value = (
            OperationResult.success()
        )  # IDP write succeeds by default
    service = AccessRequestService(
        repository=repo,  # type: ignore[arg-type]
        directory=directory,
        runtime_config=config or make_config(),
        dispatcher=dispatcher,  # type: ignore[arg-type]
        fallback_approver_slug=fallback_approver_slug,
        min_approver_count=min_approver_count,
    )
    return service, repo, dispatcher


# ---------------------------------------------------------------------------
# submit_request
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_submit_request_should_succeed_for_valid_self_request():
    service, repo, dispatcher = make_service()

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert result.is_success
    assert result.data is not None
    assert result.data.status == "pending_approval"
    assert result.data.request_id in repo._store


@pytest.mark.unit
def test_submit_request_should_reject_when_group_not_found():
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.error(
        OperationStatus.NOT_FOUND, message="not found"
    )
    service, _, _ = make_service(directory=directory)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert not result.is_success
    assert result.error_code == "GROUP_NOT_FOUND"


@pytest.mark.unit
def test_submit_request_should_reject_when_mode_is_deactivated():
    config = make_config(platform="aws", mode_overrides={"admins": "deactivated"})
    service, _, _ = make_service(config=config)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert not result.is_success
    assert result.error_code == "ENTITLEMENT_MODE_DEACTIVATED"


@pytest.mark.unit
def test_submit_request_should_reject_when_mode_is_ephemeral():
    config = make_config(platform="aws", mode_overrides={"admins": "ephemeral"})
    service, _, _ = make_service(config=config)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert not result.is_success
    assert result.error_code == "ENTITLEMENT_MODE_EPHEMERAL"


@pytest.mark.unit
def test_submit_request_should_reject_when_mode_is_deactivated_with_token_key_override():
    config = make_config(platform="aws", mode_overrides={"admins": "deactivated"})
    service, _, _ = make_service(config=config)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert not result.is_success
    assert result.error_code == "ENTITLEMENT_MODE_DEACTIVATED"


@pytest.mark.unit
def test_submit_request_should_reject_when_already_provisioned():
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=True)
    )
    service, _, _ = make_service(directory=directory)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert not result.is_success
    assert result.error_code == "ALREADY_PROVISIONED"


@pytest.mark.unit
def test_submit_request_should_auto_approve_delegated_requests():
    service, repo, dispatcher = make_service()

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Delegated request.",
    )

    assert result.is_success
    assert result.data is not None
    assert result.data.status == "approved"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_request_approved" in event_types


@pytest.mark.unit
def test_submit_request_should_reject_when_no_approvers_found():
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=False)
    )
    directory.get_group_members.return_value = OperationResult.success(data=[])

    service, _, _ = make_service(directory=directory)
    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    assert not result.is_success
    assert result.error_code == "NO_APPROVERS_FOUND"


# ---------------------------------------------------------------------------
# approve_request
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_approve_request_should_transition_to_approved():
    service, repo, dispatcher = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    assert submit.data is not None
    request_id = submit.data.request_id

    result = service.approve_request(
        request_id=request_id,
        approver_email="approver@example.com",
        comment="Looks good.",
    )

    assert result.is_success
    assert result.data is not None
    updated, decisions = result.data
    assert updated.status == "approved"
    assert len(decisions) == 1
    assert decisions[0].decision == "approved"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_request_approved" in event_types


@pytest.mark.unit
def test_approve_request_should_reject_self_approval():
    service, repo, _ = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="actor@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    assert submit.data is not None
    # Force actor into resolved_approvers for this test

    req = repo._store[submit.data.request_id]
    repo._store[submit.data.request_id] = replace(
        req, resolved_approvers=["actor@example.com"]
    )

    result = service.approve_request(
        request_id=submit.data.request_id,
        approver_email="actor@example.com",
    )

    assert not result.is_success
    assert result.error_code == "SELF_APPROVAL_DENIED"


@pytest.mark.unit
def test_approve_request_should_reject_unauthorized_approver():
    service, _, _ = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    assert submit.data is not None
    result = service.approve_request(
        request_id=submit.data.request_id,
        approver_email="not-an-approver@example.com",
    )

    assert not result.is_success
    assert result.error_code == "APPROVER_NOT_AUTHORIZED"


@pytest.mark.unit
def test_approve_request_should_return_not_found_for_missing_request():
    service, _, _ = make_service()

    result = service.approve_request(
        request_id="nonexistent-id",
        approver_email="approver@example.com",
    )

    assert not result.is_success
    assert result.error_code == "REQUEST_NOT_FOUND"


@pytest.mark.unit
def test_approve_request_calls_add_group_member_on_approval():
    service, repo, dispatcher = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id

    service.approve_request(
        request_id=request_id,
        approver_email="approver@example.com",
        comment="LGTM.",
    )

    service._directory.add_group_member.assert_called_once_with(
        "sg-aws-admins@example.com", "user@example.com"
    )


@pytest.mark.unit
def test_approve_request_should_fail_when_idp_write_fails():
    service, repo, dispatcher = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id

    service._directory.add_group_member.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="IDP unavailable"
    )

    result = service.approve_request(
        request_id=request_id,
        approver_email="approver@example.com",
        comment="Looks good.",
    )

    assert not result.is_success
    assert result.error_code == "IDP_WRITE_FAILED"
    assert repo._store[request_id].status == "failed"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_request_approved" not in event_types


@pytest.mark.unit
def test_submit_request_auto_approve_should_fail_when_idp_write_fails():
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=False)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[
            DirectoryMember(email="approver@example.com", role="OWNER"),
            DirectoryMember(email="manager@example.com", role="OWNER"),
        ]
    )
    directory.add_group_member.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="IDP unavailable"
    )
    service, repo, dispatcher = make_service(directory=directory)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Delegated request.",
    )

    assert not result.is_success
    assert result.error_code == "IDP_WRITE_FAILED"
    stored = list(repo._store.values())
    assert len(stored) == 1
    assert stored[0].status == "failed"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_request_approved" not in event_types


# ---------------------------------------------------------------------------
# reject_request
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_reject_request_should_transition_to_rejected():
    service, repo, dispatcher = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id

    result = service.reject_request(
        request_id=request_id,
        approver_email="approver@example.com",
        comment="Not needed.",
    )

    assert result.is_success
    assert result.data is not None
    updated, decisions = result.data
    assert updated.status == "rejected"
    assert len(decisions) == 1
    assert decisions[0].decision == "rejected"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_requests.request_rejected" in event_types


# ---------------------------------------------------------------------------
# cancel_request
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cancel_request_should_transition_to_cancelled():
    service, repo, dispatcher = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id

    result = service.cancel_request(
        request_id=request_id,
        actor_email="user@example.com",
        comment="Changed my mind.",
    )

    assert result.is_success
    assert result.data is not None
    updated, decisions = result.data
    assert updated.status == "cancelled"
    assert decisions == []


@pytest.mark.unit
def test_cancel_request_should_reject_non_actor():
    service, _, _ = make_service()
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )

    result = service.cancel_request(
        request_id=submit.data.request_id,
        actor_email="someone-else@example.com",
    )

    assert not result.is_success
    assert result.error_code == "CANCELLATION_NOT_AUTHORIZED"


# ---------------------------------------------------------------------------
# advance_from_sync_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_advance_from_sync_result_transitions_to_completed():

    service, repo, dispatcher = make_service()

    # Create an approved request
    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id
    assert submit.data.status == "approved"

    dispatcher.dispatched.clear()

    sync_event = Event(
        event_type=SYNC_COMPLETED,
        user_email="user@example.com",
        metadata={"request_id": request_id, "platform": "aws"},
    )
    service.advance_from_sync_result(sync_event)

    assert repo._store[request_id].status == "completed"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_requests.request_completed" in event_types


@pytest.mark.unit
def test_advance_from_sync_result_transitions_to_failed():

    service, repo, dispatcher = make_service()

    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id
    dispatcher.dispatched.clear()

    sync_event = Event(
        event_type=SYNC_FAILED,
        user_email="user@example.com",
        metadata={"request_id": request_id, "error_code": "ADAPTER_ERROR"},
    )
    service.advance_from_sync_result(sync_event)

    assert repo._store[request_id].status == "failed"
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_requests.request_failed" in event_types


@pytest.mark.unit
def test_advance_from_sync_result_is_noop_when_no_request_id():

    service, repo, _ = make_service()

    sync_event = Event(
        event_type=SYNC_COMPLETED,
        user_email="user@example.com",
        metadata={"platform": "aws"},  # no request_id
    )
    # Should not raise
    service.advance_from_sync_result(sync_event)


@pytest.mark.unit
def test_advance_from_sync_result_is_idempotent_for_completed_request():

    service, repo, dispatcher = make_service()

    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    request_id = submit.data.request_id

    sync_event = Event(
        event_type=SYNC_COMPLETED,
        user_email="user@example.com",
        metadata={"request_id": request_id, "platform": "aws"},
    )
    service.advance_from_sync_result(sync_event)
    assert repo._store[request_id].status == "completed"

    dispatcher.dispatched.clear()
    # Second delivery — should be silent no-op
    service.advance_from_sync_result(sync_event)
    assert repo._store[request_id].status == "completed"
    assert dispatcher.dispatched == []


# ---------------------------------------------------------------------------
# retry_request
# ---------------------------------------------------------------------------


def _make_failed_request(repo: FakeRepository) -> str:
    """Seed a failed request into repo and return its request_id."""

    request_id = "retry-req-001"
    req = AccessRequest(
        request_id=request_id,
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        group_email="sg-aws-admins@example.com",
        provider_group_id="gid-001",
        entitlement_type="group",
        entitlement_id="admins",
        status="failed",
        justification="Need access.",
        resolved_approvers=["approver@example.com"],
        requested_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    repo.save_request(req)
    return request_id


@pytest.mark.unit
def test_retry_request_should_succeed_and_transition_to_approved():
    service, repo, dispatcher = make_service()
    request_id = _make_failed_request(repo)

    result = service.retry_request(
        request_id=request_id,
        actor_email="approver@example.com",
        comment="DWD scopes have been fixed.",
    )

    assert result.is_success
    assert result.data is not None
    updated, decisions = result.data
    assert updated.status == "approved"
    assert decisions == []
    assert repo._store[request_id].status == "approved"
    assert any(
        e.event_type == "access_requests.request_approved"
        or e.event_type == "access_request_approved"
        for e in dispatcher.dispatched
    )


@pytest.mark.unit
def test_retry_request_should_fail_when_not_in_failed_state():
    service, repo, dispatcher = make_service()

    # Submit a fresh request — it will be pending_approval
    submit_result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Need access.",
    )
    assert submit_result.data is not None
    request_id = submit_result.data.request_id

    result = service.retry_request(
        request_id=request_id,
        actor_email="approver@example.com",
    )

    assert not result.is_success
    assert result.error_code == "INVALID_STATE_TRANSITION"


@pytest.mark.unit
def test_retry_request_should_fail_when_actor_not_in_approvers():
    service, repo, _ = make_service()
    request_id = _make_failed_request(repo)

    result = service.retry_request(
        request_id=request_id,
        actor_email="random@example.com",
    )

    assert not result.is_success
    assert result.error_code == "APPROVER_NOT_AUTHORIZED"


@pytest.mark.unit
def test_retry_request_should_return_not_found_for_missing_request():
    service, _, _ = make_service()

    result = service.retry_request(
        request_id="does-not-exist",
        actor_email="approver@example.com",
    )

    assert not result.is_success
    assert result.error_code == "REQUEST_NOT_FOUND"


@pytest.mark.unit
def test_retry_request_should_keep_failed_state_when_idp_write_fails_again():

    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=False)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[
            __import__(
                "infrastructure.directory.models",
                fromlist=["DirectoryMember"],
            ).DirectoryMember(email="approver@example.com", role="OWNER")
        ]
    )
    directory.add_group_member.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="unauthorized_client",
        error_code="IDP_WRITE_FAILED",
    )

    service, repo, dispatcher = make_service(directory=directory)
    request_id = _make_failed_request(repo)

    result = service.retry_request(
        request_id=request_id,
        actor_email="approver@example.com",
        comment="Trying again.",
    )

    assert not result.is_success
    assert result.error_code == "IDP_WRITE_FAILED"
    # Status remains failed
    assert repo._store[request_id].status == "failed"
    # Audit event recorded
    assert any(
        getattr(e, "event_type", None) == "access_request_retry_failed"
        for e in repo._audit
    )
    # No domain event dispatched
    assert dispatcher.dispatched == []


# ---------------------------------------------------------------------------
# revoke — request_type="revoke"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_revoke_request_should_reject_when_user_not_a_member():
    """Grant pre-check is inverted: revoke rejects if user is NOT a member."""
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=False)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[DirectoryMember(email="approver@example.com", role="OWNER")]
    )
    service, _, _ = make_service(directory=directory)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="revoke",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Leaving team.",
    )

    assert not result.is_success
    assert result.error_code == "NOT_PROVISIONED"


@pytest.mark.unit
def test_revoke_request_should_succeed_when_user_is_a_member():
    """Revoke proceeds to pending_approval when user is currently a member."""
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=True)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[DirectoryMember(email="approver@example.com", role="OWNER")]
    )
    service, repo, _ = make_service(directory=directory)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="revoke",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Leaving team.",
    )

    assert result.is_success
    assert result.data.status == "pending_approval"
    assert result.data.request_type == "revoke"


@pytest.mark.unit
def test_revoke_delegated_auto_approves_and_calls_remove_group_member():
    """Delegated revoke auto-approves and calls remove_group_member, not add."""
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=True)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[
            DirectoryMember(email="approver@example.com", role="OWNER"),
            DirectoryMember(email="manager@example.com", role="OWNER"),
        ]
    )
    directory.remove_group_member = MagicMock(return_value=OperationResult.success())
    service, repo, dispatcher = make_service(directory=directory)

    result = service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="revoke",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Off-boarding.",
    )

    assert result.is_success
    assert result.data.status == "approved"
    directory.remove_group_member.assert_called_once_with(
        "sg-aws-admins@example.com", "user@example.com"
    )
    directory.add_group_member.assert_not_called()
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_request_approved" in event_types


@pytest.mark.unit
def test_revoke_approve_calls_remove_group_member():
    """Approving a revoke request calls remove_group_member on the IDP."""
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=True)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[DirectoryMember(email="approver@example.com", role="OWNER")]
    )
    directory.remove_group_member = MagicMock(return_value=OperationResult.success())
    service, repo, dispatcher = make_service(directory=directory)

    submit = service.submit_request(
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="revoke",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Leaving team.",
    )
    request_id = submit.data.request_id

    result = service.approve_request(
        request_id=request_id,
        approver_email="approver@example.com",
        comment="Confirmed.",
    )

    assert result.is_success
    assert result.data is not None
    updated, decisions = result.data
    assert updated.status == "approved"
    assert len(decisions) == 1
    assert decisions[0].decision == "approved"
    directory.remove_group_member.assert_called_once_with(
        "sg-aws-admins@example.com", "user@example.com"
    )
    directory.add_group_member.assert_not_called()
    event_types = [e.event_type for e in dispatcher.dispatched]
    assert "access_request_approved" in event_types


@pytest.mark.unit
def test_revoke_request_type_in_approved_event_metadata():
    """request_type is included in the REQUEST_APPROVED event metadata."""
    directory = MagicMock()
    directory.get_group.return_value = OperationResult.success(
        data=make_directory_group()
    )
    directory.check_membership.return_value = OperationResult.success(
        data=make_membership(is_member=True)
    )
    directory.get_group_members.return_value = OperationResult.success(
        data=[
            DirectoryMember(email="approver@example.com", role="OWNER"),
            DirectoryMember(email="manager@example.com", role="OWNER"),
        ]
    )
    directory.remove_group_member = MagicMock(return_value=OperationResult.success())
    service, _, dispatcher = make_service(directory=directory)

    service.submit_request(
        user_email="user@example.com",
        actor_email="manager@example.com",
        actor_type="delegated",
        request_type="revoke",
        platform="aws",
        group_slug="sg-aws-admins",
        entitlement_type="group",
        justification="Off-boarding.",
    )

    approved_event = next(
        e for e in dispatcher.dispatched if e.event_type == "access_request_approved"
    )
    assert approved_event.metadata["request_type"] == "revoke"
