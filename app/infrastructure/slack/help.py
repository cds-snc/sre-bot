"""Slack help text generation from command definitions."""

from typing import Callable, List, Optional

from infrastructure.slack.parsing import Argument
from infrastructure.slack.models import CommandDefinition

SLACK_HELP_KEYWORDS = frozenset({"help", "aide", "--help", "-h"})


def build_slack_display_path(command_path: str) -> str:
    """Convert dot-separated path to space-separated display path."""
    return command_path.replace(".", " ")


def build_slack_command_signature(
    command_path: str,
    usage_hint: str = "",
    prefix: str = "/",
) -> str:
    """Build a Slack command signature string."""
    display_path = build_slack_display_path(command_path)
    if usage_hint:
        return f"{prefix}{display_path} {usage_hint}"
    return f"{prefix}{display_path}"


def generate_slack_help_text(
    arguments: List[Argument],
    include_types: bool = True,
    include_defaults: bool = True,
    indent: str = "  ",
) -> str:
    """Generate Slack help text from Argument definitions."""
    if not arguments:
        return ""

    lines: List[str] = []

    for i, arg in enumerate(arguments):
        if arg.is_positional:
            arg_str = f"{arg.name}"
        elif arg.is_flag:
            arg_str = f"{arg.name}"
        else:
            arg_str = f"{arg.name} VALUE"

        type_info = ""
        if include_types:
            status = "required" if arg.required else "optional"
            type_info = f"({arg.type.value}, {status})"

        if type_info:
            lines.append(f"{indent}{arg_str} {type_info}")
        else:
            lines.append(f"{indent}{arg_str}")

        if arg.aliases:
            aliases_str = ", ".join(arg.aliases)
            lines.append(f"{indent}{indent}Aliases: {aliases_str}")

        if arg.description:
            lines.append(f"{indent}{indent}{arg.description}")

        if include_defaults and arg.default is not None:
            lines.append(f"{indent}{indent}Default: {arg.default}")

        if arg.choices:
            choices_str = ", ".join(arg.choices)
            lines.append(f"{indent}{indent}Values: {choices_str}")

        if i < len(arguments) - 1:
            lines.append("")

    return "\n".join(lines)


def generate_usage_line(
    command_path: str,
    arguments: List[Argument],
) -> str:
    """Generate a Slack usage line for a command."""
    display_path = build_slack_display_path(command_path)

    arg_parts: List[str] = []
    for arg in arguments:
        if arg.is_positional:
            if arg.required:
                arg_parts.append(arg.name.upper())
            else:
                arg_parts.append(f"[{arg.name.upper()}]")
        elif arg.is_flag:
            if arg.required:
                arg_parts.append(arg.name)
            else:
                arg_parts.append(f"[{arg.name}]")
        else:
            if arg.required:
                arg_parts.append(f"{arg.name} VALUE")
            else:
                arg_parts.append(f"[{arg.name} VALUE]")

    args_str = " ".join(arg_parts)
    if args_str:
        return f"Usage: /{display_path} {args_str}"
    return f"Usage: /{display_path}"


