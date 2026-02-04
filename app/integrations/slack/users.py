"""Slack User Modules.

This module contains the user related functionality for the Slack integration.
"""

import re
import structlog
from slack_sdk import WebClient
from integrations.slack.client import SlackClientManager

SLACK_USER_ID_REGEX = r"^[A-Z0-9]+$"

logger = structlog.get_logger()


def get_all_users(client: WebClient, deleted=False, is_bot=False):
    """Get all users from the Slack workspace.

    Args:
        client (WebClient): The Slack client instance.
        deleted (bool, optional): Include deleted users. Defaults to False.
        is_bot (bool, optional): Include bot users. Defaults to False.

    Returns:
        list: A list of active users.
    """
    log = logger.bind(deleted=deleted, is_bot=is_bot)

    users_list = []
    cursor = None
    try:
        while True:
            response = client.users_list(cursor=cursor, limit=200)
            if response["ok"]:
                if "members" in response:
                    users_list.extend(response["members"])
                cursor = response["response_metadata"]["next_cursor"]
                if not cursor:
                    break
            else:
                log.error("get_all_users_failed", response=response)
                break
    except Exception as e:
        log.error("get_all_users_failed", error=str(e))

    # filters
    if not deleted:
        users_list = [user for user in users_list if not user["deleted"]]
    if not is_bot:
        users_list = [user for user in users_list if not user["is_bot"]]

    return users_list


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


def get_user_email_from_body(client: WebClient, body):
    """
    Returns the user email from the body of a request, otherwise None.
      Supports the following formats:
    - user_id (Slack slash command)
    - user (Slack Message, Modal, Block)
    - event.user (Slack Event)
    """
    user_id = get_user_id_from_request(body)
    if user_id:
        user_info = client.users_info(user=user_id)
        if user_info["ok"]:
            return user_info["user"]["profile"]["email"]


def get_user_email_from_handle(client: WebClient, user_handle: str) -> str | None:
    """
    Returns the user email from a user handle, otherwise None.

    Args:
        client (WebClient): The Slack client instance.
        user_handle (str): The user handle.

    Returns:
        str | None: The user email or None.
    """
    log = logger.bind(user_handle=user_handle)
    user_handle = user_handle.lstrip("@")
    log.debug("resolving_user_email_from_handle", user_handle=user_handle)
    users_list = get_all_users(client)
    for member in users_list:
        if "name" in member and member["name"] == user_handle:
            user_id = member["id"]

            user_info = client.users_info(user=user_id)

            if user_info["ok"]:
                return user_info["user"]["profile"]["email"]
    return None


def get_user_email_from_id(client: WebClient, user_id: str) -> str | None:
    """
    Returns the user email from a Slack user ID, otherwise None.

    Handles escaped user mentions from Slack's "Escape channels, users, and links" feature.
    When escape is enabled, Slack sends mentions as <@USER_ID> format.

    Args:
        client (WebClient): The Slack client instance.
        user_id (str): The Slack user ID (e.g., U012ABCDEF or from <@U012ABCDEF>).

    Returns:
        str | None: The user email or None if not found or error occurs.
    """
    log = logger.bind(user_id=user_id)
    try:
        user_info = client.users_info(user=user_id)
        if user_info.get("ok"):
            user: dict = user_info.get("user", {})  # type: ignore
            profile: dict = user.get("profile", {}) if isinstance(user, dict) else {}  # type: ignore
            email = profile.get("email") if isinstance(profile, dict) else None
            if email:
                log.debug(
                    "resolved_user_email_from_id",
                    user_id=user_id,
                    email=email,
                )
                return email
        else:
            log.warning(
                "get_user_email_from_id_failed",
                user_id=user_id,
                error=user_info.get("error", "unknown"),
            )
    except Exception as e:  # pylint: disable=broad-except
        log.warning(
            "get_user_email_from_id_exception",
            user_id=user_id,
            error=str(e),
        )
    return None


def get_user_locale(client: WebClient, user_id=None):
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


def replace_user_id_with_handle(client, message):
    """Function to replace the user id with the user handle in a message."""
    user_id_pattern = r"<@(\w+)>"

    # Callback function to process each match
    def replace_with_handle(match):
        user_id = match.group(1)  # Extract the actual user ID without <@ and >
        # Fetch user details using the provided client; adjust this to fit your actual method
        user = client.users_profile_get(user=user_id)
        user_handle = "@" + user["profile"]["display_name"]  # Construct user handle
        return user_handle  # Return the user handle to replace the original match

    # Use re.sub() with the callback function to replace all matches
    updated_message = re.sub(user_id_pattern, replace_with_handle, message)
    return updated_message


def replace_users_emails_with_mention(text: str) -> str:
    """Replace email addresses in the given text with Slack user mentions when resolvable.

    Args:
        text (str): The input text potentially containing email addresses.
    Returns:
        str: The modified text with email addresses replaced by Slack user mentions.
    """
    log = logger.bind(component="replace_users_emails_with_mention")

    client = SlackClientManager.get_client()
    if not client:
        return text
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    matches = re.findall(email_pattern, text)
    for email in matches:
        try:
            response = client.users_lookupByEmail(email=email)
        # It's okay to catch all exceptions here since we don't want to fail the entire
        # operation if one email lookup fails.
        except Exception as e:  # pylint: disable=broad-except
            log.info("replace_users_emails_with_mention_failed", error=str(e))
            response = None
        if response:
            user: dict = response.get("user", {})
            user_handle = user.get("id")
            if user_handle:
                text = text.replace(email, f"<@{user_handle}>")
    return text


def replace_users_emails_in_dict(data):
    """Recursively replace email addresses in all string values within a nested dictionary or list.

    Args:
        data (dict or list): The input data structure potentially containing email addresses.
    Returns:
        dict or list: The modified data structure with email addresses replaced by Slack user mentions.
    """
    if isinstance(data, dict):
        return {k: replace_users_emails_in_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_users_emails_in_dict(item) for item in data]
    elif isinstance(data, str):
        return replace_users_emails_with_mention(data)
    else:
        return data
