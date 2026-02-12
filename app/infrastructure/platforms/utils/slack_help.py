"""Slack-specific help text generation from Argument definitions.

Provides utilities to generate help text for Slack slash commands from their
Argument definitions, with optional i18n support.
"""

from typing import TYPE_CHECKING, Callable, List, Optional

from infrastructure.platforms.parsing import Argument

if TYPE_CHECKING:
    from infrastructure.platforms.models import CommandDefinition

SLACK_HELP_KEYWORDS = frozenset({"help", "aide", "--help", "-h"})


def build_slack_display_path(command_path: str) -> str:
    """Convert dot-separated command path into space-separated display path.

    Args:
        command_path: Command path in dot notation (e.g., "sre.dev.aws").

    Returns:
        Space-separated path (e.g., "sre dev aws").
    """
    return command_path.replace(".", " ")


def build_slack_command_signature(
    command_path: str,
    usage_hint: str = "",
    prefix: str = "/",
) -> str:
    """Build a Slack command signature string with optional usage hints.

    Args:
        command_path: Command path in dot notation (e.g., "sre.dev.aws").
        usage_hint: Optional usage string (e.g., "<account_id>").
        prefix: Optional prefix (default: "/").

    Returns:
        Command signature (e.g., "/sre dev aws <account_id>").
    """
    display_path = build_slack_display_path(command_path)
    if usage_hint:
        return f"{prefix}{display_path} {usage_hint}"
    return f"{prefix}{display_path}"


def generate_slack_help_text(
    arguments: List[Argument],
    include_types: bool = True,
    include_defaults: bool = True,
    indent: str = "  ",
    include_header: bool = False,
    header: Optional[str] = None,
    translate: Optional[Callable[[Optional[str], str, str], str]] = None,
    locale: str = "en-US",
) -> str:
    """Generate Slack help text from Argument definitions.

    Creates formatted help text showing all arguments, their types, defaults,
    and descriptions for display to users.

    Args:
        arguments: List of Argument definitions.
        include_types: Whether to show argument types in help.
        include_defaults: Whether to show default values.
        indent: String to use for indentation (default: 2 spaces).
        include_header: Whether to include a header line before arguments.
        header: Optional header string (caller provides formatting).
        translate: Optional function for translating description keys.

    Returns:
        Formatted help text showing all arguments.

    Example:
        >>> args = [
        ...     Argument(name="email", type=ArgumentType.EMAIL, required=True),
        ...     Argument(name="--role", type=ArgumentType.STRING, default="MEMBER"),
        ... ]
        >>> help_text = generate_slack_help_text(
        ...     args, include_header=True, header="Arguments:"
        ... )
        >>> print(help_text)
        Arguments:
          email (EMAIL, required)
              Email address of the user
          --role VALUE (STRING, optional)
              Role assignment [default: MEMBER]
    """
    if not arguments:
        return ""

    lines: List[str] = []

    if include_header and header:
        lines.append(header)
        lines.append("")

    for i, arg in enumerate(arguments):
        # Argument name and syntax
        if arg.is_positional:
            arg_str = f"{arg.name}"
        elif arg.is_flag:
            arg_str = f"{arg.name}"
        else:  # is_option
            arg_str = f"{arg.name} VALUE"

        # Add type and required info
        type_info = ""
        if include_types:
            status = "required" if arg.required else "optional"
            type_info = f"({arg.type.value}, {status})"

        # Build signature line: name + type info
        if type_info:
            lines.append(f"{indent}{arg_str} {type_info}")
        else:
            lines.append(f"{indent}{arg_str}")

        # Add aliases if present
        if arg.aliases:
            aliases_str = ", ".join(arg.aliases)
            lines.append(f"{indent}{indent}Aliases: {aliases_str}")

        # Add description
        if arg.description or arg.description_key:
            description = (
                translate(arg.description_key, arg.description)
                if translate
                else arg.description
            )
            if description:
                lines.append(f"{indent}{indent}{description}")

        # Add default value if applicable
        if include_defaults and arg.default is not None:
            lines.append(f"{indent}{indent}Default: {arg.default}")

        # Add choices if applicable
        if arg.choices:
            choices_str = ", ".join(arg.choices)
            lines.append(f"{indent}{indent}Values: {choices_str}")

        # Add blank line between arguments for visual separation (except after last one)
        if i < len(arguments) - 1:
            lines.append("")

    return "\n".join(lines)


def generate_usage_line(
    command_path: str,
    arguments: List[Argument],
) -> str:
    """Generate a Slack usage line for a command.

    Creates a concise usage example showing command syntax with arguments.

    Args:
        command_path: Full command path (e.g., "sre.groups.add").
        arguments: List of Argument definitions.

    Returns:
        Usage line (e.g., "Usage: /sre groups add EMAIL GROUP_ID --justification TEXT").

    Example:
        >>> args = [
        ...     Argument(name="email", type=ArgumentType.EMAIL, required=True),
        ...     Argument(name="group_id", type=ArgumentType.STRING, required=True),
        ...     Argument(name="--justification", type=ArgumentType.STRING),
        ... ]
        >>> usage = generate_usage_line("sre.groups.add", args)
        >>> print(usage)
        Usage: /sre groups add EMAIL GROUP_ID [--justification TEXT]
    """
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
        else:  # is_option
            if arg.required:
                arg_parts.append(f"{arg.name} VALUE")
            else:
                arg_parts.append(f"[{arg.name} VALUE]")

    args_str = " ".join(arg_parts)
    if args_str:
        return f"Usage: /{display_path} {args_str}"
    return f"Usage: /{display_path}"


