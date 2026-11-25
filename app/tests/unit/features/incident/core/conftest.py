"""Shared fixtures for the incident core unit tests."""

import copy
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from googleapiclient.errors import HttpError
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from features.incident.core.adapters import google_calendar


def slack_error(code: str) -> SlackApiError:
    """Return a ``SlackApiError`` carrying ``code`` as Slack's error field."""
    return SlackApiError(f"The request to the Slack API failed. (error: {code})", {"ok": False, "error": code})


class StubSlack:
    """Read and write Web clients over a few channels, answering as the Slack Web API does.

    ``channels`` maps a channel id to its ``is_archived`` and ``is_member`` flags (and
    ``is_private``, whose join Slack refuses with ``method_not_supported_for_channel_type``); any
    other id is ``channel_not_found``. Writes to an archived channel answer
    ``is_archived`` and writes where the bot is no member ``not_in_channel``;
    ``fail_with`` makes every call raise that Slack code instead. Posted messages get
    ``ts`` values ``1700000000.00000<n>``.

    ``names`` names some of those channels (name to id); ``foreign_names`` are names of
    channels the bot cannot see. Creating a channel under any of them answers
    ``name_taken``; a new channel is open, the bot a member, with id ``C0NEW<n>``.
    ``users.conversations`` lists the named channels the bot is a member of and that are
    not archived, ``page_size`` per page. ``groups`` maps a user group id to its members;
    any other id is ``no_such_subteam``. ``accounts`` maps an email to its user id for
    ``users.lookupByEmail``; any other email is ``users_not_found``. A second channel canvas is
    ``channel_canvas_already_exists``. A channel's purpose is absent from ``conversations.info``
    until ``purposes`` holds one (a set purpose is stored there).
    """

    def __init__(
        self,
        channels: dict[str, dict[str, bool]] | None = None,
        *,
        fail_with: str | None = None,
        names: dict[str, str] | None = None,
        foreign_names: Sequence[str] = (),
        groups: dict[str, list[str]] | None = None,
        accounts: dict[str, str] | None = None,
        page_size: int = 1,
    ) -> None:
        self.channels = channels if channels is not None else {"C0OPEN": {"is_archived": False, "is_member": True}}
        self.fail_with = fail_with
        self.names = dict(names or {})
        self.foreign_names = set(foreign_names)
        self.groups = dict(groups or {})
        self.accounts = dict(accounts or {})
        self.page_size = page_size
        self.canvases: dict[str, str] = {}
        self.purposes: dict[str, str] = {}
        self._created = 0
        self.reads = AsyncMock(spec=AsyncWebClient)
        self.writes = AsyncMock(spec=AsyncWebClient)
        self.reads.conversations_info.side_effect = self._info
        self.writes.chat_postMessage.side_effect = self._post
        self.writes.conversations_setPurpose.side_effect = self._set_purpose
        self.writes.bookmarks_add.side_effect = self._channel_write("channel_id")
        self.writes.conversations_invite.side_effect = self._invite
        self.writes.conversations_archive.side_effect = self._archive
        self.writes.conversations_join.side_effect = self._join
        self.writes.conversations_create.side_effect = self._create
        self.writes.conversations_setTopic.side_effect = self._channel_write("channel")
        self.writes.conversations_canvases_create.side_effect = self._canvas
        self.reads.users_conversations.side_effect = self._own_conversations
        self.reads.usergroups_users_list.side_effect = self._group_members
        self.reads.users_lookupByEmail.side_effect = self._lookup_by_email
        self._posted = 0

    error = staticmethod(slack_error)

    def _check(self, channel: str) -> dict[str, bool]:
        if self.fail_with:
            raise slack_error(self.fail_with)
        if channel not in self.channels:
            raise slack_error("channel_not_found")
        return self.channels[channel]

    def _writable(self, channel: str) -> None:
        state = self._check(channel)
        if state["is_archived"]:
            raise slack_error("is_archived")
        if not state["is_member"]:
            raise slack_error("not_in_channel")

    async def _info(self, *, channel: str, **_: Any) -> dict[str, Any]:
        state = self._check(channel)
        info: dict[str, Any] = {"id": channel, **state}
        if channel in self.purposes:
            info["purpose"] = {"value": self.purposes[channel]}
        return {"ok": True, "channel": info}

    async def _set_purpose(self, *, channel: str, purpose: str, **_: Any) -> dict[str, Any]:
        self._writable(channel)
        self.purposes[channel] = purpose
        return {"ok": True}

    async def _post(self, *, channel: str, text: str, **_: Any) -> dict[str, Any]:
        self._writable(channel)
        self._posted += 1
        return {"ok": True, "channel": channel, "ts": f"1700000000.{self._posted:06d}"}

    def _channel_write(self, key: str) -> Callable[..., Any]:
        async def _write(**kwargs: Any) -> dict[str, Any]:
            self._writable(kwargs[key])
            return {"ok": True}

        return _write

    async def _invite(self, *, channel: str, users: Sequence[str] | str, **_: Any) -> dict[str, Any]:
        self._writable(channel)
        return {"ok": True}

    async def _archive(self, *, channel: str, **_: Any) -> dict[str, Any]:
        state = self._check(channel)
        if state["is_archived"]:
            raise slack_error("already_archived")
        if not state["is_member"]:
            raise slack_error("not_in_channel")
        state["is_archived"] = True
        return {"ok": True}

    async def _join(self, *, channel: str, **_: Any) -> dict[str, Any]:
        state = self._check(channel)
        if state["is_archived"]:
            raise slack_error("is_archived")
        if state.get("is_private"):
            raise slack_error("method_not_supported_for_channel_type")
        already = state["is_member"]
        state["is_member"] = True
        return {"ok": True, **({"warning": "already_in_channel"} if already else {})}

    async def _create(self, *, name: str, is_private: bool = False, **_: Any) -> dict[str, Any]:
        if self.fail_with:
            raise slack_error(self.fail_with)
        if name in self.names or name in self.foreign_names:
            raise slack_error("name_taken")
        self._created += 1
        channel_id = f"C0NEW{self._created}"
        self.channels[channel_id] = {"is_archived": False, "is_member": True}
        self.names[name] = channel_id
        return {"ok": True, "channel": {"id": channel_id, "name": name, "is_private": is_private}}

    async def _own_conversations(self, *, cursor: str | None = None, **_: Any) -> dict[str, Any]:
        if self.fail_with:
            raise slack_error(self.fail_with)
        own = [
            {"id": channel_id, "name": name}
            for name, channel_id in self.names.items()
            if self.channels[channel_id]["is_member"] and not self.channels[channel_id]["is_archived"]
        ]
        start = int(cursor) if cursor else 0
        end = start + self.page_size
        next_cursor = str(end) if end < len(own) else ""
        return {"ok": True, "channels": own[start:end], "response_metadata": {"next_cursor": next_cursor}}

    async def _canvas(self, *, channel_id: str, document_content: dict[str, str], **_: Any) -> dict[str, Any]:
        self._writable(channel_id)
        if channel_id in self.canvases:
            raise slack_error("channel_canvas_already_exists")
        self.canvases[channel_id] = document_content["markdown"]
        return {"ok": True, "canvas_id": f"F0CANVAS{channel_id}"}

    async def _group_members(self, *, usergroup: str, **_: Any) -> dict[str, Any]:
        if self.fail_with:
            raise slack_error(self.fail_with)
        if usergroup not in self.groups:
            raise slack_error("no_such_subteam")
        return {"ok": True, "users": list(self.groups[usergroup])}

    async def _lookup_by_email(self, *, email: str, **_: Any) -> dict[str, Any]:
        if self.fail_with:
            raise slack_error(self.fail_with)
        if email not in self.accounts:
            raise slack_error("users_not_found")
        return {"ok": True, "user": {"id": self.accounts[email]}}


