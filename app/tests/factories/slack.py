"""Protocol-conformant fakes for the Slack handler contract."""

from collections.abc import Callable
from typing import Any

from contracts.operations import OperationResult
from contracts.slack.models import Argument, CommandPayload, CommandResponse
from contracts.slack.reply import SlackReplySender


class FakeSlackReply:
    """Records every reply call and answers each with the same configured result."""

    def __init__(self, result: OperationResult[None] | None = None) -> None:
        self.result: OperationResult[None] = result or OperationResult.success()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post_message(
        self,
        *,
        channel_id: str,
        text: str,
        username: str | None = None,
        icon_url: str | None = None,
    ) -> OperationResult[None]:
        self.calls.append(("post_message", {"channel_id": channel_id, "text": text, "username": username, "icon_url": icon_url}))
        return self.result

    def post_ephemeral(self, *, channel_id: str, user_id: str, text: str) -> OperationResult[None]:
        self.calls.append(("post_ephemeral", {"channel_id": channel_id, "user_id": user_id, "text": text}))
        return self.result

    def open_view(self, *, trigger_id: str, view: dict[str, Any]) -> OperationResult[None]:
        self.calls.append(("open_view", {"trigger_id": trigger_id, "view": view}))
        return self.result

    def calls_to(self, name: str) -> list[dict[str, Any]]:
        return [kwargs for called, kwargs in self.calls if called == name]


class FakeSlackRegistrar:
    """Records each registered command, block action and view submission, and exposes a fake reply interface."""

    def __init__(self, reply: FakeSlackReply | None = None) -> None:
        self._reply = reply or FakeSlackReply()
        self.commands: list[dict[str, Any]] = []
        self.block_actions: dict[str, Callable[..., object]] = {}
        self.view_submissions: dict[str, Callable[..., object]] = {}

    @property
    def reply(self) -> SlackReplySender:
        return self._reply

    def register_command(
        self,
        command: str,
        handler: Callable[..., CommandResponse] | None,
        description: str = "",
        description_key: str | None = None,
        usage_hint: str = "",
        examples: list[str] | None = None,
        example_keys: list[str] | None = None,
        parent: str | None = None,
        legacy_mode: bool = False,
        arguments: list[Argument] | None = None,
        schema: type[Any] | None = None,
        argument_mapper: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        fallback_handler: Callable[[CommandPayload], CommandResponse] | None = None,
    ) -> None:
        self.commands.append(
            {
                "command": command,
                "handler": handler,
                "description": description,
                "description_key": description_key,
                "usage_hint": usage_hint,
                "examples": examples,
                "example_keys": example_keys,
                "parent": parent,
                "legacy_mode": legacy_mode,
                "arguments": arguments,
                "schema": schema,
                "argument_mapper": argument_mapper,
                "fallback_handler": fallback_handler,
            }
        )

    def register_block_action(self, action_id: str, listener: Callable[..., object]) -> None:
        self.block_actions[action_id] = listener

    def register_view_submission(self, callback_id: str, listener: Callable[..., object]) -> None:
        self.view_submissions[callback_id] = listener

    def command(self, name: str, parent: str | None = None) -> dict[str, Any]:
        """Return the one registration matching ``name`` and ``parent``."""
        (match,) = [entry for entry in self.commands if entry["command"] == name and entry["parent"] == parent]
        return match
