"""Tests for DynamoDBClient.

Validates DynamoDB operations with default role fallback and service_name resolution.
"""

import pytest
from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.dynamodb import DynamoDBClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestDynamoDBClient:
    """Test suite for DynamoDBClient."""

    def test_init_with_default_role_arn(self):
        """Test DynamoDBClient initialization with default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DynamoDBRole",
        )
        assert client._default_role_arn == "arn:aws:iam::123456789012:role/DynamoDBRole"
        assert client._service_name == "dynamodb"

    def test_init_without_default_role_arn(self):
        """Test DynamoDBClient initialization without default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(session_provider=session_provider)
        assert client._default_role_arn is None
        assert client._service_name == "dynamodb"

    def test_get_item_uses_default_role(self, monkeypatch, make_fake_client):
        """Test get_item falls back to default_role_arn when not provided."""

        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::123456789012:role/DefaultRole"
            return make_fake_client(
                api_responses={"get_item": {"Item": {"id": {"S": "123"}}}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_item("my_table", {"id": {"S": "123"}})
        assert result.is_success
        assert result.data == {"Item": {"id": {"S": "123"}}}

    def test_get_item_explicit_role_overrides_default(
        self, monkeypatch, make_fake_client
    ):
        """Test get_item explicit role_arn overrides default."""

        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::999999999999:role/OverrideRole"
            return make_fake_client(api_responses={"get_item": {"Item": {}}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_item(
            "my_table",
            {"id": {"S": "123"}},
            role_arn="arn:aws:iam::999999999999:role/OverrideRole",
        )
        assert result.is_success

    def test_put_item_success(self, monkeypatch, make_fake_client):
        """Test put_item succeeds with valid parameters."""

        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"put_item": {}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.put_item(
            "my_table", {"id": {"S": "123"}, "data": {"S": "test"}}
        )
        assert result.is_success

    def test_scan_with_pagination(self, monkeypatch, make_fake_client):
        """Test scan operation with paginated results."""

        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(session_provider=session_provider)

        pages = [
            {"Items": [{"id": {"S": "1"}}], "Count": 1},
            {"Items": [{"id": {"S": "2"}}], "Count": 1},
        ]

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(paginated_pages=pages)

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.scan("my_table")
        assert result.is_success

    def test_healthcheck_success(self, monkeypatch, make_fake_client):
        """Test healthcheck returns success for reachable DynamoDB."""

        session_provider = SessionProvider(region="us-east-1")
        client = DynamoDBClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"list_tables": {"TableNames": []}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.healthcheck()
        assert result.is_success