def get_argument_by_name(
    arguments: List[Argument],
    name: str,
) -> Optional[Argument]:
    """Find an argument by name or alias.

    Args:
        arguments: List of Argument definitions.
        name: Argument name or alias to search for.

    Returns:
        The matching Argument, or None if not found.

    Example:
        >>> args = [
        ...     Argument(name="--role", aliases=["-r"]),
        ... ]
        >>> arg = get_argument_by_name(args, "-r")
        >>> assert arg.name == "--role"
    """
    for arg in arguments:
        if arg.name == name:
            return arg
        if arg.aliases and name in arg.aliases:
            return arg
    return None


class SlackHelpGenerator:
    """Unified Slack help text generator with DRY principles.

    Consolidates help generation logic into single class with mode-based API:
    - "tree": Show command tree starting from root
    - "command": Show single command with signature, args, examples
    - "arguments": Show arguments only

    Usage:
        generator = SlackHelpGenerator(
            commands=provider._commands,
            translator=provider._translate_or_fallback,
        )
        help_text = generator.generate(command_path="sre", mode="tree")
    """

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
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Formatted help text for the specified mode
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
        """Generate help tree for command and children.

        Args:
            root_path: Command path to show tree for (None for all top-level)
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Formatted tree of commands
        """
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
            # Show children of specified command
            children = self._get_child_commands(root_path)
            if not children:
                return self._translator(
                    "commands.errors.no_commands_under",
                    f"No commands found under `{root_path}`",
                    locale,
                )
            for cmd_def in children:
                self._append_command_tree_entry(
                    lines, cmd_def, indent_level=0, locale=locale
                )
        else:
            # Show all top-level commands
            top_level = [cmd for cmd in self._commands.values() if not cmd.parent]
            if not top_level:
                return self._translator(
                    "commands.errors.no_top_level_commands",
                    "No top-level commands registered.",
                    locale,
                )
            for cmd_def in sorted(top_level, key=lambda c: c.name):
                self._append_command_tree_entry(
                    lines, cmd_def, indent_level=0, locale=locale
                )

        return "\n".join(lines)

    def _generate_command(self, command_path: str, locale: str = "en-US") -> str:
        """Generate help for a specific command.

        Args:
            command_path: Full command path
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Command-specific help text
        """
        cmd_def = self._commands.get(command_path)
        if not cmd_def:
            return f"Unknown command: `{command_path}`"

        lines = []

        # Command signature
        signature = build_slack_command_signature(command_path, cmd_def.usage_hint)
        lines.append(f"*{signature}*")
        lines.append("")

        # Description (skip auto-generated)
        if not cmd_def.is_auto_generated:
            desc = self._translator(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(desc)
                lines.append("")

        # Arguments (if leaf command)
        if cmd_def.arguments:
            arguments_label = self._translator(
                "commands.labels.arguments", "Arguments:", locale
            )
            args_help = generate_slack_help_text(
                cmd_def.arguments,
                include_types=True,
                include_defaults=True,
                indent="  ",
                include_header=True,
                header=f"*{arguments_label}*",
                translate=self._translator,
                locale=locale,
            )
            lines.append(args_help)

        # Examples (skip auto-generated)
        if not cmd_def.is_auto_generated and cmd_def.examples:
            examples_label = self._translator(
                "commands.labels.examples", "Examples:", locale
            )
            lines.append("")
            lines.append(f"*{examples_label}*")
            for example in cmd_def.examples:
                lines.append(f"  `{example}`")

        # Sub-commands (if parent node)
        children = self._get_child_commands(command_path)
        if children:
            lines.append("")
            subcommands_label = self._translator(
                "commands.labels.subcommands", "Sub-commands:", locale
            )
            lines.append(f"*{subcommands_label}*")
            for child in children:
                self._append_command_tree_entry(
                    lines, child, indent_level=0, locale=locale
                )

        return "\n".join(lines)

    def _generate_arguments(self, command_path: str, locale: str = "en-US") -> str:
        """Generate help for arguments only.

        Args:
            command_path: Full command path
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Arguments-only help text
        """
        cmd_def = self._commands.get(command_path)
        if not cmd_def or not cmd_def.arguments:
            return f"Command `{command_path}` has no arguments."

        arguments_label = self._translator(
            "commands.labels.arguments", "Arguments:", locale
        )
        return generate_slack_help_text(
            cmd_def.arguments,
            include_types=True,
            include_defaults=True,
            indent="  ",
            include_header=True,
            header=f"*{arguments_label}*",
            translate=self._translator,
            locale=locale,
        )

    def _append_command_tree_entry(
        self,
        lines: List[str],
        cmd_def: "CommandDefinition",
        indent_level: int,
        locale: str = "en-US",
    ) -> None:
        """Append command tree entry to help text (DRY method).

        Args:
            lines: List to append to
            cmd_def: CommandDefinition to render
            indent_level: Indentation level (0=root)
            locale: Locale string (e.g., "en-US", "fr-FR")
        """
        indent = "  " * indent_level
        display_path = build_slack_display_path(cmd_def.full_path)

        # Build bullet point with path and description
        if not cmd_def.is_auto_generated:
            desc = self._translator(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(f"{indent}• /{display_path} - {desc}")
            else:
                lines.append(f"{indent}• /{display_path}")
        else:
            lines.append(f"{indent}• /{display_path}")

        # Add signature
        signature = build_slack_command_signature(cmd_def.full_path, cmd_def.usage_hint)
        lines.append(f"{indent}  `{signature}`")
        lines.append("")

    def _get_child_commands(self, parent_path: str) -> List["CommandDefinition"]:
        """Get all direct children of a command node.

        Args:
            parent_path: Parent full path

        Returns:
            Sorted list of child CommandDefinition objects
        """
        children = [cmd for cmd in self._commands.values() if cmd.parent == parent_path]
        return sorted(children, key=lambda c: c.name)
