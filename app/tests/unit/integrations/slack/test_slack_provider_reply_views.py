"""Behavior tests for view methods on the reply interface exposed by ``SlackPlatformProvider.reply``.

Tests for open_view returning the view id and update_view sending view id and hash.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from contracts.operations import OperationStatus
from integrations.slack.provider import SlackPlatformProvider

pytestmark = pytest.mark.unit


def _slack_error(code: str, *, headers: dict[str, str] | None = None, status_code: int = 200) -> SlackApiError:
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/views.open",
        req_args={},
        data={"ok": False, "error": code},
        headers=headers or {},
        status_code=status_code,
    )
    return SlackApiError(f"The request to the Slack API failed. (error: {code})", response)


def _provider(client: Any | None) -> SlackPlatformProvider:
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(settings=settings)
    provider._client = client
    return provider


class TestOpenViewReturnsViewId:
    """open_view returns the view id from the Slack API response."""

    def test_open_view_returns_view_id_in_success_result(self) -> None:
        client = MagicMock()
        client.views_open.return_value = {"view": {"id": "V123ABC"}}

        result = _provider(client).reply.open_view(trigger_id="T1", view={"type": "modal"})

        assert result.status is OperationStatus.SUCCESS
        assert result.data == "V123ABC"

    def test_open_view_extracts_id_from_nested_response(self) -> None:
        client = MagicMock()
        client.views_open.return_value = {"ok": True, "view": {"id": "V456DEF", "team_id": "T1"}}

        result = _provider(client).reply.open_view(trigger_id="T2", view={"type": "modal", "blocks": []})

        assert result.status is OperationStatus.SUCCESS
        assert result.data == "V456DEF"

    def test_open_view_returns_error_when_response_has_no_id(self) -> None:
        client = MagicMock()
        # Response without view id
        client.views_open.return_value = {"ok": True}

        result = _provider(client).reply.open_view(trigger_id="T3", view={"type": "modal"})

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "MISSING_VIEW_ID"

    def test_open_view_classifies_slack_error(self) -> None:
        client = MagicMock()
        error = _slack_error("expired_trigger_id")
        client.views_open.side_effect = error

        result = _provider(client).reply.open_view(trigger_id="T4", view={"type": "modal"})

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "expired_trigger_id"


class TestUpdateView:
    """update_view sends the view id and hash to Slack."""

    def test_update_view_sends_view_id_and_view(self) -> None:
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        view = {"type": "modal", "blocks": []}

        result = _provider(client).reply.update_view(view_id="V123", view=view)

        client.views_update.assert_called_once_with(view=view, view_id="V123", hash=None)
        assert result.status is OperationStatus.SUCCESS

    def test_update_view_sends_hash_when_provided(self) -> None:
        client = MagicMock()
        client.views_update.return_value = {"ok": True}
        view = {"type": "modal"}

        result = _provider(client).reply.update_view(view_id="V456", view=view, hash="abc123")

        client.views_update.assert_called_once_with(view=view, view_id="V456", hash="abc123")
        assert result.status is OperationStatus.SUCCESS

    def test_update_view_classifies_slack_error(self) -> None:
        client = MagicMock()
        error = _slack_error("not_a_valid_view")
        client.views_update.side_effect = error

        result = _provider(client).reply.update_view(view_id="V789", view={"type": "modal"})

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "not_a_valid_view"

    def test_update_view_handles_stale_hash(self) -> None:
        client = MagicMock()
        error = _slack_error("stale_hash")
        client.views_update.side_effect = error

        result = _provider(client).reply.update_view(view_id="V999", view={"type": "modal"}, hash="old123")

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "stale_hash"
