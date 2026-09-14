"""Behavior tests for build_config_adapter client construction.

get_aws_client is patched in the adapter module to record its arguments and
return a real boto3 config client with dummy static credentials. The config
role comes from AWS_CONFIG_ROLE_ARN and the settings cache is cleared
around each test, so the assertions pin the service name and the role ARN the
factory reads from SERVICE_ROLE_MAP.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.config import ConfigAdapter, build_config_adapter

pytestmark = pytest.mark.unit


def _config_client() -> Any:
    """Build a real boto3 config client with dummy static credentials."""
    return boto3.client(
        "config",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildConfigAdapter:
    """build_config_adapter builds one config client through get_aws_client."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self) -> Iterator[None]:
        """Clear settings cache before and after each test."""
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def _build_recording(self, calls: list[dict[str, Any]]) -> ConfigAdapter:
        def record_get_aws_client(service_name: str, *, role_arn: str | None = None, **kwargs: Any) -> Any:
            calls.append({"service_name": service_name, "role_arn": role_arn, **kwargs})
            return _config_client()

        with patch(
            "packages.aws_platform.adapters.config.get_aws_client",
            side_effect=record_get_aws_client,
            create=True,
        ):
            return build_config_adapter()

    def test_single_config_client_with_audit_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One get_aws_client('config') call carries SERVICE_ROLE_MAP['config']."""
        monkeypatch.setenv("AWS_CONFIG_ROLE_ARN", "arn:aws:iam::123456789012:role/config-role")
        calls: list[dict[str, Any]] = []

        adapter = self._build_recording(calls)

        assert isinstance(adapter, ConfigAdapter)
        assert len(calls) == 1
        assert calls[0]["service_name"] == "config"
        assert calls[0]["role_arn"] == "arn:aws:iam::123456789012:role/config-role"

    def test_role_arn_none_when_setting_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty AWS_CONFIG_ROLE_ARN is passed as role_arn=None, not an empty string."""
        monkeypatch.setenv("AWS_CONFIG_ROLE_ARN", "")
        calls: list[dict[str, Any]] = []

        self._build_recording(calls)

        assert calls[0]["role_arn"] is None
