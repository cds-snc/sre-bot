"""The Google Meet VideoCall returns classified results, never exceptions, for expected failures.

The gateway factory is replaced by a ``MagicMock`` whose Meet service raises
the failure under test from ``execute``, and the Google Workspace settings by a
namespace naming the tenant (or none). Statuses follow
``classify_google_error``: 429 is transient with its Retry-After, 403 is
unauthorized, refused credentials are unauthorized with the refusal's cause; an
error the classifier does not know propagates. No tenant refuses before any
request is built, and a payload without a space name or meeting link is a
transient error. Meet has no idempotency key, so the request keeps retries off.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.core.adapters import google_meet
from integrations.google_workspace.client import GoogleCredentialsRefused

pytestmark = pytest.mark.unit

EXPECTED_BODY = {"config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"}}


def _http_error(status: int, retry_after: str | None = None) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            if retry_after is not None:
                self["retry-after"] = retry_after
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def meet(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_meet, "get_meet_service", factory)
    tenant = SimpleNamespace(value=SimpleNamespace(customer_id="C0GOOGLE"))
    monkeypatch.setattr(google_meet, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=tenant.value))
    return SimpleNamespace(
        factory=factory,
        execute=service.spaces.return_value.create.return_value.execute,
        tenant=tenant,
        create=service.spaces.return_value.create,
    )


async def test_rate_limit_is_transient_with_retry_after(meet: SimpleNamespace) -> None:
    """A 429 tells the caller to retry later, carrying Meet's Retry-After."""
    meet.execute.side_effect = _http_error(429, retry_after="7")

    result = await google_meet.GoogleMeetVideoCall().create()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"
    assert result.retry_after == 7


async def test_forbidden_is_unauthorized(meet: SimpleNamespace) -> None:
    """A 403 is the bot lacking the Meet grant: unauthorized, not retried."""
    meet.execute.side_effect = _http_error(403)

    result = await google_meet.GoogleMeetVideoCall().create()

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == "403"


async def test_refused_credentials_are_unauthorized_with_the_cause(meet: SimpleNamespace) -> None:
    """The gateway refusing the token request is unauthorized, carrying the refusal's cause as the code."""
    meet.execute.side_effect = GoogleCredentialsRefused("unauthorized_client")

    result = await google_meet.GoogleMeetVideoCall().create()

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == "unauthorized_client"


async def test_unknown_error_propagates(meet: SimpleNamespace) -> None:
    """An exception no classifier knows is a bug, not a platform failure: it raises."""
    meet.execute.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await google_meet.GoogleMeetVideoCall().create()


async def test_no_tenant_refuses_before_any_request(meet: SimpleNamespace) -> None:
    """Without a Google tenant there is nothing to name the reference with: no service is built."""
    meet.tenant.value = None

    result = await google_meet.GoogleMeetVideoCall().create()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert result.message is not None and "google_workspace.tenant" in result.message
    meet.factory.assert_not_called()


@pytest.mark.parametrize("payload", [{}, {"name": "spaces/abc"}, {"meetingUri": "https://meet.google.com/abc"}])
async def test_incomplete_payload_is_transient(meet: SimpleNamespace, payload: dict[str, str]) -> None:
    """A space without a name or meeting link cannot be referenced: transient, the caller may try again."""
    meet.execute.return_value = payload

    result = await google_meet.GoogleMeetVideoCall().create()

    assert result.status is OperationStatus.TRANSIENT_ERROR


async def test_request_body_is_pinned_and_retries_are_off(meet: SimpleNamespace) -> None:
    """Meet offers no idempotency key, so the SDK must not retry the create on its own."""
    meet.execute.return_value = {"name": "spaces/abc", "meetingUri": "https://meet.google.com/abc"}

    await google_meet.GoogleMeetVideoCall().create()

    meet.create.assert_called_once_with(body=EXPECTED_BODY)
    meet.execute.assert_called_once_with(num_retries=0)
