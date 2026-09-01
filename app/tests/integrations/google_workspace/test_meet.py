"""Unit tests for the Google Meet API integration (integrations.google_workspace.meet)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from integrations.google_workspace import meet

MEET_SCOPES = ["https://www.googleapis.com/auth/meetings.space.created"]
EXPECTED_BODY = {"config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"}}


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def meet_client(monkeypatch):
    """Patch the Meet service factory and expose the mocked stub-typed Resource chain."""
    if not hasattr(google_client, "get_meet_service"):
        pytest.fail("integrations.google_workspace.client.get_meet_service is not implemented")

    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_meet_service", factory)
    if hasattr(meet, "get_meet_service"):
        monkeypatch.setattr(meet, "get_meet_service", factory)
    return SimpleNamespace(factory=factory, service=service)


def test_create_space_returns_api_response(meet_client):
    create = meet_client.service.spaces.return_value.create
    create.return_value.execute.return_value = {
        "name": "spaces/abc123",
        "meetingUri": "https://meet.google.com/abc-defg-hij",
    }

    result = meet.create_space()

    assert result == {
        "name": "spaces/abc123",
        "meetingUri": "https://meet.google.com/abc-defg-hij",
    }
    create.assert_called_once_with(body=EXPECTED_BODY)
    create.return_value.execute.assert_called_once_with()


def test_create_space_defaults_delegated_user_email_to_none(meet_client):
    meet_client.service.spaces.return_value.create.return_value.execute.return_value = {}

    meet.create_space()

    meet_client.factory.assert_called_once_with(scopes=MEET_SCOPES, delegated_user_email=None)


def test_create_space_passes_delegated_user_email(meet_client):
    meet_client.service.spaces.return_value.create.return_value.execute.return_value = {}

    meet.create_space(delegated_user_email="custom@example.com")

    meet_client.factory.assert_called_once_with(scopes=MEET_SCOPES, delegated_user_email="custom@example.com")


def test_create_space_propagates_http_error(meet_client):
    error = _http_error(429)
    meet_client.service.spaces.return_value.create.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        meet.create_space()

    assert exc_info.value is error


def test_create_space_propagates_unclassified_error(meet_client):
    error = RuntimeError("boom")
    meet_client.service.spaces.return_value.create.return_value.execute.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        meet.create_space()

    assert exc_info.value is error
