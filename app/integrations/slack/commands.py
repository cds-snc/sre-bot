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
            args.append(arg)
            arg = ""
        else:
            arg += char
    if arg:
        args.append(arg)
    return args
