"""Behavior tests for build_security_hub_adapter client construction.

get_aws_client is patched in the adapter module to record its arguments and
return a real boto3 securityhub client with dummy static credentials. The logging
role comes from the tenant's logging_role_arn and the settings cache is cleared
around each test, so the assertions pin the service name and the role ARN the
factory reads from service_role_map.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.security_hub import SecurityHubAdapter, build_security_hub_adapter
from tests.factories.aws import set_aws_tenant

pytestmark = pytest.mark.unit


def _security_hub_client() -> Any:
    """Build a real boto3 securityhub client with dummy static credentials."""
    return boto3.client(
        "securityhub",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildSecurityHubAdapter:
    """build_security_hub_adapter builds one securityhub client through get_aws_client."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self) -> Iterator[None]:
        """Clear settings cache before and after each test."""
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def _build_recording(self, calls: list[dict[str, Any]]) -> SecurityHubAdapter:
        def record_get_aws_client(service_name: str, *, role_arn: str | None = None, **kwargs: Any) -> Any:
            calls.append({"service_name": service_name, "role_arn": role_arn, **kwargs})
            return _security_hub_client()

        with patch(
            "packages.aws_platform.adapters.security_hub.get_aws_client",
            side_effect=record_get_aws_client,
            create=True,
        ):
            return build_security_hub_adapter()

    def test_single_security_hub_client_with_logging_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One get_aws_client('securityhub') call carries service_role_map['securityhub']."""
        set_aws_tenant(monkeypatch, logging_role_arn="arn:aws:iam::123456789012:role/logging-role")
        calls: list[dict[str, Any]] = []

        adapter = self._build_recording(calls)

        assert isinstance(adapter, SecurityHubAdapter)
        assert len(calls) == 1
        assert calls[0]["service_name"] == "securityhub"
        assert calls[0]["role_arn"] == "arn:aws:iam::123456789012:role/logging-role"

    def test_role_arn_none_when_setting_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty logging_role_arn is passed as role_arn=None, not an empty string."""
        set_aws_tenant(monkeypatch, logging_role_arn="")
        calls: list[dict[str, Any]] = []

        self._build_recording(calls)

        assert calls[0]["role_arn"] is None
