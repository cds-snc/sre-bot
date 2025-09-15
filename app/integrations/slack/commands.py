"""Slack Commands utilities functions"""


def parse_command(command):
    """
    Parses a command string into a list of arguments.
    Args:
        command (str): The command string.
    Returns:
        List[str]: The list of arguments.
    """
    args = []
    arg = ""
    in_quote = False
    for char in command:
        if char == '"':
            if in_quote:
                args.append(arg)
                arg = ""
                in_quote = False
            else:
                in_quote = True
        elif char == " " and not in_quote:
            if arg:
                args.append(arg)
            arg = ""
        else:
            arg += char
    if arg:
        args.append(arg)
    return args


def parse_flags(args: list[str]) -> tuple[list[str], dict[str, str | bool]]:
    """
    Parses a list of arguments into positional args and flags.
    This can be used in conjunction with parse_command to support flags in commands.

    Flags can be --flag, --key value, or -f.

    Args:
        args (List[str]): The list of arguments.
    Returns:
        Tuple[List[str], Dict[str, Union[str, bool]]]: A tuple containing the list of positional arguments and a dictionary of flags.
    """
    positional: list[str] = []
    flags: dict[str, str | bool] = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg.lstrip("-")
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                flags[key] = args[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        elif arg.startswith("-") and len(arg) == 2:
            key = arg.lstrip("-")
            flags[key] = True
            i += 1
        else:
            positional.append(arg)
            i += 1
    return positional, flags
