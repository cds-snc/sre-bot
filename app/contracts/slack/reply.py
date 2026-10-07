"""Outbound messaging Protocol Slack handlers use to reply.

Handlers reach the Slack Web API only through this interface, obtained from
``SlackCommandRegistrar.reply``. Implementations classify Web API failures
into an ``OperationResult`` and never raise.

See: decisions/transport-slack.md (Errors)
"""

from typing import Any, Protocol

from contracts.operations import OperationResult


class SlackReplySender(Protocol):
    """Replies a Slack handler can send as the bot."""

    def post_message(
        self,
        *,
        channel_id: str,
        text: str,
        username: str | None = None,
        icon_url: str | None = None,
    ) -> OperationResult[None]:
        """Post a message to a channel, optionally under a custom name and avatar."""
        ...

    def post_ephemeral(self, *, channel_id: str, user_id: str, text: str) -> OperationResult[None]:
        """Post a message in a channel that only one user sees."""
        ...

    def open_view(self, *, trigger_id: str, view: dict[str, Any]) -> OperationResult[str]:
        """Open a modal view for the interaction identified by ``trigger_id``.

        Returns:
            Success carrying the opened view's id, for ``update_view``.
        """
        ...

    def update_view(self, *, view_id: str, view: dict[str, Any], hash: str | None = None) -> OperationResult[None]:  # noqa: A002 -- Slack's parameter name
        """Replace an open modal view; ``hash`` guards against concurrent updates."""
        ...