@pytest.fixture
def stub_slack() -> Callable[..., StubSlack]:
    """Return the ``StubSlack`` constructor."""
    return StubSlack


def google_http_error(status: int, retry_after: str | None = None) -> HttpError:
    """Return a googleapiclient ``HttpError`` with ``status`` (and a Retry-After header when given)."""

    class FakeResp(dict[str, str]):
        def __init__(self) -> None:
            super().__init__()
            if retry_after is not None:
                self["retry-after"] = retry_after
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")  # type: ignore[arg-type]


class _CalendarRequest:
    def __init__(self, stub: StubCalendar, method: str, params: dict[str, Any], run: Callable[[], Any]) -> None:
        self._stub, self._method, self._params, self._run = stub, method, params, run

    def execute(self, num_retries: int | None = None) -> Any:
        self._stub.calls.append(CalendarCall(self._method, self._params, num_retries, threading.get_ident()))
        failure = self._stub.fail.get(self._method)
        if failure is not None:
            raise failure
        result = self._run()
        transform = self._stub.transform.get(self._method)
        return transform(result) if transform is not None else result


@dataclass(frozen=True)
class CalendarCall:
    """One executed Calendar request: the method, its parameters, the retries asked for (None = factory default), the thread."""

    method: str
    params: dict[str, Any]
    num_retries: int | None
    thread: int


