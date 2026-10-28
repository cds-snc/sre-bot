"""Tests for the Opsgenie client: on-call lookups, the healthcheck and the request helper.

The client reads the Opsgenie slice at use through ``get_opsgenie_settings``, which each test
patches with a real ``OpsGenieSettings`` (``model_construct``, so no configuration files are
needed). Lookups are stubbed at ``api_get_request``; the helper's own tests stub ``Request``
and ``urlopen``, so no test reaches the network.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from integrations import opsgenie
from integrations.opsgenie import OpsGenieAPIError
from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant

API_URL = "https://api.eu.opsgenie.com"


def _settings(tenant: OpsGenieTenant | None = OpsGenieTenant(api_url=API_URL)) -> OpsGenieSettings:
    key = SecretStr("genie-key" if tenant else "")
    return OpsGenieSettings.model_construct(tenant=tenant, integrations_key=key, timeout_seconds=12.0)


@pytest.fixture(autouse=True)
def _configured_opsgenie():
    with patch("integrations.opsgenie.client.get_opsgenie_settings", return_value=_settings()):
        yield


@pytest.fixture
def _unconfigured_opsgenie():
    with patch("integrations.opsgenie.client.get_opsgenie_settings", return_value=_settings(tenant=None)):
        yield


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_users(api_get_request_mock):
    api_get_request_mock.return_value = '{"data": {"onCallParticipants": [{"name": "test_user"}]}}'
    assert opsgenie.get_on_call_users("test_schedule") == ["test_user"]
    api_get_request_mock.assert_called_once_with("/v2/schedules/test_schedule/on-calls")


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_users_with_exception(api_get_request_mock):
    api_get_request_mock.return_value = "{]"
    assert opsgenie.get_on_call_users("test_schedule") == []


def test_create_alert_is_gone():
    """Nothing raises Opsgenie alerts any more: the function, its POST helper and their exports are deleted."""
    assert not hasattr(opsgenie, "create_alert")
    assert not hasattr(opsgenie, "api_post_request")
    assert not hasattr(opsgenie.client, "create_alert")
    assert not hasattr(opsgenie.client, "api_post_request")


@patch("integrations.opsgenie.client.Request")
@patch("integrations.opsgenie.client.urlopen")
def test_api_get_request_reaches_the_tenant_host_with_the_key_and_timeout(urlopen_mock, request_mock):
    urlopen_mock.return_value.read.return_value.decode.return_value = '{"data": []}'

    assert opsgenie.api_get_request("/v1/services") == '{"data": []}'

    request_mock.assert_called_once_with(f"{API_URL}/v1/services")
    request_mock.return_value.add_header.assert_called_once_with("Authorization", "GenieKey genie-key")
    urlopen_mock.assert_called_once_with(request_mock.return_value, timeout=12.0)


@pytest.mark.usefixtures("_unconfigured_opsgenie")
@patch("integrations.opsgenie.client.urlopen")
def test_api_get_request_without_a_tenant_raises_without_a_request(urlopen_mock):
    with pytest.raises(OpsGenieAPIError, match="not configured"):
        opsgenie.api_get_request("/v1/services")

    urlopen_mock.assert_not_called()


@pytest.mark.usefixtures("_unconfigured_opsgenie")
@patch("integrations.opsgenie.client.urlopen")
def test_get_on_call_user_for_rotation_without_a_tenant_raises(urlopen_mock):
    with pytest.raises(OpsGenieAPIError):
        opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation")

    urlopen_mock.assert_not_called()


@pytest.mark.usefixtures("_unconfigured_opsgenie")
@patch("integrations.opsgenie.client.urlopen")
def test_healthcheck_without_a_tenant_is_unhealthy_without_a_request(urlopen_mock):
    with capture_logs() as entries:
        assert opsgenie.healthcheck() is False

    assert [entry["event"] for entry in entries] == ["opsgenie_not_configured"]
    urlopen_mock.assert_not_called()


@patch("integrations.opsgenie.client.api_get_request")
def test_healthcheck_healthy(api_get_request_mock):
    api_get_request_mock.return_value = '{"data": {"name": "test_user"}}'
    assert opsgenie.healthcheck() is True
    api_get_request_mock.assert_called_once_with("/v1/services")


@patch("integrations.opsgenie.client.api_get_request")
def test_healthcheck_unhealthy(api_get_request_mock):
    api_get_request_mock.return_value = '{"error": "failed"}'
    assert opsgenie.healthcheck() is False


@patch("integrations.opsgenie.client.api_get_request")
def test_healthcheck_unhealthy_error(api_get_request_mock):
    api_get_request_mock.return_value = "{]"
    assert opsgenie.healthcheck() is False


def _timeline_response(rotations):
    return json.dumps({"data": {"finalTimeline": {"rotations": rotations}}})


def _iso(dt: datetime) -> str:
    """Render an aware UTC datetime in OpsGenie's response format."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _window_around_now(
    *,
    before: timedelta = timedelta(minutes=30),
    after: timedelta = timedelta(minutes=30),
) -> tuple[str, str]:
    now = datetime.now(UTC)
    return _iso(now - before), _iso(now + after)


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_user_for_rotation_returns_email(api_get_request_mock):
    start, end = _window_around_now()
    api_get_request_mock.return_value = _timeline_response(
        [
            {
                "name": "PSO_rotation",
                "periods": [
                    {
                        "startDate": start,
                        "endDate": end,
                        "type": "user",
                        "recipient": {"type": "user", "name": "a@x.ca"},
                    }
                ],
            }
        ]
    )

    result = opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation")

    assert result == "a@x.ca"
    called_url = api_get_request_mock.call_args[0][0]
    assert "/v2/schedules/sched-1/timeline" in called_url
    assert "intervalUnit=days" in called_url


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_user_for_rotation_returns_none_when_rotation_absent(
    api_get_request_mock,
):
    start, end = _window_around_now()
    api_get_request_mock.return_value = _timeline_response(
        [
            {
                "name": "OtherRotation",
                "periods": [
                    {
                        "startDate": start,
                        "endDate": end,
                        "type": "user",
                        "recipient": {"type": "user", "name": "b@x.ca"},
                    }
                ],
            }
        ]
    )

    assert opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation") is None


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_user_for_rotation_returns_none_when_no_user_period(
    api_get_request_mock,
):
    api_get_request_mock.return_value = _timeline_response([{"name": "PSO_rotation", "periods": []}])

    assert opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation") is None


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_user_for_rotation_skips_non_user_recipients(
    api_get_request_mock,
):
    start, end = _window_around_now()
    api_get_request_mock.return_value = _timeline_response(
        [
            {
                "name": "PSO_rotation",
                "periods": [
                    {
                        "startDate": start,
                        "endDate": end,
                        "type": "team",
                        "recipient": {"type": "team", "name": "platform"},
                    }
                ],
            }
        ]
    )

    assert opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation") is None


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_user_for_rotation_returns_none_when_first_period_in_future(
    api_get_request_mock,
):
    """A first period starting after 'now' signals a coverage gap."""
    future_start = _iso(datetime.now(UTC) + timedelta(hours=6))
    future_end = _iso(datetime.now(UTC) + timedelta(hours=12))
    api_get_request_mock.return_value = _timeline_response(
        [
            {
                "name": "PSO_rotation",
                "periods": [
                    {
                        "startDate": future_start,
                        "endDate": future_end,
                        "type": "user",
                        "recipient": {"type": "user", "name": "later@x.ca"},
                    }
                ],
            }
        ]
    )

    assert opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation") is None


@patch("integrations.opsgenie.client.api_get_request")
def test_get_on_call_user_for_rotation_raises_on_api_failure(api_get_request_mock):
    api_get_request_mock.return_value = "{not json"

    with pytest.raises(OpsGenieAPIError):
        opsgenie.get_on_call_user_for_rotation("sched-1", "PSO_rotation")
