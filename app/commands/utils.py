def log_ops_message(client, message):
    channel_id = "C0388M21LKZ"
    client.conversations_join(channel=channel_id)
    client.chat_postMessage(channel=channel_id, text=message, as_user=True)


def parse_command(command):
    """
    Parses a command string into a list of arguments.
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
