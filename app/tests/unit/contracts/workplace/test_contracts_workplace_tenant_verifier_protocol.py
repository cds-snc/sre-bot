"""Unit tests for the TenantVerifier Protocol in contracts.workplace.

The shared FakeTenantVerifier is assigned to the Protocol type, which mypy
checks structurally, and called through it, so a consumer written against the
contract works with any implementation. The tests also pin the public export.
"""

import pytest

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import TenantVerifier, WorkplaceSystem
from tests.factories.tenant_verifier import FakeTenantVerifier

pytestmark = pytest.mark.unit


def test_a_structural_fake_returns_the_verified_tenant_id_through_the_protocol() -> None:
    fake = FakeTenantVerifier({WorkplaceSystem.SLACK: OperationResult.success(data="T0123")})
    verifier: TenantVerifier = fake

    result = verifier.verified_tenant(WorkplaceSystem.SLACK)

    assert result.status is OperationStatus.SUCCESS
    assert result.data == "T0123"
    assert fake.calls == [WorkplaceSystem.SLACK]