class SlackHelpGenerator:
    """Unified Slack help text generator."""

    def __init__(
        self,
        commands: dict,
        translator: Optional[Callable[[Optional[str], str, str], str]] = None,
    ):
        """Initialize help generator.

        Args:
            commands: Dict of registered CommandDefinition objects
            translator: Optional i18n translator function (key, fallback, locale) -> str
        """
        self._commands = commands
        self._translator = translator or (lambda key, fallback, locale: fallback)

    def generate(
        self, command_path: str, mode: str = "command", locale: str = "en-US"
    ) -> str:
        """Generate help text in specified mode.

        Args:
            command_path: Command path (e.g., "sre", "sre.groups")
            mode: Help mode ("tree", "command", "arguments")
            locale: Locale string

        Returns:
            Formatted help text
        """
        if mode == "tree":
            return self._generate_tree(command_path, locale)
        elif mode == "command":
            return self._generate_command(command_path, locale)
        elif mode == "arguments":
            return self._generate_arguments(command_path, locale)
        else:
            return f"Unknown help mode: {mode}"

    def _generate_tree(
        self, root_path: Optional[str] = None, locale: str = "en-US"
    ) -> str:
        """Generate help tree for command and children."""
        if not self._commands:
            return self._translator(
                "commands.errors.no_commands_registered",
                "No commands registered.",
                locale,
            )

        header = self._translator(
            "commands.labels.available_commands", "Available Commands", locale
        )
        lines = [f"*{header}*", ""]

        if root_path:
            children = self._get_child_commands(root_path)
            if not children:
                return f"No commands found under `{root_path}`"
            for cmd_def in children:
                self._append_command_tree_entry(lines, cmd_def, locale=locale)
        else:
            top_level = [cmd for cmd in self._commands.values() if not cmd.parent]
            if not top_level:
                return "No top-level commands registered."
            for cmd_def in sorted(top_level, key=lambda c: c.name):
                self._append_command_tree_entry(lines, cmd_def, locale=locale)

        return "\n".join(lines)

    def _generate_command(self, command_path: str, locale: str = "en-US") -> str:
        """Generate help for a specific command."""
        cmd_def = self._commands.get(command_path)
        if not cmd_def:
            return f"Unknown command: `{command_path}`"

        lines = []

        signature = build_slack_command_signature(command_path, cmd_def.usage_hint)
        lines.append(f"*{signature}*")
        lines.append("")

        if not cmd_def.is_auto_generated:
            desc = self._translator(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(desc)
                lines.append("")

        if cmd_def.arguments:
            arguments_label = self._translator(
                "commands.labels.arguments", "Arguments:", locale
            )
            lines.append(f"*{arguments_label}*")
            lines.append("")
            args_help = generate_slack_help_text(cmd_def.arguments)
            lines.append(args_help)

        children = self._get_child_commands(command_path)
        if children:
            lines.append("")
            subcommands_label = self._translator(
                "commands.labels.subcommands", "Sub-commands:", locale
            )
            lines.append(f"*{subcommands_label}*")
            lines.append("")
            for child in children:
                self._append_command_tree_entry(lines, child, locale=locale)

        return "\n".join(lines)

    def _generate_arguments(self, command_path: str, locale: str = "en-US") -> str:
        """Generate help for arguments only."""
        cmd_def = self._commands.get(command_path)
        if not cmd_def or not cmd_def.arguments:
            return f"Command `{command_path}` has no arguments."

        arguments_label = self._translator(
            "commands.labels.arguments", "Arguments:", locale
        )
        return f"*{arguments_label}*\n\n{generate_slack_help_text(cmd_def.arguments)}"

    def _append_command_tree_entry(
        self,
        lines: List[str],
        cmd_def: CommandDefinition,
        locale: str = "en-US",
    ) -> None:
        """Append command tree entry to help text."""
        display_path = build_slack_display_path(cmd_def.full_path)

        if not cmd_def.is_auto_generated:
            desc = self._translator(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(f"• /{display_path} - {desc}")
            else:
                lines.append(f"• /{display_path}")
        else:
            lines.append(f"• /{display_path}")

        signature = build_slack_command_signature(cmd_def.full_path, cmd_def.usage_hint)
        lines.append(f"  `{signature}`")
        lines.append("")

    def _get_child_commands(self, parent_path: str) -> List[CommandDefinition]:
        """Get all direct children of a command node."""
        children = [cmd for cmd in self._commands.values() if cmd.parent == parent_path]
        return sorted(children, key=lambda c: c.name)


__all__ = [
    "SLACK_HELP_KEYWORDS",
    "SlackHelpGenerator",
    "build_slack_command_signature",
    "build_slack_display_path",
    "generate_slack_help_text",
    "generate_usage_line",
]
