"""Fixtures for AWS Identity Center adapter integration tests.

Provides ``make_aws_adapter`` — a factory that builds an
``AwsIdentityCenterAdapter`` wired to a mock ``AWSClients`` facade.

The mock is structured to match the facade contract used by the adapter:

    fake_aws.identitystore  →  MagicMock with per-method return value control

Each factory call returns a fresh adapter + fresh mock, so tests cannot
share state between calls.

Adding a new adapter family (Github, Miro, …):
    Create ``tests/integration/packages/access/sync/adapters/<name>/conftest.py``
    following this same pattern — one ``make_<name>_adapter`` factory fixture
    that returns ``(adapter, mock_client)``.  The generic coordinator-level
    tests in ``test_single_user_sync.py`` and ``test_platform_sync.py`` already
    cover adapter-agnostic scenarios via ``SpyAdapter``; put adapter-specific
    scenarios (canonicalisation, error codes, client contract) here.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter

# ---------------------------------------------------------------------------
# make_aws_adapter
# ---------------------------------------------------------------------------


@pytest.fixture
def make_aws_adapter():
    """Factory for ``AwsIdentityCenterAdapter`` backed by a mock identitystore facade.

    The mock facade exposes the same method surface as the real
    ``IdentityStoreClient`` so the adapter exercises its own logic in full.

    Usage::

        def test_something(make_aws_adapter):
            adapter, fake_is = make_aws_adapter(
                user_id="ec5d2588-f081-70f2-db36-2afc4ef5ce94",
                group_memberships=[],
            )
            result = adapter.get_current_entitlement_ids("alice@example.com")
            assert result.is_success
            assert result.data == set()

    Parameters
    ----------
    user_id:
        When set, ``get_user_id_by_username`` returns a successful result with
        ``{"UserId": user_id}``.  When ``None``, the call returns
        ``ResourceNotFoundException`` (user absent from Identity Store).
    group_memberships:
        List of ``{"GroupId": "<uuid>"}`` dicts returned by
        ``list_group_memberships_for_member``.  Defaults to ``[]``.
    aws_groups:
        List of ``{"GroupId": "<uuid>", "DisplayName": "<name>"}`` dicts
        returned by ``list_groups``.  Used by the group index build.
        Defaults to ``[]``.
    list_memberships_error:
        When set, ``list_group_memberships_for_member`` returns this
        ``OperationResult`` error instead of the normal response.
    """

    def _make(
        user_id: str | None = "test-user-uuid-0001",
        group_memberships: list[dict[str, Any]] | None = None,
        aws_groups: list[dict[str, Any]] | None = None,
        list_memberships_error: OperationResult | None = None,
    ) -> tuple:
        fake_identitystore = MagicMock()

        # get_user_id_by_username
        if user_id is not None:
            fake_identitystore.get_user_id_by_username.return_value = OperationResult.success(data={"UserId": user_id})
        else:
            fake_identitystore.get_user_id_by_username.return_value = OperationResult.error(
                OperationStatus.NOT_FOUND,
                message="User not found",
                error_code="ResourceNotFoundException",
            )

        # list_group_memberships_for_member
        if list_memberships_error is not None:
            fake_identitystore.list_group_memberships_for_member.return_value = list_memberships_error
        else:
            fake_identitystore.list_group_memberships_for_member.return_value = OperationResult.success(
                data=group_memberships or []
            )

        # list_groups (used by group-index build in canonicalise path)
        fake_identitystore.list_groups.return_value = OperationResult.success(data=aws_groups or [])

        # describe_group (used by UUID resolution path — return NOT_FOUND by default
        # so adapter falls through to name-based lookup)
        fake_identitystore.describe_group.return_value = OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="not a uuid",
            error_code="NOT_FOUND",
        )

        fake_aws = MagicMock()
        fake_aws.identitystore = fake_identitystore

        adapter = AwsIdentityCenterAdapter(aws_clients=fake_aws)
        return adapter, fake_identitystore

    return _make
