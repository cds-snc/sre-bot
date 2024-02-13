"""Slack User Modules.

This module contains the user related functionality for the Slack integration.
"""


def get_user_locale(user_id, client):
    """
    Returns the user locale from a command's user_id if valid, "en-US" as default otherwise
    """
    default_locale = "en-US"
    supported_locales = ["en-US", "fr-FR"]
    user_locale = client.users_info(user=user_id, include_locale=True)
    if user_locale["ok"] and (user_locale["user"]["locale"] in supported_locales):
        return user_locale["user"]["locale"]
    return default_locale
