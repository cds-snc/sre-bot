"""Behavior tests for OrganizationsAdapter operations.

A real boto3 organizations client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination across two pages with NextToken,
and classification paths for ResourceNotFoundException, AccessDeniedException,
ThrottlingException, BotoCoreError transient errors, and unmapped errors
propagating.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.organizations import OrganizationsAdapter

pytestmark = pytest.mark.unit


def _organizations_client() -> Any:
    """Build a real boto3 organizations client with dummy static credentials."""
    return boto3.client(
        "organizations",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestListOrganizationAccounts:
    """ListAccounts returns paginated list of accounts."""

    def test_list_organization_accounts_success_single_page(self) -> None:
        """ListAccounts with single page returns list of accounts."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_accounts",
                {
                    "Accounts": [
                        {
                            "Id": "123456789012",
                            "Arn": "arn:aws:organizations::123456789012:account/o-1234567890/123456789012",
                            "Email": "account1@example.com",
                            "Name": "Account 1",
                            "Status": "ACTIVE",
                            "JoinedMethod": "CREATED",
                            "JoinedTimestamp": 1234567890.0,
                        }
                    ]
                },
                expected_params={},
            )

            result = adapter.list_organization_accounts()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["Id"] == "123456789012"
        assert result.data[0]["Email"] == "account1@example.com"

    def test_list_organization_accounts_pagination_two_pages(self) -> None:
        """ListAccounts flattens accounts across two pages via NextToken."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_accounts",
                {
                    "Accounts": [
                        {
                            "Id": "111111111111",
                            "Arn": "arn:aws:organizations::111111111111:account/o-1234567890/111111111111",
                            "Email": "account1@example.com",
                            "Name": "Account 1",
                            "Status": "ACTIVE",
                            "JoinedMethod": "CREATED",
                            "JoinedTimestamp": 1234567890.0,
                        }
                    ],
                    "NextToken": "accounts-token",
                },
                expected_params={},
            )
            stub.add_response(
                "list_accounts",
                {
                    "Accounts": [
                        {
                            "Id": "222222222222",
                            "Arn": "arn:aws:organizations::222222222222:account/o-1234567890/222222222222",
                            "Email": "account2@example.com",
                            "Name": "Account 2",
                            "Status": "ACTIVE",
                            "JoinedMethod": "CREATED",
                            "JoinedTimestamp": 1234567891.0,
                        }
                    ]
                },
                expected_params={"NextToken": "accounts-token"},
            )

            result = adapter.list_organization_accounts()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [a["Id"] for a in result.data] == ["111111111111", "222222222222"]

    def test_list_organization_accounts_empty(self) -> None:
        """ListAccounts with no accounts returns empty list."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_accounts",
                {"Accounts": []},
                expected_params={},
            )

            result = adapter.list_organization_accounts()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestGetAccountDetails:
    """DescribeAccount returns account details."""

    def test_get_account_details_success(self) -> None:
        """DescribeAccount returns account details for a given account ID."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "describe_account",
                {
                    "Account": {
                        "Id": "123456789012",
                        "Arn": "arn:aws:organizations::123456789012:account/o-1234567890/123456789012",
                        "Email": "account@example.com",
                        "Name": "My Account",
                        "Status": "ACTIVE",
                        "JoinedMethod": "CREATED",
                        "JoinedTimestamp": 1234567890.0,
                    }
                },
                expected_params={"AccountId": "123456789012"},
            )

            result = adapter.get_account_details("123456789012")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data["Id"] == "123456789012"
        assert result.data["Email"] == "account@example.com"


class TestGetAccountTags:
    """ListTagsForResource returns tags for an account, paginated."""

    def test_get_account_tags_success_single_page(self) -> None:
        """ListTagsForResource with single page returns list of tags."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_tags_for_resource",
                {
                    "Tags": [
                        {"Key": "Environment", "Value": "Production"},
                        {"Key": "Owner", "Value": "TeamA"},
                    ]
                },
                expected_params={"ResourceId": "123456789012"},
            )

            result = adapter.get_account_tags("123456789012")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["Key"] == "Environment"

    def test_get_account_tags_pagination_two_pages(self) -> None:
        """ListTagsForResource paginates across pages via NextToken.

        This test verifies the bug fix: the legacy mirror did not paginate
        ListTagsForResource, so accounts with >1 page of tags would silently lose tags.
        The adapter's _paginate helper correctly handles pagination.
        """
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_tags_for_resource",
                {
                    "Tags": [{"Key": "Environment", "Value": "Production"}],
                    "NextToken": "tags-token",
                },
                expected_params={"ResourceId": "123456789012"},
            )
            stub.add_response(
                "list_tags_for_resource",
                {
                    "Tags": [{"Key": "Owner", "Value": "TeamA"}],
                },
                expected_params={"ResourceId": "123456789012", "NextToken": "tags-token"},
            )

            result = adapter.get_account_tags("123456789012")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [t["Key"] for t in result.data] == ["Environment", "Owner"]

    def test_get_account_tags_empty(self) -> None:
        """ListTagsForResource with no tags returns empty list."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_tags_for_resource",
                {"Tags": []},
                expected_params={"ResourceId": "123456789012"},
            )

            result = adapter.get_account_tags("123456789012")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestHealthcheck:
    """Healthcheck succeeds when ListAccounts returns."""

    def test_healthcheck_succeeds_on_empty_and_nonempty_page(self) -> None:
        """Healthcheck succeeds (returns True) on both empty and non-empty account lists."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        # Test with empty page
        with Stubber(client) as stub:
            stub.add_response(
                "list_accounts",
                {"Accounts": []},
                expected_params={"MaxResults": 1},
            )

            result = adapter.healthcheck()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True

        # Test with non-empty page
        with Stubber(client) as stub:
            stub.add_response(
                "list_accounts",
                {
                    "Accounts": [
                        {
                            "Id": "123456789012",
                            "Arn": "arn:aws:organizations::123456789012:account/o-1234567890/123456789012",
                            "Email": "account@example.com",
                            "Name": "Account",
                            "Status": "ACTIVE",
                            "JoinedMethod": "CREATED",
                            "JoinedTimestamp": 1234567890.0,
                        }
                    ]
                },
                expected_params={"MaxResults": 1},
            )

            result = adapter.healthcheck()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_resource_not_found_classification(self) -> None:
        """ResourceNotFoundException maps to NOT_FOUND."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_accounts",
                service_error_code="ResourceNotFoundException",
                http_status_code=404,
            )

            result = adapter.list_organization_accounts()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "ResourceNotFoundException"

    def test_access_denied_classification(self) -> None:
        """AccessDeniedException maps to UNAUTHORIZED."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_accounts",
                service_error_code="AccessDeniedException",
                http_status_code=403,
            )

            result = adapter.list_organization_accounts()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == "AccessDeniedException"

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "describe_account",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.get_account_details("123456789012")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://organizations.ca-central-1.amazonaws.com")

            stub.client.list_accounts = raise_endpoint_error

            result = adapter.list_organization_accounts()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "describe_account",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.get_account_details("invalid")

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _organizations_client()
        adapter = OrganizationsAdapter(client=client)

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.list_accounts = raise_key_error

            with pytest.raises(KeyError):
                adapter.list_organization_accounts()

            stub.assert_no_pending_responses()
