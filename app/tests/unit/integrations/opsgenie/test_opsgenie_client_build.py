"""Tests for ``build_opsgenie_client``, the Opsgenie vendor client factory.

The factory is given a real ``OpsGenieSettings`` (``model_construct``, so no configuration
files are needed). The transport is observed through a recording stand-in for
``httpx.AsyncHTTPTransport`` (the SDK edge), so the assertions read the resilience settings the
client is built with rather than httpx internals. Nothing reaches the network.
"""

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from integrations.opsgenie.client import build_opsgenie_client
from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant

pytestmark = pytest.mark.unit

API_URL = "https://api.eu.opsgenie.com"


def _settings(
    *,
    tenant: OpsGenieTenant | None = OpsGenieTenant(api_url=API_URL),
    timeout_seconds: float = 30.0,
    connect_retries: int = 2,
) -> OpsGenieSettings:
    key = SecretStr("genie-key" if tenant else "")
    return OpsGenieSettings.model_construct(
        tenant=tenant, integrations_key=key, timeout_seconds=timeout_seconds, connect_retries=connect_retries
    )


def test_the_client_targets_the_tenant_host_with_the_genie_key() -> None:
    client = build_opsgenie_client(_settings())

    assert isinstance(client, httpx.AsyncClient)
    assert client.headers["Authorization"] == "GenieKey genie-key"
    assert str(client.base_url).rstrip("/") == API_URL


def test_the_timeout_and_connect_retries_are_set_once_at_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry policy is set at construction beside the per-attempt timeout (outbound-clients.md)."""
    built: list[dict[str, Any]] = []
    real_transport = httpx.AsyncHTTPTransport

    def recording_transport(**kwargs: Any) -> httpx.AsyncHTTPTransport:
        built.append(kwargs)
        return real_transport(**kwargs)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", recording_transport)

    client = build_opsgenie_client(_settings(timeout_seconds=12.0, connect_retries=3))

    assert built == [{"retries": 3}]
    assert client.timeout == httpx.Timeout(12.0)


def test_a_missing_tenant_is_a_programming_error() -> None:
    """Consumers check the tenant first; reaching the factory without one is a bug, not an outcome."""
    with pytest.raises(ValueError, match="not configured"):
        build_opsgenie_client(_settings(tenant=None))
