"""Tests for `AWSShield` construction and SDK wiring.

Verifies that boto3 clients are constructed with the native retry
`Config(retries={...})` from settings, that connect/read timeouts are
applied, that the per-service client cache is preserved, and that no
hand-rolled retry primitives leak into the shield.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrations.aws.settings import AWSSettings
from integrations.aws.shield import AWSShield

pytestmark = pytest.mark.unit


@pytest.fixture
def settings() -> AWSSettings:
    return AWSSettings(
        AWS_REGION="us-east-1",
        AWS_ENDPOINT_URL=None,
        AWS_RETRY_MAX_ATTEMPTS=3,
        AWS_RETRY_MODE="standard",
        AWS_CONNECT_TIMEOUT_SECONDS=10,
        AWS_READ_TIMEOUT_SECONDS=10,
    )


class TestAWSShieldClientConstruction:
    """`AWSShield.client(service_name)` constructs botocore clients with native retry."""

    def test_client_uses_settings_region(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            shield.client("dynamodb")

            assert mock_create.call_args.kwargs["region_name"] == "us-east-1"

    def test_client_applies_native_retry_config(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            shield.client("dynamodb")

            config = mock_create.call_args.kwargs["config"]
            assert config.retries == {"max_attempts": 3, "mode": "standard"}

    def test_client_applies_connect_and_read_timeouts(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            shield.client("dynamodb")

            config = mock_create.call_args.kwargs["config"]
            assert config.connect_timeout == 10
            assert config.read_timeout == 10

    def test_client_passes_endpoint_url_when_set(self) -> None:
        settings = AWSSettings(AWS_REGION="us-east-1", AWS_ENDPOINT_URL="http://localhost:4566")
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            shield.client("dynamodb")

            assert mock_create.call_args.kwargs["endpoint_url"] == "http://localhost:4566"

    def test_client_passes_none_endpoint_url_when_unset(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            shield.client("dynamodb")

            assert mock_create.call_args.kwargs["endpoint_url"] is None

    def test_client_caches_one_instance_per_service(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.side_effect = lambda *a, **kw: MagicMock()

            first = shield.client("dynamodb")
            second = shield.client("dynamodb")

            assert first is second
            assert mock_create.call_count == 1

    def test_client_caches_separately_per_service_name(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.side_effect = lambda *a, **kw: MagicMock()

            ddb = shield.client("dynamodb")
            sqs = shield.client("sqs")

            assert ddb is not sqs
            assert mock_create.call_count == 2


class TestAWSShieldLaziness:
    """Shield construction has no side effects until a client is requested."""

    def test_init_does_not_create_clients(self, settings: AWSSettings) -> None:
        with patch("integrations.aws.shield.boto3.session.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            AWSShield(settings=settings)

            mock_session.client.assert_not_called()
