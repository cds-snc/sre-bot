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
        assert client._service_name == "guardduty"

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

    def test_list_detectors_explicit_role_overrides_default(
        self, monkeypatch, make_fake_client
    ):
        """Test list_detectors explicit role_arn overrides default."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::999999999999:role/OverrideRole"
            return make_fake_client(
                api_responses={"list_detectors": {"DetectorIds": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_detectors(
            role_arn="arn:aws:iam::999999999999:role/OverrideRole"
        )
        assert result.is_success

    def test_get_detector_success(self, monkeypatch, make_fake_client):
        """Test get_detector returns detector details."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "get_detector": {
                        "DetectorId": "detector-123",
                        "Status": "ENABLED",
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_detector(detector_id="detector-123")
        assert result.is_success

    def test_list_findings_success(self, monkeypatch, make_fake_client):
        """Test list_findings returns finding IDs."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "list_findings": {"FindingIds": ["finding-123", "finding-456"]}
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_findings(detector_id="detector-123")
        assert result.is_success

    def test_get_findings_success(self, monkeypatch, make_fake_client):
        """Test get_findings returns findings details."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "get_findings": {
                        "Findings": [
                            {
                                "Id": "finding-123",
                                "Type": "UnauthorizedAccess",
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_findings(
            detector_id="detector-123",
            finding_ids=["finding-123"],
        )
        assert result.is_success

    def test_create_threat_intel_set_success(self, monkeypatch, make_fake_client):
        """Test create_threat_intel_set creates a threat intel set."""

        session_provider = SessionProvider(region="us-east-1")
        client = GuardDutyClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "create_threat_intel_set": {"ThreatIntelSetId": "tis-123"}
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.create_threat_intel_set(
            detector_id="detector-123",
            format="TXT",
            location="s3://bucket/list.txt",
            name="My Threat Intel",
        )
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
