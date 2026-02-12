"""Slack-specific help text generation from Argument definitions.

Provides utilities to generate help text for Slack slash commands from their
Argument definitions, with optional i18n support.
"""

from typing import Callable, List, Optional

from infrastructure.platforms.parsing import Argument

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
    translate: Optional[Callable[[Optional[str], str], str]] = None,
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
