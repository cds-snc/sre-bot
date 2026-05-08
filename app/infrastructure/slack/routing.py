"""Slack command routing — hierarchical command tree, dispatch, and help generation."""

from typing import Callable, Dict, List, Optional

import structlog

from infrastructure.slack.help import SLACK_HELP_KEYWORDS, SlackHelpGenerator
from infrastructure.slack.models import (
    CommandDefinition,
    CommandPayload,
    CommandResponse,
)
from infrastructure.slack.parsing import (
    Argument,
    ArgumentParsingError,
    CommandArgumentParser,
)

logger = structlog.get_logger()


class CommandRouter:
    """Hierarchical command tree for Slack slash command dispatch.

    Register commands at startup, then route/dispatch at runtime.
    """

    def __init__(self, translator: Optional[Callable] = None) -> None:
        self._commands: Dict[str, CommandDefinition] = {}
        self._translator = translator
        self._logger = logger.bind(component="slack_command_router")
        self._help_generator = SlackHelpGenerator(
            commands=self._commands,
            translator=self._translate_or_fallback,
        )

    def set_translator(self, translator: Callable) -> None:
        """Inject i18n translator callable."""
        self._translator = translator

    def _translate_or_fallback(
        self,
        key: Optional[str],
        fallback: str,
        locale: str = "en-US",
    ) -> str:
        if not key or not self._translator:
            return fallback
        try:
            result = self._translator(key, fallback, locale)
            return result if result else fallback
        except Exception as e:
            self._logger.warning(
                "translation_failed", key=key, locale=locale, error=str(e)
            )
            return fallback

    def register(
        self,
        command: str,
        handler: Optional[Callable[..., CommandResponse]],
        description: str = "",
        description_key: Optional[str] = None,
        usage_hint: str = "",
        examples: Optional[list] = None,
        example_keys: Optional[list] = None,
        parent: Optional[str] = None,
        legacy_mode: bool = False,
        arguments: Optional[List[Argument]] = None,
        schema: Optional[type] = None,
        argument_mapper: Optional[Callable] = None,
        fallback_handler: Optional[Callable[[CommandPayload], CommandResponse]] = None,
    ) -> None:
        """Register a command in the command tree."""
        if parent:
            self._ensure_parent_chain_exists(parent)

        cmd_def = CommandDefinition(
            name=command,
            handler=handler,
            description=description,
            description_key=description_key,
            usage_hint=usage_hint,
            examples=examples or [],
            example_keys=example_keys or [],
            parent=parent,
            legacy_mode=legacy_mode,
            arguments=arguments,
            schema=schema,
            argument_mapper=argument_mapper,
            fallback_handler=fallback_handler,
        )

        self._commands[cmd_def.full_path] = cmd_def
        self._logger.debug(
            "slack_command_registered",
            command=command,
            parent=parent,
            full_path=cmd_def.full_path,
        )

    def root_commands(self) -> List[str]:
        """Return the unique set of top-level slash command names."""
        roots: List[str] = []
        seen: set = set()
        for full_path in self._commands:
            root = full_path.split(".")[0]
            if root not in seen:
                seen.add(root)
                roots.append(root)
        return sorted(roots)

    def route(
        self, root_command: str, text: str, payload: CommandPayload
    ) -> CommandResponse:
        """Route a slash command text recursively to the matching leaf handler.

        Args:
            root_command: Current command path segment (e.g. "sre", "sre.groups").
            text: Remaining text from the Slack command payload.
            payload: Full CommandPayload with user context.

        Returns:
            CommandResponse from the matched handler or auto-generated help.
        """
        if not text or not text.strip():
            return self.dispatch(root_command, payload)

        tokens = self._tokenize(text)
        if not tokens:
            return self.dispatch(root_command, payload)

        first_word = tokens[0]
        remaining_text = " ".join(tokens[1:]) if len(tokens) > 1 else ""

        if first_word.lower() in SLACK_HELP_KEYWORDS:
            payload.text = first_word
            return self.dispatch(root_command, payload)

        child_path = f"{root_command}.{first_word}"
        if child_path in self._commands:
            payload.text = remaining_text
            return self.route(child_path, remaining_text, payload)

        payload.text = text
        return self.dispatch(root_command, payload)

    def dispatch(
        self, command_name: str, payload: CommandPayload
    ) -> CommandResponse:  # noqa: C901
        """Dispatch a command to its registered handler."""
        cmd_def = self._commands.get(command_name)
        if not cmd_def:
            return CommandResponse(
                message=f"Unknown command: {command_name}",
                ephemeral=True,
            )

        user_locale = payload.user_locale

        if cmd_def.handler is None:
            help_text = self.generate_help(
                locale=user_locale, root_command=command_name
            )
            return CommandResponse(message=help_text, ephemeral=True)

        try:
            parsed_args = None

            if cmd_def.arguments:
                if not payload.text or not payload.text.strip():
                    if cmd_def.fallback_handler:
                        return cmd_def.fallback_handler(payload)
                    else:
                        help_text = self.generate_command_help(
                            command_name, locale=user_locale
                        )
                        return CommandResponse(message=help_text, ephemeral=True)

                parser = CommandArgumentParser(cmd_def.arguments)
                try:
                    parsed_args = parser.parse(payload.text)
                    mapped_args = (
                        cmd_def.argument_mapper(parsed_args)
                        if cmd_def.argument_mapper
                        else parsed_args
                    )
                    if cmd_def.schema:
                        _ = cmd_def.schema(**mapped_args)
                except ArgumentParsingError as e:
                    return CommandResponse(
                        message=f"❌ Argument parsing error: {e.message}",
                        ephemeral=True,
                    )
                except Exception as e:
                    return CommandResponse(
                        message=f"❌ Validation error: {str(e)}",
                        ephemeral=True,
                    )

            if parsed_args is not None:
                response = cmd_def.handler(payload, parsed_args)
            else:
                response = cmd_def.handler(payload)

            return response

        except Exception as e:
            self._logger.error(
                "command_handler_error", command=command_name, error=str(e)
            )
            return CommandResponse(
                message=f"Error executing {command_name}: {str(e)}",
                ephemeral=True,
            )

    def generate_help(
        self, locale: str = "en-US", root_command: Optional[str] = None
    ) -> str:
        """Generate Slack-formatted help text for a command tree or subtree."""
        if root_command:
            return self._help_generator.generate(
                root_command, mode="tree", locale=locale
            )
        return self._help_generator.generate("", mode="tree", locale=locale)

    def generate_command_help(self, command_name: str, locale: str = "en-US") -> str:
        """Generate help text for a single command."""
        return self._help_generator.generate(
            command_name, mode="command", locale=locale
        )

    def _ensure_parent_chain_exists(self, parent: str) -> None:
        if not parent:
            return
        parts = parent.split(".")
        for i in range(len(parts)):
            partial_path = ".".join(parts[: i + 1])
            if partial_path not in self._commands:
                node_parent = ".".join(parts[:i]) if i > 0 else None
                node_name = parts[i]
                auto_cmd = CommandDefinition(
                    name=node_name,
                    handler=None,
                    description=f"Commands for {node_name}",
                    parent=node_parent,
                    is_auto_generated=True,
                )
                self._commands[partial_path] = auto_cmd
                self._logger.debug(
                    "auto_generated_intermediate_command",
                    path=partial_path,
                    parent=node_parent,
                )

    def _tokenize(self, text: str) -> List[str]:
        parser = CommandArgumentParser([])
        return parser._tokenize(text)


__all__ = ["CommandRouter"]
