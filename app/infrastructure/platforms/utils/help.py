"""Automatic help text generation from Argument definitions.

Provides utilities to generate help text for commands from their
Argument definitions, with i18n support.
"""

from typing import List, Optional
from infrastructure.platforms.parsing import Argument


def generate_help_text(
    arguments: List[Argument],
    include_types: bool = True,
    include_defaults: bool = True,
    indent: str = "  ",
) -> str:
    """Generate help text from Argument definitions.

    Creates formatted help text showing all arguments, their types, defaults,
    and descriptions for display to users.

    Args:
        arguments: List of Argument definitions.
        include_types: Whether to show argument types in help.
        include_defaults: Whether to show default values.
        indent: String to use for indentation (default: 2 spaces).

    Returns:
        Formatted help text showing all arguments.

    Example:
        >>> args = [
        ...     Argument(name="email", type=ArgumentType.EMAIL, required=True),
        ...     Argument(name="--role", type=ArgumentType.STRING, default="MEMBER"),
        ... ]
        >>> help_text = generate_help_text(args)
        >>> print(help_text)
        Arguments:
          email (EMAIL, required)
              Email address of the user
          --role VALUE (STRING, optional)
              Role assignment [default: MEMBER]
    """
    if not arguments:
        return ""

    lines = []

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
        if arg.description:
            lines.append(f"{indent}{indent}{arg.description}")

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
    """Generate a usage line for a command.

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
    parts = command_path.split(".")
    cmd_str = " ".join(parts)

    arg_parts = []
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
        return f"Usage: /{cmd_str} {args_str}"
    else:
        return f"Usage: /{cmd_str}"


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
