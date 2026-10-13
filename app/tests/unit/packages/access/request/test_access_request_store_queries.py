"""Unit tests for the access request repository's read paths.

Runs AccessRequestRepository over the in-memory record store, so the
decision prefix query, sort-key ordering and the combined request read are
checked as stored-then-read behaviour rather than as SDK call shapes.
"""

from datetime import UTC, datetime

import pytest

from infrastructure.records.in_memory import InMemoryRecordStore
from packages.access.request.domain import AccessRequest, ApprovalDecision, RequestAuditEvent
from packages.access.request.store import AccessRequestRepository

pytestmark = pytest.mark.unit


def _request(request_id: str) -> AccessRequest:
    return AccessRequest(
        request_id=request_id,
        user_email="alice@example.com",
        actor_email="alice@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="eng",
        group_email="eng@example.com",
        provider_group_id="g-1",
        entitlement_type="group",
        entitlement_id="e-1",
        status="pending_approval",
        justification="on call",
        requested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _decision(request_id: str, day: int, actor: str) -> ApprovalDecision:
    return ApprovalDecision(
        request_id=request_id,
        actor_email=actor,
        decision="approved",
        comment="",
        decided_at=datetime(2026, 1, day, tzinfo=UTC),
    )


@pytest.fixture
def repository() -> AccessRequestRepository:
    repo = AccessRequestRepository(storage=InMemoryRecordStore(), table_name="access_requests")
    repo.save_request(_request("r1"))
    repo.save_decision(_decision("r1", 3, "carol@example.com"))
    repo.save_decision(_decision("r1", 2, "bob@example.com"))
    repo.save_audit_event(
        RequestAuditEvent(
            event_type="submitted",
            request_id="r1",
            actor_email="alice@example.com",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            metadata={},
        )
    )
    repo.save_request(_request("r2"))
    repo.save_decision(_decision("r2", 4, "dave@example.com"))
    return repo


def test_get_decisions_returns_only_that_requests_decisions_oldest_first(repository: AccessRequestRepository) -> None:
    decisions = repository.get_decisions("r1")

    assert [decision.actor_email for decision in decisions] == ["bob@example.com", "carol@example.com"]


def test_get_decisions_for_unknown_request_is_empty(repository: AccessRequestRepository) -> None:
    assert repository.get_decisions("missing") == []


def test_get_request_with_decisions_returns_request_and_its_decisions(repository: AccessRequestRepository) -> None:
    request, decisions = repository.get_request_with_decisions("r1")

    assert request is not None
    assert request.request_id == "r1"
    assert [decision.actor_email for decision in decisions] == ["bob@example.com", "carol@example.com"]


def test_get_request_with_decisions_for_unknown_request(repository: AccessRequestRepository) -> None:
    assert repository.get_request_with_decisions("missing") == (None, [])
