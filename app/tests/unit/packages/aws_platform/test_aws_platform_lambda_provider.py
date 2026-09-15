"""Behavior tests for build_lambda_adapter client construction.

get_aws_client is patched in the adapter module to record its arguments and
return a real boto3 lambda client with dummy static credentials. The Lambda
adapter calls get_aws_client with role_arn=None (no SERVICE_ROLE_MAP entry),
and the settings cache is cleared around each test to pin that the factory
reads from the settings even when role ARN environment variables are set.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.aws_lambda import LambdaAdapter, build_lambda_adapter

pytestmark = pytest.mark.unit


def _lambda_client() -> Any:
    """Build a real boto3 lambda client with dummy static credentials."""
    return boto3.client(
        "lambda",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildLambdaAdapter:
    """build_lambda_adapter builds one lambda client through get_aws_client with role_arn=None."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self) -> Iterator[None]:
        """Clear settings cache before and after each test."""
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def _build_recording(self, calls: list[dict[str, Any]]) -> LambdaAdapter:
        def record_get_aws_client(service_name: str, *, role_arn: str | None = None, **kwargs: Any) -> Any:
            calls.append({"service_name": service_name, "role_arn": role_arn, **kwargs})
            return _lambda_client()

        with patch(
            "packages.aws_platform.adapters.aws_lambda.get_aws_client",
            side_effect=record_get_aws_client,
            create=True,
        ):
            return build_lambda_adapter()

    def test_single_lambda_client_with_role_arn_none(self) -> None:
        """One get_aws_client('lambda') call carries role_arn=None (no SERVICE_ROLE_MAP entry)."""
        calls: list[dict[str, Any]] = []

        adapter = self._build_recording(calls)

        assert isinstance(adapter, LambdaAdapter)
        assert len(calls) == 1
        assert calls[0]["service_name"] == "lambda"
        assert calls[0]["role_arn"] is None

    def test_role_arn_none_even_when_all_role_env_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """role_arn=None even when AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, AWS_LOGGING_ACCOUNT_ROLE_ARN are set."""
        monkeypatch.setenv("AWS_AUDIT_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/audit-role")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")
        monkeypatch.setenv("AWS_LOGGING_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/logging-role")
        calls: list[dict[str, Any]] = []

        self._build_recording(calls)

        assert calls[0]["role_arn"] is None
