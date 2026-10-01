"""Slack Web API implementation of ``contracts.slack.reply.SlackReplyPort``.

Maps ``SlackApiError`` to ``OperationResult`` through ``classify_slack_error``
so handlers branch on a result instead of catching SDK exceptions
(decisions/transport-slack.md, Errors).
"""

from collections.abc import Callable
from typing import Any

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from contracts.operations import ErrorCode, OperationResult, OperationStatus
from integrations.slack.client import classify_slack_error

logger = structlog.get_logger()


class SlackWebReply:
    """Send handler replies through a Slack Web client.

    The client is resolved on every call: the platform provider only has one
    after it has started, which happens after command registration.
    """

    def __init__(self, client: Callable[[], WebClient | None]) -> None:
        self._client = client

    def post_message(
        self,
        *,
        channel_id: str,
        text: str,
        username: str | None = None,
        icon_url: str | None = None,
    ) -> OperationResult[None]:
        """Post a message to a channel, optionally under a custom name and avatar."""
        return self._call(
            "chat_postMessage",
            lambda client: client.chat_postMessage(channel=channel_id, text=text, username=username, icon_url=icon_url),
        )

    def post_ephemeral(self, *, channel_id: str, user_id: str, text: str) -> OperationResult[None]:
        """Post a message in a channel that only one user sees."""
        return self._call(
            "chat_postEphemeral",
            lambda client: client.chat_postEphemeral(channel=channel_id, user=user_id, text=text),
        )

    def open_view(self, *, trigger_id: str, view: dict[str, Any]) -> OperationResult[None]:
        """Open a modal view for the interaction identified by ``trigger_id``."""
        return self._call("views_open", lambda client: client.views_open(trigger_id=trigger_id, view=view))

    def _call(self, method: str, call: Callable[[WebClient], object]) -> OperationResult[None]:
        """Run one Web API call and turn any failure into an error result."""
        client = self._client()
        if client is None:
            return OperationResult.permanent_error(
                "Slack client is not initialized",
                error_code=ErrorCode.INITIALIZATION_ERROR,
            )

        try:
            call(client)
        except SlackApiError as exc:
            return _classified(method, exc)
        except Exception as exc:  # noqa: BLE001 - a reply failure is reported to the handler, never raised
            logger.warning("slack_reply_failed", method=method, error=str(exc))
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"Slack {method} failed: {exc}",
                error_code=ErrorCode.UNEXPECTED_ERROR,
                cause=exc,
            )
        return OperationResult.success()


def _classified(method: str, exc: SlackApiError) -> OperationResult[None]:
    """Classify a Slack API error; a code the catalogues do not name is permanent."""
    try:
        status, error_code, retry_after = classify_slack_error(exc)
    except SlackApiError:
        status, error_code, retry_after = OperationStatus.PERMANENT_ERROR, exc.response.get("error"), None

    return OperationResult(
        status=status,
        message=f"Slack {method} failed: {error_code}",
        error_code=error_code,
        retry_after=retry_after,
        cause=exc,
    )
