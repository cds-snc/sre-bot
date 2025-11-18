from unittest.mock import patch

from models.webhooks import WebhookPayload
from modules.webhooks.slack import map_emails_to_slack_users


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
