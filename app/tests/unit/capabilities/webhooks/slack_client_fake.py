"""A stand-in for the two Slack Web API methods the webhooks poster calls.

It records every call's arguments and answers from what the test configured: a lookup table
of addresses to user ids (a miss is Slack's ``users_not_found``), or an error to raise. The
poster receives it through its constructor, as it receives the real ``AsyncWebClient``.
"""

from typing import Any, cast

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.slack_response import SlackResponse

from capabilities.webhooks.adapters.slack import SlackChannelPoster, SlackDeliveryPoster

TENANT = "T0TEST"


def slack_error(code: str, *, status: int = 200, headers: dict[str, str] | None = None) -> SlackApiError:
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/x",
        req_args={},
        data={"ok": False, "error": code},
        headers=headers or {},
        status_code=status,
    )
    return SlackApiError(code, response)


class FakeSlackClient:
    def __init__(self, users: dict[str, str] | None = None, *, post_error: BaseException | None = None) -> None:
        self.users = users or {}
        self.post_error = post_error
        self.posts: list[dict[str, Any]] = []
        self.lookups: list[str] = []

    async def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        self.posts.append(kwargs)
        if self.post_error is not None:
            raise self.post_error
        return {"ok": True, "ts": "1700000000.000100"}

    async def users_lookupByEmail(self, *, email: str) -> dict[str, Any]:
        self.lookups.append(email)
        if email not in self.users:
            raise slack_error("users_not_found")
        return {"ok": True, "user": {"id": self.users[email]}}

    def section_texts(self) -> list[str]:
        """The mrkdwn text of every section in the last post."""
        return [block["text"]["text"] for block in self.posts[-1]["blocks"] if block["type"] == "section"]


def poster(client: FakeSlackClient, *, lookups_per_message: int = 10) -> SlackChannelPoster:
    handle = cast(AsyncWebClient, client)
    return SlackChannelPoster(writes=handle, reads=handle, tenant=TENANT, lookups_per_message=lookups_per_message)


def delivery_poster(client: FakeSlackClient, *, lookups_per_message: int = 10) -> SlackDeliveryPoster:
    return poster(client, lookups_per_message=lookups_per_message).for_delivery()
