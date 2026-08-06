"""Moto-backed conformance tests for the AWS IdentityStore consumer surface.

Additive alongside the MagicMock-based unit/integration tests for
``AwsIdentityCenterAdapter`` — exercises real IdentityStore request/response
semantics (via moto) for the operations the access-sync adapter depends on:
create_user, delete_user, get_user_id, describe_user, list_users,
create_group_membership, delete_group_membership, list_group_memberships.

``get_group_membership_id`` and the bulk ``list_groups_with_memberships``
facade helper are intentionally NOT exercised here: moto 5.2.2 does not
implement ``GetGroupMembershipId`` (a real AWS API gap, not a naming
artifact), and ``list_groups_with_memberships`` is not a real boto3
IdentityStore operation.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from botocore.exceptions import ClientError

from integrations.aws import client as aws_client
from integrations.aws.client import AWS_REGION
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter

_IDENTITY_STORE_ID = "d-1234567890"

pytestmark = pytest.mark.integration


def _set_moto_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials so moto never touches real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", AWS_REGION)
    monkeypatch.setattr(aws_client.app_settings, "ENVIRONMENT", "test")


@pytest.fixture
def identitystore_client(monkeypatch: pytest.MonkeyPatch) -> Iterator:
    moto = pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        yield boto3.client("identitystore", region_name=AWS_REGION)


def _create_user(client, username: str) -> Any:
    return client.create_user(
        IdentityStoreId=_IDENTITY_STORE_ID,
        UserName=username,
        DisplayName=username,
        Name={"GivenName": "First", "FamilyName": "Last"},
        Emails=[{"Value": username, "Primary": True, "Type": "WORK"}],
    )


# ---------------------------------------------------------------------------
# Direct boto3 operation conformance
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_create_user_and_get_user_id_roundtrip(identitystore_client):
    _create_user(identitystore_client, "alice@example.com")

    response = identitystore_client.get_user_id(
        IdentityStoreId=_IDENTITY_STORE_ID,
        AlternateIdentifier={"UniqueAttribute": {"AttributePath": "userName", "AttributeValue": "alice@example.com"}},
    )

    assert response["UserId"]


@pytest.mark.integration
def test_get_user_id_raises_not_found_for_unknown_username(identitystore_client):
    with pytest.raises(ClientError) as exc_info:
        identitystore_client.get_user_id(
            IdentityStoreId=_IDENTITY_STORE_ID,
            AlternateIdentifier={"UniqueAttribute": {"AttributePath": "userName", "AttributeValue": "ghost@example.com"}},
        )

    assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"


@pytest.mark.integration
def test_describe_user_returns_created_user(identitystore_client):
    create_response = _create_user(identitystore_client, "bob@example.com")

    response = identitystore_client.describe_user(IdentityStoreId=_IDENTITY_STORE_ID, UserId=create_response["UserId"])

    assert response["UserName"] == "bob@example.com"


@pytest.mark.integration
def test_delete_user_removes_user_then_get_user_id_not_found(identitystore_client):
    create_response = _create_user(identitystore_client, "carol@example.com")

    identitystore_client.delete_user(IdentityStoreId=_IDENTITY_STORE_ID, UserId=create_response["UserId"])

    with pytest.raises(ClientError) as exc_info:
        identitystore_client.get_user_id(
            IdentityStoreId=_IDENTITY_STORE_ID,
            AlternateIdentifier={"UniqueAttribute": {"AttributePath": "userName", "AttributeValue": "carol@example.com"}},
        )
    assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"


@pytest.mark.integration
def test_list_users_paginates_all_created_users(identitystore_client):
    for username in ("dan@example.com", "erin@example.com"):
        _create_user(identitystore_client, username)

    paginator = identitystore_client.get_paginator("list_users")
    usernames = {user["UserName"] for page in paginator.paginate(IdentityStoreId=_IDENTITY_STORE_ID) for user in page["Users"]}

    assert {"dan@example.com", "erin@example.com"} <= usernames


@pytest.mark.integration
def test_create_group_membership_and_list_group_memberships_roundtrip(identitystore_client):
    group_response = identitystore_client.create_group(IdentityStoreId=_IDENTITY_STORE_ID, DisplayName="finops-readonly")
    user_response = _create_user(identitystore_client, "frank@example.com")

    identitystore_client.create_group_membership(
        IdentityStoreId=_IDENTITY_STORE_ID,
        GroupId=group_response["GroupId"],
        MemberId={"UserId": user_response["UserId"]},
    )

    paginator = identitystore_client.get_paginator("list_group_memberships")
    memberships = [
        membership
        for page in paginator.paginate(IdentityStoreId=_IDENTITY_STORE_ID, GroupId=group_response["GroupId"])
        for membership in page["GroupMemberships"]
    ]

    assert len(memberships) == 1
    assert memberships[0]["MemberId"]["UserId"] == user_response["UserId"]


@pytest.mark.integration
def test_delete_group_membership_removes_membership(identitystore_client):
    group_response = identitystore_client.create_group(IdentityStoreId=_IDENTITY_STORE_ID, DisplayName="breakglass-admin")
    user_response = _create_user(identitystore_client, "grace@example.com")
    membership_response = identitystore_client.create_group_membership(
        IdentityStoreId=_IDENTITY_STORE_ID,
        GroupId=group_response["GroupId"],
        MemberId={"UserId": user_response["UserId"]},
    )

    identitystore_client.delete_group_membership(
        IdentityStoreId=_IDENTITY_STORE_ID, MembershipId=membership_response["MembershipId"]
    )

    paginator = identitystore_client.get_paginator("list_group_memberships")
    memberships = [
        membership
        for page in paginator.paginate(IdentityStoreId=_IDENTITY_STORE_ID, GroupId=group_response["GroupId"])
        for membership in page["GroupMemberships"]
    ]
    assert memberships == []


# ---------------------------------------------------------------------------
# Adapter-level conformance (moto-only path; excludes get_group_membership_id
# call sites, which moto does not implement)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_adapter_ensure_user_creates_real_identitystore_user(identitystore_client):
    adapter = AwsIdentityCenterAdapter(identitystore=identitystore_client, identity_store_id=_IDENTITY_STORE_ID)

    result = adapter.ensure_user("henry@example.com")

    assert result.is_success
    user_id = (result.data or {}).get("user_id")
    describe = identitystore_client.describe_user(IdentityStoreId=_IDENTITY_STORE_ID, UserId=user_id)
    assert describe["UserName"] == "henry@example.com"


@pytest.mark.integration
def test_adapter_remove_user_is_idempotent_against_real_semantics(identitystore_client):
    adapter = AwsIdentityCenterAdapter(identitystore=identitystore_client, identity_store_id=_IDENTITY_STORE_ID)

    absent_result = adapter.remove_user("ivy@example.com")
    assert absent_result.is_success
    assert absent_result.message == "user_already_absent"

    adapter.ensure_user("ivy@example.com")
    removed_result = adapter.remove_user("ivy@example.com")
    assert removed_result.is_success
