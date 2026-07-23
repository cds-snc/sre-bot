"""Tests for SessionProvider role resolution behavior."""

import pytest

from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestSessionProvider:
    """Validate role resolution and boto3 client construction."""

    def test_get_boto3_client_preserves_explicit_role_arn(self, monkeypatch):
        """Explicit role_arn should be passed through unchanged."""
        captured = {}

        def fake_get_boto3_client(
            service_name,
            session_config=None,
            client_config=None,
            role_arn=None,
            session_name="InfraClientSession",
        ):
            captured["service_name"] = service_name
            captured["role_arn"] = role_arn
            captured["session_config"] = session_config
            captured["client_config"] = client_config
            captured["session_name"] = session_name
            return object()

        monkeypatch.setattr(
            "infrastructure.clients.aws.session_provider.get_boto3_client",
            fake_get_boto3_client,
        )

        provider = SessionProvider(
            region="ca-central-1",
            service_role_map={"identitystore": "arn:aws:iam::123456789012:role/Mapped"},
        )
        provider.get_boto3_client(
            "identitystore",
            role_arn="arn:aws:iam::123456789012:role/Explicit",
        )

        assert captured["service_name"] == "identitystore"
        assert captured["role_arn"] == "arn:aws:iam::123456789012:role/Explicit"
        assert captured["session_config"] == {"region_name": "ca-central-1"}

    def test_get_boto3_client_uses_service_role_map_when_role_missing(self, monkeypatch):
        """Mapped service role should be used when role_arn is not provided."""
        captured = {}

        def fake_get_boto3_client(
            service_name,
            session_config=None,
            client_config=None,
            role_arn=None,
            session_name="InfraClientSession",
        ):
            captured["service_name"] = service_name
            captured["role_arn"] = role_arn
            return object()

        monkeypatch.setattr(
            "infrastructure.clients.aws.session_provider.get_boto3_client",
            fake_get_boto3_client,
        )

        provider = SessionProvider(
            region="ca-central-1",
            service_role_map={"identitystore": "arn:aws:iam::123456789012:role/Mapped"},
        )
        provider.get_boto3_client("identitystore")

        assert captured["service_name"] == "identitystore"
        assert captured["role_arn"] == "arn:aws:iam::123456789012:role/Mapped"

    def test_build_client_kwargs_applies_endpoint_override_only_to_dynamodb(self):
        """Custom endpoints should be scoped to DynamoDB local development only."""
        provider = SessionProvider(
            region="ca-central-1",
            endpoint_url="http://dynamodb-local:8000",
        )

        dynamodb_kwargs = provider.build_client_kwargs(service_name="dynamodb")
        identitystore_kwargs = provider.build_client_kwargs(service_name="identitystore")

        assert dynamodb_kwargs["client_config"] == {
            "region_name": "ca-central-1",
            "endpoint_url": "http://dynamodb-local:8000",
        }
        assert identitystore_kwargs["client_config"] == {"region_name": "ca-central-1"}
