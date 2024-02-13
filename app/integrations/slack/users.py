"""Slack User Modules.

This module contains the user related functionality for the Slack integration.
"""
import re
import logging

SLACK_USER_ID_REGEX = r"^[A-Z0-9]+$"


def get_user_id_from_request(body):
    """
    Returns the user_id from the body of a request, otherwise None.
      Supports the following formats:
    - user_id (Slack slash command)
    - user (Slack Message, Modal, Block)
    - event.user (Slack Event)
    """
    user_id = None
    if "user_id" in body:
        user_id = body["user_id"]
    elif "user" in body:
        if isinstance(body["user"], dict) and "id" in body["user"]:
            user_id = body["user"]["id"]
        else:
            user_id = body["user"]
    elif (
        "event" in body and isinstance(body["event"], dict) and "user" in body["event"]
    ):
        user_id = body["event"]["user"]
    if user_id:
        match = re.match(SLACK_USER_ID_REGEX, user_id)
        if match:
            return match.group(0)


def get_user_locale(client, user_id=None):
    """
    Returns the user locale from a command's user_id if valid, "en-US" as default otherwise
    """
    default_locale = "en-US"
    supported_locales = ["en-US", "fr-FR"]
    if user_id is None:
        return default_locale
    user_locale = client.users_info(user=user_id, include_locale=True)
    if user_locale["ok"] and (user_locale["user"]["locale"] in supported_locales):
        return user_locale["user"]["locale"]
    return default_locale


def replace_user_id_with_handle(user_handle, message):
    """Function to replace the user id with the user handle in a message:w"""
    if not user_handle or not message:
        logging.error("User handle or message is empty or None")
        return None

    user_id_pattern = r"<@\w+>"
    if re.search(user_id_pattern, message):
        message = re.sub(user_id_pattern, user_handle, message)
    return message
