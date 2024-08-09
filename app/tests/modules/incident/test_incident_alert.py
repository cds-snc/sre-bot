from unittest.mock import MagicMock, patch
from modules.incident import incident_alert


@patch("modules.incident.incident_alert.incident")
def test_handle_incident_action_buttons_call_incident(incident_mock):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "call-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "user": {"id": "user_id"},
    }
    incident_alert.handle_incident_action_buttons(client, ack, body, logger)
    incident_mock.open_modal.assert_called_with(
        client, ack, {"text": "incident_id"}, body
    )


@patch("modules.incident.incident_alert.webhooks.increment_acknowledged_count")
@patch("modules.incident.incident_alert.incident")
def test_handle_incident_action_buttons_ignore(
    incident_mock, increment_acknowledged_count_mock
):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                }
            ],
        },
    }
    incident_alert.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                }
            ],
        },
    )


@patch("modules.incident.incident_alert.webhooks.increment_acknowledged_count")
@patch("modules.incident.incident_alert.incident")
def test_handle_incident_action_buttons_ignore_drop_richtext_block(
    incident_mock,
    increment_acknowledged_count_mock,
):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                }
            ],
            "blocks": [
                {
                    "type": "rich_text",
                    "block_id": "6Qv",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "AWS notification"}],
                        }
                    ],
                }
            ],
        },
    }
    incident_alert.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                }
            ],
            "blocks": [],
        },
    )


@patch("modules.incident.incident_alert.webhooks.increment_acknowledged_count")
@patch("modules.incident.incident_alert.incident")
def test_handle_incident_action_buttons_ignore_drop_richtext_block_no_type(
    incident_mock,
    increment_acknowledged_count_mock,
):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                }
            ],
            "blocks": [
                {
                    "foo": "rich_text",
                    "block_id": "6Qv",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "AWS notification"}],
                        }
                    ],
                }
            ],
        },
    }
    incident_alert.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                }
            ],
            "blocks": [
                {
                    "foo": "rich_text",
                    "block_id": "6Qv",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "AWS notification"}],
                        }
                    ],
                }
            ],
        },
    )


# Test that the order of the ignore buttons are appended properly and the preview is moved up once the ignore button is clicked


@patch("modules.incident.incident_alert.webhooks.increment_acknowledged_count")
@patch("modules.incident.incident_alert.incident")
def test_handle_incident_action_buttons_link_preview(
    incident_mock, increment_acknowledged_count_mock
):
    client = MagicMock()
    ack = MagicMock()
    logger = MagicMock()
    body = {
        "actions": [
            {
                "name": "ignore-incident",
                "value": "incident_id",
                "type": "button",
            }
        ],
        "channel": {"id": "channel_id"},
        "user": {"id": "user_id"},
        "original_message": {
            "attachments": [
                {
                    "color": "3AA3E3",
                    "fallback": "foo",
                    "text": "bar",
                },
                {
                    "text": "test",
                    "title": "title",
                    "app_unfurl_url": "http://blah.com",
                    "thumb_url": "http://blah.com/g/200/200",
                    "image_url": "http://blah.com/g/200/200",
                },
            ],
        },
    }
    incident_alert.handle_incident_action_buttons(client, ack, body, logger)
    increment_acknowledged_count_mock.assert_called_with("incident_id")
    client.api_call.assert_called_with(
        "chat.update",
        json={
            "channel": "channel_id",
            "attachments": [
                {
                    "text": "test",
                    "title": "title",
                    "app_unfurl_url": "http://blah.com",
                    "thumb_url": "http://blah.com/g/200/200",
                    "image_url": "http://blah.com/g/200/200",
                },
                {
                    "color": "3AA3E3",
                    "fallback": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                    "text": "🙈  <@user_id> has acknowledged and ignored the incident.\n<@user_id> a pris connaissance et ignoré l'incident.",
                },
            ],
        },
    )
