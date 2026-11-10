"""The legacy ``create_space`` keeps its contract after moving into core.

The legacy declare and recreate call ``create_space()`` and read ``meetingUri``
from the payload it returns. The gateway factory is replaced by a ``MagicMock``
returning a stubbed Meet service, so the tests pin the request (scopes only,
the space config body, retries off) and that failures still propagate as the
legacy callers expect: an ``HttpError`` is logged and re-raised, anything else
raises unchanged.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from features.incident.core.adapters import google_meet

pytestmark = pytest.mark.unit

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
def meet_client(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_meet, "get_meet_service", factory)
    return SimpleNamespace(factory=factory, service=service)


def test_create_space_returns_api_response_and_sends_expected_body(meet_client: SimpleNamespace) -> None:
    """The payload comes back as Meet sent it; the request carries the trusted-access config and no retries."""
    create = meet_client.service.spaces.return_value.create
    create.return_value.execute.return_value = {"name": "spaces/abc123", "meetingUri": "https://meet.google.com/abc-defg-hij"}

    result = google_meet.create_space()

    assert result == {"name": "spaces/abc123", "meetingUri": "https://meet.google.com/abc-defg-hij"}
    create.assert_called_once_with(body=EXPECTED_BODY)
    create.return_value.execute.assert_called_once_with(num_retries=0)


def test_create_space_builds_the_service_with_scopes_only(meet_client: SimpleNamespace) -> None:
    """No delegation subject reaches the gateway factory: who the call runs as is the gateway's decision."""
    meet_client.service.spaces.return_value.create.return_value.execute.return_value = {}

    google_meet.create_space()

    meet_client.factory.assert_called_once_with(scopes=MEET_SCOPES)


def test_create_space_propagates_http_error(meet_client: SimpleNamespace) -> None:
    """A Meet HTTP failure is re-raised as the same exception, so the legacy callers' handling is unchanged."""
    error = _http_error(429)
    meet_client.service.spaces.return_value.create.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_meet.create_space()

    assert exc_info.value is error


def test_create_space_propagates_unclassified_error(meet_client: SimpleNamespace) -> None:
    """An error that is not an HttpError raises unchanged."""
    error = RuntimeError("boom")
    meet_client.service.spaces.return_value.create.return_value.execute.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        google_meet.create_space()

    assert exc_info.value is error
