from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant
from modules.incident import on_call


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    email = "user@example.com"
    user_info = {
        "ok": True,
        "user": {
            "id": "U12345",
            "name": "testuser",
            "real_name": "Test User",
            "profile": {
                "email": email,
                "real_name": "Test User",
                "display_name": "testuser",
            },
        },
    }
    mock_get_folder_metadata.return_value = {"appProperties": {"genie_schedule": "schedule_id"}}
    mock_opsgenie_get_on_call_users.return_value = [email]
    client.users_lookupByEmail.return_value = user_info

    result = on_call.get_on_call_users_from_folder(client, folder)

    # Assert that the result is a list with the expected user object
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "U12345"
    assert result[0]["profile"]["email"] == email


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_tuple_metadata(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    email = "user2@example.com"
    user_info = {
        "ok": True,
        "user": {
            "id": "U67890",
            "name": "testuser2",
            "real_name": "Test User2",
            "profile": {
                "email": email,
                "real_name": "Test User2",
                "display_name": "testuser2",
            },
        },
    }
    # Simulate get_folder_metadata returning a tuple
    mock_get_folder_metadata.return_value = (
        {"appProperties": {"genie_schedule": "schedule_id2"}},
        "extra_value",
    )
    mock_opsgenie_get_on_call_users.return_value = [email]
    client.users_lookupByEmail.return_value = user_info

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "U67890"
    assert result[0]["profile"]["email"] == email
    mock_opsgenie_get_on_call_users.assert_called_once_with("schedule_id2")
    client.users_lookupByEmail.assert_called_once_with(email=email)


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_no_genie_schedule(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    # No 'genie_schedule' in appProperties
    mock_get_folder_metadata.return_value = {"appProperties": {}}
    # Should not matter, but set anyway
    mock_opsgenie_get_on_call_users.return_value = []
    client.users_lookupByEmail.return_value = {}

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert isinstance(result, list)
    assert not result
    mock_opsgenie_get_on_call_users.assert_not_called()
    client.users_lookupByEmail.assert_not_called()


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_any_type(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    mock_get_folder_metadata.return_value = "unexpected_string_value"
    mock_opsgenie_get_on_call_users.return_value = []
    client.users_lookupByEmail.return_value = {}

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert isinstance(result, list)
    assert not result
    mock_opsgenie_get_on_call_users.assert_not_called()
    client.users_lookupByEmail.assert_not_called()


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_handles_slack_lookup_exception(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    email = "missing-user@example.com"

    mock_get_folder_metadata.return_value = {"appProperties": {"genie_schedule": "schedule_id"}}
    mock_opsgenie_get_on_call_users.return_value = [email]
    client.users_lookupByEmail.side_effect = Exception(
        "The request to the Slack API failed. (url: https://slack.com/api/users.lookupByEmail) "
        "The server responded with: {'ok': False, 'error': 'users_not_found'}"
    )

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert result == []
    mock_opsgenie_get_on_call_users.assert_called_once_with("schedule_id")
    client.users_lookupByEmail.assert_called_once_with(email=email)


# The module-local Opsgenie lookup. The HTTP edge is an httpx.MockTransport behind the real
# factory signature (build_opsgenie_client is swapped for one that injects the transport); the
# settings are a real OpsGenieSettings built with model_construct. Assertions are on the names
# returned and on the request reaching the on-calls path.

ON_CALLS_PATH = "/v2/schedules/schedule_id/on-calls"


def _opsgenie_settings(configured: bool = True) -> OpsGenieSettings:
    tenant = OpsGenieTenant(api_url="https://api.opsgenie.com") if configured else None
    return OpsGenieSettings.model_construct(
        tenant=tenant,
        integrations_key=SecretStr("genie-key" if configured else ""),
        timeout_seconds=5.0,
        connect_retries=0,
    )


def _wire_opsgenie(monkeypatch, handler, configured: bool = True) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    def build(settings):
        return httpx.AsyncClient(base_url=settings.tenant.api_url, transport=httpx.MockTransport(recording))

    monkeypatch.setattr(on_call, "get_opsgenie_settings", lambda: _opsgenie_settings(configured))
    monkeypatch.setattr(on_call, "build_opsgenie_client", build)
    return requests


def test_get_on_call_users_returns_the_participant_names(monkeypatch):
    requests = _wire_opsgenie(
        monkeypatch,
        lambda request: httpx.Response(200, json={"data": {"onCallParticipants": [{"name": "a@x.ca"}, {"name": "b@x.ca"}]}}),
    )

    assert on_call.get_on_call_users("schedule_id") == ["a@x.ca", "b@x.ca"]
    assert [r.url.path for r in requests] == [ON_CALLS_PATH]


def test_get_on_call_users_is_empty_when_opsgenie_is_not_configured(monkeypatch):
    """A missing source invites nobody and never fails the declare (decisions/oncall.md)."""
    requests = _wire_opsgenie(monkeypatch, lambda request: httpx.Response(200, json={}), configured=False)

    assert on_call.get_on_call_users("schedule_id") == []
    assert requests == []


def test_get_on_call_users_is_empty_on_a_classified_failure(monkeypatch):
    _wire_opsgenie(monkeypatch, lambda request: httpx.Response(503))

    assert on_call.get_on_call_users("schedule_id") == []


def test_get_on_call_users_is_empty_on_an_unparseable_body(monkeypatch):
    _wire_opsgenie(monkeypatch, lambda request: httpx.Response(200, text="<html>"))

    assert on_call.get_on_call_users("schedule_id") == []


def test_get_on_call_users_is_empty_on_an_unexpected_shape(monkeypatch):
    _wire_opsgenie(monkeypatch, lambda request: httpx.Response(200, json={"data": {"onCallParticipants": "nobody"}}))

    assert on_call.get_on_call_users("schedule_id") == []


def test_get_on_call_users_lets_an_unexpected_exception_propagate(monkeypatch):
    def broken(request):
        raise RuntimeError("bug in the transport handler")

    _wire_opsgenie(monkeypatch, broken)

    with pytest.raises(RuntimeError):
        on_call.get_on_call_users("schedule_id")
