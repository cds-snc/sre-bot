"""Slack registrar scoped to one plugin's entry-point name.

The host hands each plugin's ``register_slack_commands`` hookimpl its own
``PluginSlackRegistrar``, so every block-action and view-submission id it
registers carries that plugin's entry-point name and two plugins cannot
claim the same id. Commands and the reply interface pass through unchanged.

See: decisions/transport-slack.md (Block actions and view submissions),
decisions/platform-entrypoints.md rule 2
"""

from collections.abc import Callable
from typing import Any

from contracts.slack.models import Argument, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender


class PluginSlackRegistrar:
    """Delegates to the host registrar, rejecting listener ids outside the plugin's namespace."""

    def __init__(self, registrar: SlackCommandRegistrar, plugin_name: str) -> None:
        self._registrar = registrar
        self.plugin_name = plugin_name

    @property
    def reply(self) -> SlackReplySender:
        """The host registrar's reply interface."""
        return self._registrar.reply

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
        """Register a command on the host registrar unchanged."""
        self._registrar.register_command(
            command,
            handler,
            description=description,
            description_key=description_key,
            usage_hint=usage_hint,
            examples=examples,
            example_keys=example_keys,
            parent=parent,
            legacy_mode=legacy_mode,
            arguments=arguments,
            schema=schema,
            argument_mapper=argument_mapper,
            fallback_handler=fallback_handler,
        )

    def register_block_action(self, action_id: str, listener: Callable[..., object]) -> None:
        """Register a block action whose id starts with the plugin's entry-point name."""
        self._require_own_prefix(action_id)
        self._registrar.register_block_action(action_id, listener)

    def register_view_submission(self, callback_id: str, listener: Callable[..., object]) -> None:
        """Register a view submission whose id starts with the plugin's entry-point name."""
        self._require_own_prefix(callback_id)
        self._registrar.register_view_submission(callback_id, listener)

    def _require_own_prefix(self, listener_id: str) -> None:
        if not listener_id.startswith(f"{self.plugin_name}."):
            raise ValueError(f"Slack id {listener_id!r} must start with the plugin's entry-point name {self.plugin_name!r}.")
