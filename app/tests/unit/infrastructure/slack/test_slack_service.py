"""Unit tests for standalone SlackBot infrastructure service."""

from unittest.mock import MagicMock

import pytest

from infrastructure.configuration.integrations.slack import SlackSettings
from infrastructure.platforms.clients.slack import SlackClientFacade
from infrastructure.platforms.service import PlatformService
from integrations.slack.service import SlackBot, get_slack_bot

pytestmark = pytest.mark.unit


def test_slack_service_constructs_with_settings_and_client() -> None:
    slack_settings = MagicMock(spec=SlackSettings)
    slack_settings.ENABLED = True
    slack_settings.SOCKET_MODE = True
    slack_settings.APP_TOKEN = "xapp-test"
    slack_settings.SLACK_TOKEN = "xoxb-test"
    slack_client = MagicMock(spec=SlackClientFacade)

    slack_bot = SlackBot(slack_settings=slack_settings, slack_client=slack_client)

    assert slack_bot is not None


def test_slack_service_is_not_platform_service() -> None:
    assert not issubclass(SlackBot, PlatformService)


def test_get_slack_bot_singleton() -> None:
    get_slack_bot.cache_clear()
    first = get_slack_bot()
    second = get_slack_bot()

    assert first is second

    get_slack_bot.cache_clear()


def test_slack_service_exposes_registration_methods() -> None:
    assert hasattr(SlackBot, "register_command")
    assert hasattr(SlackBot, "register_view_handler")
    assert hasattr(SlackBot, "register_action_handler")
