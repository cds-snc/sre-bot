"""Tests for `AWSShield` construction and SDK wiring.

Verifies that boto3 clients are constructed with the native retry
`Config(retries={...})` from settings, that connect/read timeouts are
applied, that the typed per-service handles are exposed as shape γ
attributes, and that the session cache is preserved across calls.
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


class TestAWSShieldTypedHandles:
    """`AWSShield` exposes per-service boto3 client handles as shape γ attributes."""

    def test_dynamodb_handle_constructs_dynamodb_client(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.dynamodb
            assert mock_create.call_args.args[0] == "dynamodb"

    def test_s3_handle_constructs_s3_client(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.s3
            assert mock_create.call_args.args[0] == "s3"

    def test_organizations_handle_constructs_organizations_client(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.organizations
            assert mock_create.call_args.args[0] == "organizations"

    def test_identity_store_handle_constructs_identitystore_client(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.identity_store
            assert mock_create.call_args.args[0] == "identitystore"

    def test_handle_applies_native_retry_config(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.dynamodb
            config = mock_create.call_args.kwargs["config"]
            assert config.retries == {"max_attempts": 3, "mode": "standard"}

    def test_handle_applies_connect_and_read_timeouts(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.dynamodb
            config = mock_create.call_args.kwargs["config"]
            assert config.connect_timeout == 10
            assert config.read_timeout == 10

    def test_handle_uses_settings_region(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.dynamodb
            assert mock_create.call_args.kwargs["region_name"] == "us-east-1"

    def test_handle_passes_endpoint_url_when_set(self) -> None:
        settings = AWSSettings(
            AWS_REGION="us-east-1", AWS_ENDPOINT_URL="http://localhost:4566"
        )
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.dynamodb
            assert mock_create.call_args.kwargs["endpoint_url"] == "http://localhost:4566"

    def test_handle_passes_none_endpoint_url_when_unset(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.return_value = MagicMock()
            _ = shield.dynamodb
            assert mock_create.call_args.kwargs["endpoint_url"] is None


class TestAWSShieldSessionCache:
    """One boto3 client is created per service per shield instance."""

    def test_same_handle_is_cached_across_calls(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.side_effect = lambda *a, **kw: MagicMock()
            first = shield.dynamodb
            second = shield.dynamodb
            assert first is second
            assert mock_create.call_count == 1

    def test_different_handles_are_cached_independently(self, settings: AWSSettings) -> None:
        shield = AWSShield(settings=settings)
        with patch.object(shield._session, "client") as mock_create:
            mock_create.side_effect = lambda *a, **kw: MagicMock()
            ddb = shield.dynamodb
            s3 = shield.s3
            assert ddb is not s3
            assert mock_create.call_count == 2


class TestAWSShieldLaziness:
    """Shield construction has no side effects until a handle is accessed."""

    def test_init_does_not_create_clients(self, settings: AWSSettings) -> None:
        with patch("integrations.aws.shield.boto3.session.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            AWSShield(settings=settings)
            mock_session.client.assert_not_called()
