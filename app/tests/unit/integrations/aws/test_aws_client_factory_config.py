"""Behavior tests for the typed AWS client factory's construction policy.

Real boto3 clients are built (no credentials, no network: construction never
calls AWS) and the policy is asserted through the public ``client.meta``
surface: retry mode and attempt budget, per-attempt timeouts, and the region and
dynamodb-local endpoint, which the SDK alone resolves (AWS_DEFAULT_REGION or the
shared config file, AWS_ENDPOINT_URL_DYNAMODB). The tuning comes from the
installed configuration files, so the assertions prove the values reach botocore
rather than a fake.
"""

from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import NoRegionError

from integrations.aws import client as aws_client
from tests.unit.integrations.aws.conftest import install_aws_files

pytestmark = pytest.mark.unit

_LOCAL_DYNAMODB = "http://dynamodb-local:8000"
_REGIONAL_DYNAMODB = "https://dynamodb.ca-central-1.amazonaws.com"
_REGIONAL_IDENTITYSTORE = "https://identitystore.ca-central-1.amazonaws.com"


@pytest.fixture(autouse=True)
def _sdk_region(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Resolve the region the way the deployment does: AWS_DEFAULT_REGION, with no shared config file."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ca-central-1")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-credentials"))


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

    def test_file_overrides_reach_the_botocore_config(self, tmp_path: Path) -> None:
        install_aws_files(
            tmp_path,
            "[aws]\nretry_mode = 'standard'\nretry_max_attempts = 3\nconnect_timeout_seconds = 10\nread_timeout_seconds = 10\n",
            "[aws]\nretry_mode = 'adaptive'\nretry_max_attempts = 5\nconnect_timeout_seconds = 2\nread_timeout_seconds = 7\n",
        )

        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.config.retries == {"mode": "adaptive", "total_max_attempts": 6}
        assert client.meta.config.connect_timeout == 2
        assert client.meta.config.read_timeout == 7

    def test_retries_disabled_ignores_the_configured_attempt_budget(self, tmp_path: Path) -> None:
        install_aws_files(tmp_path, "[aws]\nretry_max_attempts = 5\n")

        client = aws_client.get_aws_client("dynamodb", retries=False)

        assert client.meta.config.retries["total_max_attempts"] == 1


class TestRegion:
    """The region is the SDK's: the factory names none and never defaults one."""

    def test_region_comes_from_aws_default_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        client = aws_client.get_aws_client("identitystore")

        assert client.meta.region_name == "eu-west-1"

    def test_aws_region_alone_is_not_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """botocore reads AWS_DEFAULT_REGION, not AWS_REGION, so the factory leaves the name unread too."""
        monkeypatch.delenv("AWS_DEFAULT_REGION")
        monkeypatch.setenv("AWS_REGION", "eu-west-1")

        with pytest.raises(NoRegionError):
            aws_client.get_aws_client("identitystore")

    def test_no_region_anywhere_fails_instead_of_defaulting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The deployment must supply a region (ECS injects AWS_DEFAULT_REGION); the code carries no default."""
        monkeypatch.delenv("AWS_DEFAULT_REGION")

        with pytest.raises(NoRegionError):
            aws_client.get_aws_client("dynamodb")

    def test_assumed_role_session_is_built_in_the_resolved_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AssumeRole builds the STS client and the assumed session without naming a region of their own."""
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        credentials = {"AccessKeyId": "k", "SecretAccessKey": "s", "SessionToken": "t"}

        with patch.object(aws_client, "_assume_role_credentials", return_value=credentials) as assume:
            client = aws_client.get_aws_client("identitystore", role_arn="arn:aws:iam::123456789012:role/org-role")

        assume.assert_called_once()
        assert assume.call_args.args[0].meta.region_name == "eu-west-1"
        assert client.meta.region_name == "eu-west-1"


class TestDynamoDbLocalEndpointGate:
    """The SDK honours AWS_ENDPOINT_URL_DYNAMODB for dynamodb only; the factory sets no endpoint."""

    def test_dynamodb_uses_the_sdk_local_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ENDPOINT_URL_DYNAMODB", _LOCAL_DYNAMODB)

        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.endpoint_url == _LOCAL_DYNAMODB

    def test_dynamodb_uses_the_regional_endpoint_when_nothing_is_configured(self) -> None:
        client = aws_client.get_aws_client("dynamodb")

        assert client.meta.endpoint_url == _REGIONAL_DYNAMODB

    def test_other_services_ignore_the_dynamodb_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ENDPOINT_URL_DYNAMODB", _LOCAL_DYNAMODB)

        client = aws_client.get_aws_client("identitystore")

        assert client.meta.endpoint_url == _REGIONAL_IDENTITYSTORE

    def test_factory_passes_no_region_or_endpoint_to_the_session(self) -> None:
        """The region and endpoint are never arguments of the factory's own session or client calls."""
        with patch.object(boto3, "Session", wraps=boto3.Session) as session:
            aws_client.get_aws_client("dynamodb")

        assert session.call_args.kwargs == {}


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
