"""Slack Channels Module.

This module contains the channel related functionality for the Slack integration."""

import re
import time
from datetime import datetime, timedelta


def get_channels(client, pattern=None):
    channels = []
    cursor = None

    # Execute while the next_cursor is not empty. We need to iterate through the collection limiting to a max of 100 channels
    # at a time. The cursor is used to keep track of the current position in the collection. This is due to Slack's pagination
    # and the way it hanles retrieval of channels.
    while True:
        response = client.conversations_list(
            exclude_archived=True, limit=100, types="public_channel", cursor=cursor
        )

        # if we did not get a successful response, break out of the loop
        if not response.get("ok"):
            break

        if pattern is not None:
            # filter the channels to only include channels that match the pattern
            for channel in response.get("channels", []):
                if re.match(pattern, channel["name"]):
                    channels.append(channel)
        else:
            channels.extend(response.get("channels", []))

        # get the next cursor
        cursor = response.get("response_metadata", {}).get("next_cursor")

        # if the cursor is empty, break out of the loop
        if not cursor:
            break

    # return the list of incident channels
    return channels


def get_stale_channels(client, pattern=None):
    STALE_PERIOD = timedelta(days=14)
    now = datetime.now()
    stale_channels = []
    channels = list(
        filter(
            lambda x: x["created"] < time.mktime((now - STALE_PERIOD).timetuple()),
            get_channels(client, pattern=pattern),
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
