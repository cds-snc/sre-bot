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


def fetch_user_details(client, channel_id):
    """
    Fetches user details from a Slack channel, excluding users with the real names 'SRE' and 'SRE Dev'.

    Parameters:
    client (object): The Slack client used to interact with the Slack API.
    channel_id (str): The ID of the Slack channel from which to fetch user details.

    Returns:
    list: A list of dictionaries containing user details, formatted for Slack modal blocks.
    """
    # get all members of the channel
    result = client.conversations_members(channel=channel_id)
    users = []
    # extract the real name of the user and append it to the users list, excluding users with the real names 'SRE' and 'SRE Dev'
    for user_id in result["members"]:
        user_info = client.users_info(user=user_id)
        if (
            user_info["user"]["real_name"] != "SRE"
            and user_info["user"]["real_name"] != "SRE Dev"
        ):
            users.append(
                {
                    "text": {
                        "type": "plain_text",
                        "text": user_info["user"]["real_name"],
                        "emoji": True,
                    },
                    "value": user_info["user"]["id"],
                }
            )
    return users
