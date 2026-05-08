"""Unit tests for standalone SlackBot infrastructure service."""

from unittest.mock import MagicMock

import pytest

from infrastructure.clients.slack import SlackSettings
from infrastructure.platforms.service import PlatformService
from infrastructure.slack.service import SlackBot

pytestmark = pytest.mark.unit


def test_slack_service_constructs_with_settings() -> None:
    slack_settings = MagicMock(spec=SlackSettings)
    slack_settings.ENABLED = True
    slack_settings.SOCKET_MODE = True
    slack_settings.APP_TOKEN = "xapp-test"
    slack_settings.effective_bot_token = "xoxb-test"

    slack_bot = SlackBot(settings=slack_settings)

    assert slack_bot is not None


def test_slack_service_is_not_platform_service() -> None:
    assert not issubclass(SlackBot, PlatformService)


def test_slack_service_exposes_registration_methods() -> None:
    assert hasattr(SlackBot, "register_command")
    assert hasattr(SlackBot, "register_view_handler")
    assert hasattr(SlackBot, "register_action_handler")
