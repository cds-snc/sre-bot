from unittest.mock import patch

from models.webhooks import WebhookPayload
from modules.webhooks.slack import (
    hydrate_ip_addresses,
    link_ip_addresses_to_geolocate,
    map_emails_to_slack_users,
)


@patch("modules.webhooks.slack.replace_users_emails_with_mention")
def test_map_emails_to_slack_users_text_only(mock_replace_users_emails_with_mention):
    payload = WebhookPayload(text="hello user@example.com", blocks=None)
    mock_replace_users_emails_with_mention.return_value = "hello <@U12345>"
    result = map_emails_to_slack_users(payload)
    assert result.text == "hello <@U12345>"
    mock_replace_users_emails_with_mention.assert_called_once_with(
        "hello user@example.com"
    )


@patch("modules.webhooks.slack.replace_users_emails_in_dict")
def test_map_emails_to_slack_users_blocks_only(mock_replace_users_emails_in_dict):
    blocks = [{"type": "section", "text": "user@example.com"}]
    payload = WebhookPayload(text=None, blocks=blocks)
    mock_replace_users_emails_in_dict.return_value = [
        {"type": "section", "text": "<@U12345>"}
    ]
    result = map_emails_to_slack_users(payload)
    assert result.blocks == [{"type": "section", "text": "<@U12345>"}]
    mock_replace_users_emails_in_dict.assert_called_once_with(blocks)


@patch("modules.webhooks.slack.replace_users_emails_in_dict")
@patch("modules.webhooks.slack.replace_users_emails_with_mention")
def test_map_emails_to_slack_users_text_and_blocks(
    mock_replace_users_emails_with_mention, mock_replace_users_emails_in_dict
):
    blocks = [{"type": "section", "text": "user@example.com"}]
    payload = WebhookPayload(text="hello user@example.com", blocks=blocks)
    mock_replace_users_emails_with_mention.return_value = "hello <@U12345>"
    mock_replace_users_emails_in_dict.return_value = [
        {"type": "section", "text": "<@U12345>"}
    ]
    result = map_emails_to_slack_users(payload)
    assert result.text == "hello <@U12345>"
    assert result.blocks == [{"type": "section", "text": "<@U12345>"}]
    mock_replace_users_emails_with_mention.assert_called_once_with(
        "hello user@example.com"
    )
    mock_replace_users_emails_in_dict.assert_called_once_with(blocks)


def test_map_emails_to_slack_users_no_text_no_blocks():
    payload = WebhookPayload(text=None, blocks=None)
    result = map_emails_to_slack_users(payload)
    assert result.text is None
    assert result.blocks is None


@patch("modules.webhooks.slack.replace_users_emails_in_dict")
@patch("modules.webhooks.slack.replace_users_emails_with_mention")
def test_map_emails_to_slack_users_empty_text_and_blocks(
    mock_replace_users_emails_with_mention, mock_replace_users_emails_in_dict
):
    payload = WebhookPayload(text="", blocks=[])
    mock_replace_users_emails_with_mention.return_value = ""
    mock_replace_users_emails_in_dict.return_value = []
    result = map_emails_to_slack_users(payload)
    assert result.text == ""
    assert not result.blocks
    mock_replace_users_emails_with_mention.assert_not_called()
    mock_replace_users_emails_in_dict.assert_not_called()


def test_link_ip_addresses_to_geolocate():
    result = link_ip_addresses_to_geolocate(
        "source 8.8.8.8 hit 1.1.1.1",
        base_url="https://sre-bot.example.com/",
    )

    assert (
        result
        == "source <https://sre-bot.example.com/geolocate/8.8.8.8|8.8.8.8> hit <https://sre-bot.example.com/geolocate/1.1.1.1|1.1.1.1>"
    )


def test_link_ip_addresses_to_geolocate_ignores_invalid_ip_and_urls():
    result = link_ip_addresses_to_geolocate(
        "invalid 999.999.999.999 url https://8.8.8.8/path",
        base_url="https://sre-bot.example.com",
    )

    assert result == "invalid 999.999.999.999 url https://8.8.8.8/path"


def test_link_ip_addresses_to_geolocate_ignores_existing_slack_links():
    result = link_ip_addresses_to_geolocate(
        "already <https://example.com|8.8.8.8>",
        base_url="https://sre-bot.example.com",
    )

    assert result == "already <https://example.com|8.8.8.8>"


def test_link_ip_addresses_to_geolocate_supports_ipv6():
    result = link_ip_addresses_to_geolocate(
        "resolver 2001:4860:4860::8888",
        base_url="https://sre-bot.example.com",
    )

    assert (
        result
        == "resolver <https://sre-bot.example.com/geolocate/2001%3A4860%3A4860%3A%3A8888|2001:4860:4860::8888>"
    )


def test_hydrate_ip_addresses_links_text_and_block_strings():
    payload = WebhookPayload(
        text="source 8.8.8.8",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "destination 1.1.1.1"},
            }
        ],
    )

    with patch("modules.webhooks.slack.get_settings") as mock_get_settings:
        mock_get_settings.return_value.server.BACKEND_URL = (
            "https://sre-bot.example.com"
        )
        result = hydrate_ip_addresses(payload)

    assert (
        result.text == "source <https://sre-bot.example.com/geolocate/8.8.8.8|8.8.8.8>"
    )
    assert result.blocks == [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "destination <https://sre-bot.example.com/geolocate/1.1.1.1|1.1.1.1>",
            },
        }
    ]
