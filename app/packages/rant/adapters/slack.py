"""Slack adapter — implements ``UserIdentityLookup`` on the Slack Web API."""

from typing import Any

import structlog
from slack_sdk import WebClient

from integrations.slack.client import get_slack_web_client
from packages.rant.service import UserIdentity

logger = structlog.get_logger()


class SlackUserIdentityLookup:
    """Resolve a Slack user's display name and avatar through ``users.info``."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def lookup_user_identity(self, user_id: str) -> UserIdentity | None:
        """Return the user's name and avatar, or ``None`` when the profile is unusable.

        Web API errors propagate; the handler owns the fallback to posting as the bot.
        """
        log = logger.bind(user_id=user_id)
        response = self._client.users_info(user=user_id)

        if not response.get("ok"):
            log.warning("rant_user_identity_lookup_not_ok", error=response.get("error"))
            return None

        user: dict[str, Any] = response.get("user") or {}
        profile: dict[str, Any] = user.get("profile") or {}
        display_name = profile.get("display_name") or profile.get("real_name")
        icon_url = profile.get("image_512") or profile.get("image_192") or profile.get("image_72")

        if not display_name or not icon_url:
            log.warning("rant_user_identity_incomplete")
            return None

        return UserIdentity(display_name=display_name, icon_url=icon_url)


def build_user_identity_lookup() -> SlackUserIdentityLookup:
    """Build the lookup on the bot's Web client."""
    return SlackUserIdentityLookup(get_slack_web_client())
