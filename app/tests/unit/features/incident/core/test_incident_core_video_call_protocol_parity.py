"""One behaviour suite for every VideoCall: the Google Meet adapter and the in-memory fake.

The adapter runs over a stubbed Meet service (the gateway factory replaced) and
a configured Google tenant; the fake is built with the same tenant. Each test
runs against both, so a consumer tested on the fake sees the adapter's
observable rules: ``create`` returns a Google reference under the tenant with a
``spaces/`` id and a meeting link, ``link`` returns the stored link, and a
reference of another system has no link. The adapter's blocking request is
pinned to run off the event loop's thread.
"""

import threading
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters import google_meet
from features.incident.core.adapters.in_memory import InMemoryVideoCall
from features.incident.core.api import VideoCall, VideoCallReference

pytestmark = pytest.mark.unit

TENANT = "C0GOOGLE"


@pytest.fixture
def request_threads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Stub the Meet service; record the thread each space-creation request runs on."""
    threads: list[int] = []
    counter = iter(range(1, 100))

    def execute(**_: object) -> dict[str, str]:
        threads.append(threading.get_ident())
        n = next(counter)
        return {"name": f"spaces/call-{n}", "meetingUri": f"https://meet.google.com/call-{n}"}

    service = MagicMock()
    service.spaces.return_value.create.return_value.execute.side_effect = execute
    monkeypatch.setattr(google_meet, "get_meet_service", MagicMock(return_value=service))
    monkeypatch.setattr(
        google_meet, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(customer_id=TENANT))
    )
    return threads


def _adapter() -> VideoCall:
    return google_meet.GoogleMeetVideoCall()


def _fake() -> VideoCall:
    return InMemoryVideoCall(tenant=TENANT)


@pytest.fixture(params=[_adapter, _fake], ids=["google_meet", "in_memory"])
def video_call(request: pytest.FixtureRequest, request_threads: list[int]) -> VideoCall:
    build: Callable[[], VideoCall] = request.param
    return build()


def test_both_implementations_satisfy_the_protocol(video_call: VideoCall) -> None:
    """Consumers type against ``VideoCall``; both the adapter and the fake are runtime instances of it."""
    assert isinstance(video_call, VideoCall)


async def test_create_returns_a_google_reference_under_the_tenant(video_call: VideoCall) -> None:
    """A new call is referenced by its Meet space name under the Google tenant, with its meeting link."""
    result = await video_call.create()

    assert result.status is OperationStatus.SUCCESS
    call = result.data
    assert isinstance(call, VideoCallReference)
    assert call.system is WorkplaceSystem.GOOGLE
    assert call.tenant == TENANT
    assert call.vendor_id.startswith("spaces/")
    assert call.url is not None and call.url.startswith("https://meet.google.com/")


async def test_each_create_makes_a_distinct_call(video_call: VideoCall) -> None:
    """Two creates are two calls: no create returns an earlier call."""
    first = await video_call.create()
    second = await video_call.create()

    assert first.data is not None and second.data is not None
    assert first.data.vendor_id != second.data.vendor_id


async def test_link_returns_the_stored_link(video_call: VideoCall) -> None:
    """The link is the url the reference stores; nothing is fetched."""
    call = (await video_call.create()).data
    assert call is not None

    assert video_call.link(call) == call.url


def test_link_of_another_systems_reference_is_none(video_call: VideoCall) -> None:
    """A reference the implementation does not serve has no link."""
    foreign = VideoCallReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="H0HUDDLE", url="https://x")

    assert video_call.link(foreign) is None


async def test_adapter_runs_the_blocking_request_off_the_event_loop(request_threads: list[int]) -> None:
    """The Meet SDK blocks, so the adapter offloads it: the request runs on a thread other than the loop's."""
    await google_meet.GoogleMeetVideoCall().create()

    assert request_threads and request_threads[0] != threading.get_ident()
