"""Pytest fixtures for audit infrastructure tests."""

import pytest
from infrastructure.audit.models import AuditEvent


@pytest.fixture
def sample_audit_event():
    """Create a sample audit event for testing.

    Returns:
        AuditEvent with typical success scenario (member added to group).
    """
    return AuditEvent(
        correlation_id="req-test-123",
        timestamp="2025-01-08T12:00:00+00:00",
        action="member_added",
        resource_type="group",
        resource_id="engineering@example.com",
        user_email="alice@example.com",
        result="success",
        provider="google",
        duration_ms=500,
    )


@pytest.fixture
def sample_audit_event_failure():
    """Create a sample audit event for failure scenario.

    Returns:
        AuditEvent with operation failure (transient error).
    """
    return AuditEvent(
        correlation_id="req-test-456",
        timestamp="2025-01-08T12:01:00+00:00",
        action="member_removed",
        resource_type="group",
        resource_id="engineering@example.com",
        user_email="bob@example.com",
        result="failure",
        error_type="transient",
        error_message="API rate limit exceeded",
        provider="aws",
    )


@pytest.fixture
def sample_audit_event_with_metadata():
    """Create a sample audit event with flattened metadata.

    Returns:
        AuditEvent with metadata converted to audit_meta_* fields.
    """
    return AuditEvent(
        correlation_id="req-test-789",
        timestamp="2025-01-08T12:02:00+00:00",
        action="group_created",
        resource_type="group",
        resource_id="newgroup@example.com",
        user_email="charlie@example.com",
        result="success",
        provider="google",
        audit_meta_propagation_count="2",
        audit_meta_retry_count="0",
        audit_meta_source="api",
    )
