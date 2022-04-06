import time
from datetime import datetime, timedelta


def get_incident_channels(client):
    channels = []
    response = client.conversations_list(
        exclude_archived=True, limit=1000, types="public_channel"
    )
    if response["ok"]:
        channels = list(
            filter(lambda x: x["name"].startswith("incident-20"), response["channels"])
        )
    return channels


def get_messages_in_time_period(client, channel_id, time_delta):
    client.conversations_join(channel=channel_id)
    messages = client.conversations_history(
        channel=channel_id,
        limit=10,
        oldest=time.mktime((datetime.now() - time_delta).timetuple()),
    )
    if messages["ok"]:
        return list(
            filter(lambda x: "team" in x, messages["messages"])
        )  # Return only messages from users
    else:
        return []


def get_stale_channels(client):
    STALE_PERIOD = timedelta(days=14)
    now = datetime.now()
    stale_channels = []
    channels = list(
        filter(
            lambda x: x["created"] < time.mktime((now - STALE_PERIOD).timetuple()),
            get_incident_channels(client),
        )
    )
    stale_channels = list(
        filter(
            lambda x: len(get_messages_in_time_period(client, x["id"], STALE_PERIOD))
            == 0,
            channels,
        )
    )
    return stale_channels


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
