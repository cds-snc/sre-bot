"""Tests for GuardDutyClient.

Validates AWS GuardDuty operations with default role fallback and service_name resolution.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.guard_duty import GuardDutyClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestGuardDutyClient:
    """Test suite for GuardDutyClient."""

    def test_init_with_default_role_arn(self):
        """Test GuardDutyClient initialization with default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/GuardDutyRole",
        )
        assert (
            client._default_role_arn == "arn:aws:iam::123456789012:role/GuardDutyRole"
        )
        assert client.service_name == "guardduty"

    def test_init_without_default_role_arn(self):
        """Test GuardDutyClient initialization without default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(session_provider=session_provider)
        assert client._default_role_arn is None

    def test_list_detectors_with_default_role(self, monkeypatch, make_fake_client):
        """Test list_detectors uses default_role_arn when not provided."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::123456789012:role/DefaultRole"
            return make_fake_client(
                api_responses={"list_detectors": {"DetectorIds": ["detector-123"]}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_detectors()
        assert result.is_success

    def test_list_detectors_multiple_detectors(self, monkeypatch, make_fake_client):
        """Test list_detectors returns multiple detector IDs."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::123456789012:role/DefaultRole"
            return make_fake_client(
                api_responses={
                    "list_detectors": {"DetectorIds": ["detector-1", "detector-2"]}
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_detectors()
        assert result.is_success

    def test_healthcheck_success(self, monkeypatch, make_fake_client):
        """Test healthcheck returns success for reachable GuardDuty."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={"list_detectors": {"DetectorIds": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.healthcheck()
        assert result.is_success
