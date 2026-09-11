"""Behavior tests for the typed AWS client factory's construction policy.

Real boto3 clients are built (no credentials, no network: construction never
calls AWS) and the policy is asserted through the public ``client.meta``
surface: retry mode and attempt budget, per-attempt timeouts, region and the
dynamodb-only local endpoint. Settings come from ``integrations.aws.settings``
and are exercised through real environment variables plus a provider cache
clear, so the assertions prove the overrides reach botocore rather than a fake.
"""

from __future__ import annotations

import pytest

from integrations.aws import client as aws_client
from integrations.aws.settings import get_aws_settings

pytestmark = pytest.mark.unit

_LOCAL_DYNAMODB = "http://dynamodb-local:8000"
_REGIONAL_DYNAMODB = "https://dynamodb.ca-central-1.amazonaws.com"
_REGIONAL_IDENTITYSTORE = "https://identitystore.ca-central-1.amazonaws.com"


def _reload_settings() -> None:
    """Drop the cached settings so freshly set environment variables are read."""
    get_aws_settings.cache_clear()


class TestRetryAndTimeoutPolicy:
    """Every client carries the SDK-native retry and timeout policy set once at construction."""

    def test_default_client_uses_standard_retries_with_three_retries_after_the_first_attempt(self) -> None:
        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 4}
        assert client.meta.config.connect_timeout == 10
        assert client.meta.config.read_timeout == 10

    def test_retries_disabled_variant_makes_exactly_one_attempt_with_the_same_timeouts(self) -> None:
        client = aws_client.get_aws_client("dynamodb", retries=False)

        assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 1}
        assert client.meta.config.connect_timeout == 10
        assert client.meta.config.read_timeout == 10

    def test_environment_overrides_reach_the_botocore_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_RETRY_MODE", "adaptive")
        monkeypatch.setenv("AWS_RETRY_MAX_ATTEMPTS", "5")
        monkeypatch.setenv("AWS_CONNECT_TIMEOUT_SECONDS", "2")
        monkeypatch.setenv("AWS_READ_TIMEOUT_SECONDS", "7")
        _reload_settings()

        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.config.retries == {"mode": "adaptive", "total_max_attempts": 6}
        assert client.meta.config.connect_timeout == 2
        assert client.meta.config.read_timeout == 7

    def test_retries_disabled_ignores_the_configured_attempt_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_RETRY_MAX_ATTEMPTS", "5")
        _reload_settings()

        client = aws_client.get_aws_client("dynamodb", retries=False)

        assert client.meta.config.retries["total_max_attempts"] == 1


class TestRegion:
    """The region is read from settings and applied to the client."""

    def test_default_region_is_ca_central_1(self) -> None:
        client = aws_client.get_aws_client("identitystore")

        assert client.meta.region_name == "ca-central-1"

    def test_region_override_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        _reload_settings()

        client = aws_client.get_aws_client("identitystore")

        assert client.meta.region_name == "eu-west-1"


class TestDynamoDbLocalEndpointGate:
    """The local endpoint applies to dynamodb only, and only when configured."""

    def test_dynamodb_uses_the_configured_local_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ENDPOINT_URL_DYNAMODB", _LOCAL_DYNAMODB)
        _reload_settings()

        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.endpoint_url == _LOCAL_DYNAMODB

    def test_dynamodb_uses_the_regional_endpoint_when_nothing_is_configured(self) -> None:
        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.endpoint_url == _REGIONAL_DYNAMODB

    def test_other_services_ignore_the_dynamodb_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ENDPOINT_URL_DYNAMODB", _LOCAL_DYNAMODB)
        _reload_settings()

        client = aws_client.get_aws_client("identitystore")

        assert client.meta.endpoint_url == _REGIONAL_IDENTITYSTORE

    def test_factory_no_longer_depends_on_the_application_environment_setting(self) -> None:
        """The gate is driven by AWS settings alone; the application settings module is not consulted."""
        assert not hasattr(aws_client, "get_app_settings")
        assert not hasattr(aws_client, "app_settings")


class TestServiceSelection:
    """Each supported service name builds a client for that service, per call, never cached."""

    @pytest.mark.parametrize(
        "service_name",
        [
            "dynamodb",
            "identitystore",
            "organizations",
            "sso-admin",
            "ce",
            "config",
            "guardduty",
            "securityhub",
            "lambda",
            "sts",
        ],
    )
    def test_builds_a_client_for_the_requested_service(self, service_name: str) -> None:
        client = aws_client.get_aws_client(service_name)  # type: ignore[call-overload]

        assert client.meta.service_model.service_name == service_name

    def test_each_call_builds_a_fresh_client(self) -> None:
        first = aws_client.get_aws_client("dynamodb")
        second = aws_client.get_aws_client("dynamodb")

        assert first is not second

    def test_legacy_session_and_client_config_kwargs_are_rejected(self) -> None:
        with pytest.raises(TypeError):
            aws_client.get_aws_client("dynamodb", session_config={"region_name": "us-east-1"})  # type: ignore[call-overload]
        with pytest.raises(TypeError):
            aws_client.get_aws_client("dynamodb", client_config={"endpoint_url": _LOCAL_DYNAMODB})  # type: ignore[call-overload]
