"""Tests for ``build_canada_holidays_client``, the Canada Holidays vendor client factory.

The factory is given a real ``CanadaHolidaysSettings`` (``model_construct``, so no configuration
files are needed). The transport is observed through a recording stand-in for
``httpx.AsyncHTTPTransport`` (the SDK edge). Nothing reaches the network.
"""

from typing import Any

import httpx
import pytest

from integrations.canada_holidays.client import build_canada_holidays_client
from integrations.canada_holidays.settings import CanadaHolidaysSettings, CanadaHolidaysTenant

pytestmark = pytest.mark.unit

BASE_URL = "https://canada-holidays.ca/api/v1"


def _settings(
    *,
    tenant: CanadaHolidaysTenant | None = CanadaHolidaysTenant(base_url=BASE_URL),
    timeout_seconds: float = 10.0,
    connect_retries: int = 2,
) -> CanadaHolidaysSettings:
    return CanadaHolidaysSettings.model_construct(tenant=tenant, timeout_seconds=timeout_seconds, connect_retries=connect_retries)


def test_the_client_targets_the_tenant_host_without_credentials() -> None:
    client = build_canada_holidays_client(_settings())

    assert isinstance(client, httpx.AsyncClient)
    assert str(client.base_url) == f"{BASE_URL}/"
    assert "Authorization" not in client.headers


def test_the_timeout_and_connect_retries_are_set_once_at_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict[str, Any]] = []
    real_transport = httpx.AsyncHTTPTransport

    def recording_transport(**kwargs: Any) -> httpx.AsyncHTTPTransport:
        built.append(kwargs)
        return real_transport(**kwargs)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", recording_transport)

    client = build_canada_holidays_client(_settings(timeout_seconds=4.0, connect_retries=3))

    assert built == [{"retries": 3}]
    assert client.timeout == httpx.Timeout(4.0)


def test_a_missing_tenant_is_a_programming_error() -> None:
    """Consumers check the tenant first; reaching the factory without one is a bug, not an outcome."""
    with pytest.raises(ValueError, match="not configured"):
        build_canada_holidays_client(_settings(tenant=None))
