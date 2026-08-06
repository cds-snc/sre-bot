"""Fixtures for AWS Identity Center adapter integration tests.

Provides ``make_aws_adapter`` — a factory that builds an
``AwsIdentityCenterAdapter`` wired to a typed boto3 identitystore client mock.

The mock is restricted (via ``spec``) to the real boto3 IdentityStore
operation surface plus ``get_paginator`` — matching the production contract
(``get_aws_client("identitystore")``), never an ``AWSClients`` facade:

    fake_identitystore  →  MagicMock(spec=[...boto3 operations...])

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
from botocore.exceptions import ClientError

from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter

_IDENTITY_STORE_ID = "d-1234567890"

_IDENTITYSTORE_CLIENT_METHODS = [
    "list_users",
    "list_groups",
    "describe_group",
    "get_user_id",
    "create_user",
    "delete_user",
    "get_group_membership_id",
    "create_group_membership",
    "delete_group_membership",
    "list_group_memberships_for_member",
    "list_group_memberships",
    "get_paginator",
]


def _not_found(operation: str) -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
        operation_name=operation,
    )


def _paginator(pages: list[dict[str, Any]]) -> MagicMock:
    paginator = MagicMock()
    paginator.paginate.return_value = pages
    return paginator


# ---------------------------------------------------------------------------
# make_aws_adapter
# ---------------------------------------------------------------------------


@pytest.fixture
def make_aws_adapter():
    """Factory for ``AwsIdentityCenterAdapter`` backed by a mock identitystore client.

    The mock exposes the same method surface as the real typed boto3
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
        When set, ``get_user_id`` returns a successful result with
        ``{"UserId": user_id}``.  When ``None``, the call raises
        ``ResourceNotFoundException`` (user absent from Identity Store).
    group_memberships:
        List of ``{"GroupId": "<uuid>"}`` dicts returned (paginated) by
        ``list_group_memberships_for_member``.  Defaults to ``[]``.
    aws_groups:
        List of ``{"GroupId": "<uuid>", "DisplayName": "<name>"}`` dicts
        returned (paginated) by ``list_groups``.  Used by the group index
        build. Defaults to ``[]``.
    list_memberships_error:
        When set, ``list_group_memberships_for_member`` raises this
        ``ClientError`` instead of returning the normal response.
    """

    def _make(
        user_id: str | None = "test-user-uuid-0001",
        group_memberships: list[dict[str, Any]] | None = None,
        aws_groups: list[dict[str, Any]] | None = None,
        list_memberships_error: ClientError | None = None,
    ) -> tuple:
        fake_identitystore = MagicMock(spec=_IDENTITYSTORE_CLIENT_METHODS)

        # get_user_id
        if user_id is not None:
            fake_identitystore.get_user_id.return_value = {"UserId": user_id}
        else:
            fake_identitystore.get_user_id.side_effect = _not_found("GetUserId")

        # describe_group (used by UUID resolution path — raise NOT_FOUND by default
        # so adapter falls through to name-based lookup)
        fake_identitystore.describe_group.side_effect = _not_found("DescribeGroup")

        # get_paginator: list_group_memberships_for_member / list_groups
        paginators = {
            "list_group_memberships_for_member": _paginator([{"GroupMemberships": group_memberships or []}]),
            "list_groups": _paginator([{"Groups": aws_groups or []}]),
        }
        if list_memberships_error is not None:
            paginators["list_group_memberships_for_member"] = MagicMock()
            paginators["list_group_memberships_for_member"].paginate.side_effect = list_memberships_error
        fake_identitystore.get_paginator.side_effect = lambda operation_name: paginators.get(operation_name, _paginator([]))

        adapter = AwsIdentityCenterAdapter(identitystore=fake_identitystore, identity_store_id=_IDENTITY_STORE_ID)
        return adapter, fake_identitystore

    return _make
