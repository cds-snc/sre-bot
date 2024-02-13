"""Slack Channels Module.

This module contains the channel related functionality for the Slack integration."""

import re


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