class StubCalendar:
    """A Calendar API v3 service stand-in over one in-memory calendar, answering as Google documents.

    ``events().insert`` stores the body under its client-supplied ``id`` (a second insert of the
    same id, deleted or not, is a 409), adds ``htmlLink``, ``hangoutLink`` and a confirmed status;
    ``get`` of an unknown id is a 404 and of a deleted event a minimal cancelled resource;
    ``patch`` merges the body (arrays replace); ``delete`` cancels the event, and a second delete
    is a 410. ``freebusy().query`` answers each requested calendar from ``busy`` (intervals as
    ``(start, end)`` aware datetimes, clipped to the window), ``calendar_errors`` (a reason per
    address) or omits addresses in ``omitted``. ``fail`` maps a method name (``insert``, ``get``,
    ``patch``, ``delete``, ``query``) to the exception its ``execute`` raises, and ``transform``
    to a function applied to its answer (a hand-edited or incomplete event). Every executed
    request is recorded in ``calls``.
    """

    def __init__(self) -> None:
        self.stored: dict[str, dict[str, Any]] = {}
        self.calls: list[CalendarCall] = []
        self.fail: dict[str, Exception] = {}
        self.busy: dict[str, list[tuple[datetime, datetime]]] = {}
        self.calendar_errors: dict[str, str] = {}
        self.omitted: set[str] = set()
        self.transform: dict[str, Callable[[Any], Any]] = {}

    def calls_to(self, method: str) -> list[CalendarCall]:
        return [call for call in self.calls if call.method == method]

    def events(self) -> SimpleNamespace:
        return SimpleNamespace(insert=self._insert, get=self._get, patch=self._patch, delete=self._delete)

    def freebusy(self) -> SimpleNamespace:
        return SimpleNamespace(query=self._query)

    def _insert(self, **params: Any) -> _CalendarRequest:
        def run() -> dict[str, Any]:
            body = copy.deepcopy(params["body"])
            event_id = body["id"]
            if event_id in self.stored:
                raise google_http_error(409)
            body.update(
                status="confirmed",
                htmlLink=f"https://calendar.google.com/calendar/event?eid={event_id}",
                hangoutLink=f"https://meet.google.com/{event_id[:3]}-{event_id[3:7]}-{event_id[7:10]}",
            )
            self.stored[event_id] = body
            return copy.deepcopy(body)

        return _CalendarRequest(self, "insert", params, run)

    def _get(self, **params: Any) -> _CalendarRequest:
        def run() -> dict[str, Any]:
            event = self.stored.get(params["eventId"])
            if event is None:
                raise google_http_error(404)
            if event["status"] == "cancelled":
                return {"id": event["id"], "status": "cancelled"}
            return copy.deepcopy(event)

        return _CalendarRequest(self, "get", params, run)

    def _patch(self, **params: Any) -> _CalendarRequest:
        def run() -> dict[str, Any]:
            event = self.stored.get(params["eventId"])
            if event is None:
                raise google_http_error(404)
            if event["status"] == "cancelled":
                raise google_http_error(410)
            event.update(copy.deepcopy(params["body"]))
            return copy.deepcopy(event)

        return _CalendarRequest(self, "patch", params, run)

    def _delete(self, **params: Any) -> _CalendarRequest:
        def run() -> str:
            event = self.stored.get(params["eventId"])
            if event is None:
                raise google_http_error(404)
            if event["status"] == "cancelled":
                raise google_http_error(410)
            event["status"] = "cancelled"
            return ""

        return _CalendarRequest(self, "delete", params, run)

    def _query(self, **params: Any) -> _CalendarRequest:
        def run() -> dict[str, Any]:
            body = params["body"]
            window_start = datetime.fromisoformat(body["timeMin"])
            window_end = datetime.fromisoformat(body["timeMax"])
            calendars: dict[str, Any] = {}
            for item in body["items"]:
                email = item["id"]
                if email in self.omitted:
                    continue
                if email in self.calendar_errors:
                    calendars[email] = {"errors": [{"domain": "global", "reason": self.calendar_errors[email]}], "busy": []}
                    continue
                busy = [
                    {
                        "start": max(start, window_start).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "end": min(end, window_end).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                    for start, end in self.busy.get(email, [])
                    if start < window_end and end > window_start
                ]
                calendars[email] = {"busy": busy}
            return {"kind": "calendar#freeBusy", "calendars": calendars}

        return _CalendarRequest(self, "query", params, run)


@pytest.fixture
def stub_calendar(monkeypatch: pytest.MonkeyPatch) -> StubCalendar:
    """Replace the Calendar gateway factory of the core Calendar adapter with a ``StubCalendar``."""
    stub = StubCalendar()
    monkeypatch.setattr(google_calendar, "get_calendar_service", lambda **_: stub)
    return stub
