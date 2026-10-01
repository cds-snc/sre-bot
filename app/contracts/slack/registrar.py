"""Registrar Protocol features use to attach Slack command handlers.

The ``register_slack_commands`` hookspec hands features this Protocol, never
the Slack SDK runtime (the Bolt app or the platform provider).

See: decisions/platform-entrypoints.md, decisions/transport-slack.md
"""

from collections.abc import Callable
from typing import Any, Protocol

from contracts.slack.models import Argument, CommandPayload, CommandResponse
from contracts.slack.reply import SlackReplyPort


class SlackCommandRegistrar(Protocol):
    """Registers hierarchical Slack commands and exposes the reply port."""

    @property
    def reply(self) -> SlackReplyPort:
        """Port handlers use to post messages and open views."""
        ...

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
        """Register a command, creating intermediate nodes for a dotted ``parent``.

        Args:
            command: Command name (e.g., "aws", "test-connection").
            handler: Handler returning a ``CommandResponse``; ``None`` for a
                grouping node whose help is generated.
            description: English description (fallback if translation unavailable).
            description_key: i18n translation key for the description.
            usage_hint: Usage string (e.g., "<account_id>").
            examples: Example argument strings.
            example_keys: Translation keys for the examples.
            parent: Dot notation parent path (e.g., "sre.dev").
            legacy_mode: If True, bypass automatic help interception.
            arguments: Argument definitions for parsing.
            schema: Pydantic schema validating the parsed arguments.
            argument_mapper: Transforms parsed arguments into schema fields.
            fallback_handler: Called when the command expects arguments but none are given.
        """
        ...
