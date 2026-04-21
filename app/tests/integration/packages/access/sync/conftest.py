"""Fixtures for access_sync integration tests."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig
from packages.access.common.config import PlatformPolicy


@pytest.fixture
def aws_config() -> AccessSyncRuntimeConfig:
    """Canonical AccessSyncRuntimeConfig for AWS integration tests.

    Uses the same naming convention as production:
        dir_prefix="sg", dir_separator="-"
        → group prefix "sg-aws-", authn slug "sg-aws-authn"
    """
    return AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_separator="-",
        platforms={
            "aws": PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
            ),
        },
    )


def make_adapter(
    aws_ic_groups: list[dict[str, Any]],
) -> tuple[AwsIdentityCenterAdapter, MagicMock]:
    """Build an adapter wired to a fake IdentityStore with a known group list.

    Returns ``(adapter, fake_identitystore)`` so callers can assert on mock
    call counts with the correct ``MagicMock`` type rather than piercing the
    adapter's private ``_aws`` attribute through a typed production facade.

    ``describe_group`` always returns NOT_FOUND (tokens are not UUIDs) so the
    adapter falls through to the name-based group index on every resolution.
    """
    fake_identitystore = MagicMock()
    fake_identitystore.describe_group.return_value = OperationResult.error(
        OperationStatus.NOT_FOUND,
        message="not a uuid",
        error_code="NOT_FOUND",
    )
    fake_identitystore.list_groups.return_value = OperationResult.success(
        data=aws_ic_groups
    )
    fake_aws = MagicMock()
    fake_aws.identitystore = fake_identitystore
    adapter = AwsIdentityCenterAdapter(aws_clients=fake_aws)
    return adapter, fake_identitystore
