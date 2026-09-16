"""Behavior tests for build_dynamodb_adapter and client routing.

The provider is monkeypatched to record get_aws_client calls and verify routing:
two calls to get_aws_client('dynamodb', ...), the second with retries=False.
Environment variables AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, and
AWS_LOGGING_ACCOUNT_ROLE_ARN are set to verify that dynamodb has no SERVICE_ROLE_MAP
entry and always receives role_arn=None. get_aws_settings cache is cleared before
and after each test.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.dynamodb import build_dynamodb_adapter

pytestmark = pytest.mark.unit


def _dynamodb_client() -> Any:
    """Build a real boto3 dynamodb client with dummy static credentials."""
    return boto3.client(
        "dynamodb",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildDynamoDBAdapter:
    """build_dynamodb_adapter builds two dynamodb clients with role_arn=None."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self) -> Iterator[None]:
        """Clear settings cache before and after each test."""
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def test_two_get_aws_client_calls_standard_and_no_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """build_dynamodb_adapter calls get_aws_client twice: standard and no-retry."""
        get_aws_client_calls: list[dict[str, Any]] = []

        def record_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            get_aws_client_calls.append(
                {
                    "service_name": service_name,
                    "role_arn": role_arn,
                    "session_name": session_name,
                    "retries": retries,
                }
            )
            return _dynamodb_client()

        with patch(
            "packages.aws_platform.adapters.dynamodb.get_aws_client",
            side_effect=record_get_aws_client,
        ):
            _ = build_dynamodb_adapter()

        assert len(get_aws_client_calls) == 2
        # First call: standard retry
        assert get_aws_client_calls[0]["service_name"] == "dynamodb"
        assert get_aws_client_calls[0]["role_arn"] is None
        assert get_aws_client_calls[0]["retries"] is True

        # Second call: no retry
        assert get_aws_client_calls[1]["service_name"] == "dynamodb"
        assert get_aws_client_calls[1]["role_arn"] is None
        assert get_aws_client_calls[1]["retries"] is False

    def test_role_arn_always_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Role ARN is None even when AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, AWS_LOGGING_ACCOUNT_ROLE_ARN are set."""
        monkeypatch.setenv("AWS_AUDIT_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/audit-role")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")
        monkeypatch.setenv("AWS_LOGGING_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/logging-role")
        get_aws_client_calls: list[dict[str, Any]] = []

        def record_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            get_aws_client_calls.append({"role_arn": role_arn})
            return _dynamodb_client()

        with patch(
            "packages.aws_platform.adapters.dynamodb.get_aws_client",
            side_effect=record_get_aws_client,
        ):
            _ = build_dynamodb_adapter()

        # Both calls should have None role ARN
        assert get_aws_client_calls[0]["role_arn"] is None
        assert get_aws_client_calls[1]["role_arn"] is None
