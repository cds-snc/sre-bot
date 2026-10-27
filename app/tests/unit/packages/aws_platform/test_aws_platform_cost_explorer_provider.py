"""Behavior tests for build_cost_explorer_adapter client construction.

get_aws_client is patched in the adapter module to record its arguments and
return a real boto3 cost-explorer client with dummy static credentials. The Cost
Explorer role comes from the AWS tenant's org_role_arn and the settings cache is
cleared around each test, so the assertions pin the service name 'ce' and the
role ARN the factory reads from service_role_map.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.cost_explorer import CostExplorerAdapter, build_cost_explorer_adapter
from tests.factories.aws import set_aws_tenant

pytestmark = pytest.mark.unit


def _cost_explorer_client() -> Any:
    """Build a real boto3 cost-explorer client with dummy static credentials."""
    return boto3.client(
        "ce",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildCostExplorerAdapter:
    """build_cost_explorer_adapter builds one cost-explorer client through get_aws_client."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self) -> Iterator[None]:
        """Clear settings cache before and after each test."""
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def _build_recording(self, calls: list[dict[str, Any]]) -> CostExplorerAdapter:
        def record_get_aws_client(service_name: str, *, role_arn: str | None = None, **kwargs: Any) -> Any:
            calls.append({"service_name": service_name, "role_arn": role_arn, **kwargs})
            return _cost_explorer_client()

        with patch(
            "packages.aws_platform.adapters.cost_explorer.get_aws_client",
            side_effect=record_get_aws_client,
            create=True,
        ):
            return build_cost_explorer_adapter()

    def test_single_cost_explorer_client_with_org_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One get_aws_client('ce') call carries service_role_map['ce']."""
        set_aws_tenant(monkeypatch, org_role_arn="arn:aws:iam::123456789012:role/org-role")
        calls: list[dict[str, Any]] = []

        adapter = self._build_recording(calls)

        assert isinstance(adapter, CostExplorerAdapter)
        assert len(calls) == 1
        assert calls[0]["service_name"] == "ce"
        assert calls[0]["role_arn"] == "arn:aws:iam::123456789012:role/org-role"

    def test_role_arn_none_when_setting_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty org_role_arn is passed as role_arn=None, not an empty string."""
        set_aws_tenant(monkeypatch, org_role_arn="")
        calls: list[dict[str, Any]] = []

        self._build_recording(calls)

        assert calls[0]["role_arn"] is None
