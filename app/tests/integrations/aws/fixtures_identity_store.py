from typing import Any, Dict, List, Optional

from models.integrations import IntegrationResponse
from tests.fixtures.aws_clients import FakeClient


def fake_user_client(user: Dict[str, Any]) -> FakeClient:
    """
    Return a FakeClient that responds to describe_user, get_user_id, and create_user as needed.

    Args:
        user: Dict representing a user object.

    Returns:
        FakeClient: Simulated AWS client for user operations.
    """
    return FakeClient(
        api_responses={
            "describe_user": user,
            "get_user_id": {"UserId": user.get("UserId")},
            "create_user": {"UserId": user.get("UserId")},
        }
    )


def fake_group_client(groups: List[Dict[str, Any]]) -> FakeClient:
    """
    Return a FakeClient that pages groups via paginator or returns describe_group.

    Args:
        groups: List of group dicts.

    Returns:
        FakeClient: Simulated AWS client for group operations.
    """
    pages = [{"Groups": groups}]
    return FakeClient(
        paginated_pages=pages,
        api_responses={"describe_group": lambda **kw: groups[0] if groups else {}},
    )


def fake_paginator_for_key(key: str, pages: List[Dict[str, Any]]) -> FakeClient:
    """
    Create a FakeClient with a paginator that yields pages where each page contains `key`.

    Example:
        fake_paginator_for_key("GroupMemberships", [{"GroupMemberships": [...]}, ...])

    Args:
        key: The key to use in each page dict.
        pages: List of dicts or values to normalize.

    Returns:
        FakeClient: Simulated paginator client.
    """
    # Ensure pages are dicts and contain the key
    normalized = []
    for p in pages:
        if isinstance(p, dict) and key in p:
            normalized.append(p)
        else:
            normalized.append({key: p})
    return FakeClient(paginated_pages=normalized)


def fake_membership_client(memberships: List[Dict[str, Any]]) -> FakeClient:
    """
    Return a FakeClient that pages group memberships for list_group_memberships.

    Args:
        memberships: List of membership dicts.

    Returns:
        FakeClient: Simulated AWS client for group membership operations.
    """
    pages = [{"GroupMemberships": memberships}]
    return FakeClient(paginated_pages=pages)


def fake_sts_and_session(
    monkeypatch, fake_client: FakeClient, creds: Optional[Dict[str, str]] = None
):
    """
    Monkeypatch boto3.client('sts') and boto3.Session to simulate role assumption.

    The helper installs a minimal FakeBoto3 into the `integrations.aws.client_next` module
    so tests using get_aws_client(..., role_arn=...) will exercise the assume-role path.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        fake_client: The FakeClient to return for AWS service calls.
        creds: Optional credentials dict.

    Returns:
        Dict of created session parameters.
    """

    if creds is None:
        creds = {"AccessKeyId": "AK", "SecretAccessKey": "SK", "SessionToken": "TK"}

    class FakeSTS:
        def assume_role(self, RoleArn, RoleSessionName, **kwargs):
            return {
                "Credentials": {
                    "AccessKeyId": creds["AccessKeyId"],
                    "SecretAccessKey": creds["SecretAccessKey"],
                    "SessionToken": creds["SessionToken"],
                }
            }

    created = {}

    class FakeSession:
        def __init__(
            self,
            aws_access_key_id=None,
            aws_secret_access_key=None,
            aws_session_token=None,
            region_name=None,
        ):
            created["aws_access_key_id"] = aws_access_key_id
            created["aws_secret_access_key"] = aws_secret_access_key
            created["aws_session_token"] = aws_session_token
            created["region_name"] = region_name

        def client(self, service_name, region_name=None):
            return fake_client

    class FakeBoto3:
        def client(self, name, **kwargs):
            if name == "sts":
                return FakeSTS()
            return fake_client

        Session = FakeSession

    # Patch into integrations.aws.client_next at test time (test must set monkeypatch)
    monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "test_role_arn")
    monkeypatch.setattr("integrations.aws.client_next.boto3", FakeBoto3())
    return created


def assert_integration_success(resp: IntegrationResponse, expected_data=None):
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    if expected_data is not None:
        assert resp.data == expected_data


def assert_integration_error(resp: IntegrationResponse):
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False


# Example builder usage:
# build_success_response({"UserId": "u-1"}, "get_user", "aws")
# build_error_response(Exception("Not found"), "get_user", "aws")
#
# IntegrationResponse contract:
#   build_success_response(data, operation, provider) -> IntegrationResponse(success=True, data=data, ...)
#   build_error_response(error, operation, provider) -> IntegrationResponse(success=False, error=error, ...)
