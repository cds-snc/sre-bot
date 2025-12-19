"""Tests for ConfigClient.

Validates AWS Config operations with default role fallback and service_name resolution.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.config import ConfigClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestConfigClient:
    """Test suite for ConfigClient."""

    def test_init_with_default_role_arn(self):
        """Test ConfigClient initialization with default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/ConfigRole",
        )
        assert client._default_role_arn == "arn:aws:iam::123456789012:role/ConfigRole"
        assert client._service_name == "config"

    def test_init_without_default_role_arn(self):
        """Test ConfigClient initialization without default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(session_provider=session_provider)
        assert client._default_role_arn is None

    def test_describe_aggregate_compliance_by_config_rules_success(
        self, monkeypatch, make_fake_client
    ):
        """Test describe_aggregate_compliance_by_config_rules returns compliance data."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "describe_aggregate_compliance_by_config_rules": {
                        "AggregateComplianceByConfigRules": [
                            {
                                "ConfigRuleName": "required-tags",
                                "Compliance": {"ComplianceType": "COMPLIANT"},
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.describe_aggregate_compliance_by_config_rules(
            configuration_aggregator_name="org-aggregator"
        )
        assert result.is_success

    def test_describe_aggregate_compliance_by_config_rules_explicit_role(
        self, monkeypatch, make_fake_client
    ):
        """Test describe_aggregate_compliance_by_config_rules with explicit role."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::999999999999:role/OverrideRole"
            return make_fake_client(
                api_responses={
                    "describe_aggregate_compliance_by_config_rules": {
                        "AggregateComplianceByConfigRules": []
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.describe_aggregate_compliance_by_config_rules(
            configuration_aggregator_name="org-aggregator",
            role_arn="arn:aws:iam::999999999999:role/OverrideRole",
        )
        assert result.is_success

    def test_describe_aggregate_compliance_by_config_rules_uses_default_role(
        self, monkeypatch, make_fake_client
    ):
        """Test describe_aggregate_compliance_by_config_rules uses default_role_arn."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::123456789012:role/DefaultRole"
            return make_fake_client(
                api_responses={
                    "describe_aggregate_compliance_by_config_rules": {
                        "AggregateComplianceByConfigRules": []
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.describe_aggregate_compliance_by_config_rules(
            configuration_aggregator_name="org-aggregator"
        )
        assert result.is_success

    def test_put_config_rule_success(self, monkeypatch, make_fake_client):
        """Test put_config_rule creates or updates a config rule."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "put_config_rule": {"ConfigRuleArn": "arn:aws:config:..."}
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        config_rule = {
            "ConfigRuleName": "required-tags",
            "Source": {
                "Owner": "AWS",
                "SourceIdentifier": "REQUIRED_TAGS",
            },
        }
        result = client.put_config_rule(config_rule=config_rule)
        assert result.is_success

    def test_delete_config_rule_success(self, monkeypatch, make_fake_client):
        """Test delete_config_rule removes a config rule."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"delete_config_rule": {}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.delete_config_rule(config_rule_name="required-tags")
        assert result.is_success

    def test_describe_config_rules_success(self, monkeypatch, make_fake_client):
        """Test describe_config_rules returns config rules."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "describe_config_rules": {
                        "ConfigRules": [
                            {
                                "ConfigRuleName": "required-tags",
                                "Source": {
                                    "Owner": "AWS",
                                    "SourceIdentifier": "REQUIRED_TAGS",
                                },
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.describe_config_rules()
        assert result.is_success

    def test_healthcheck_success(self, monkeypatch, make_fake_client):
        """Test healthcheck returns success for reachable Config."""

        session_provider = SessionProvider(region="us-east-1")
        client = ConfigClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={"describe_config_rules": {"ConfigRules": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.healthcheck()
        assert result.is_success
