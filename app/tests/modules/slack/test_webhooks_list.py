import json
from unittest.mock import MagicMock, call, patch, ANY
from modules.slack import webhooks_list


@patch("modules.slack.webhooks_list.webhook_list_item")
def test_get_webhooks_active(mock_webhook_list_item: MagicMock):
    mock_webhook_list_item.side_effect = lambda x: x
    all_hooks = [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
        helper_generate_webhook("name3", "channel3", "id3", active=False),
    ]

    assert webhooks_list.get_webhooks(all_hooks, "active") == [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
    ]
    assert mock_webhook_list_item.call_args_list == [
        call(helper_generate_webhook("name1", "channel1", "id1")),
        call(helper_generate_webhook("name2", "channel2", "id2")),
    ]


@patch("modules.slack.webhooks_list.webhook_list_item")
def test_get_webhooks_disabled(mock_webhook_list_item):
    mock_webhook_list_item.side_effect = lambda x: x
    all_hooks = [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
        helper_generate_webhook("name3", "channel3", "id3", active=False),
    ]

    assert webhooks_list.get_webhooks(all_hooks, "disabled") == [
        helper_generate_webhook("name3", "channel3", "id3", active=False)
    ]
    assert mock_webhook_list_item.call_args_list == [
        call(helper_generate_webhook("name3", "channel3", "id3", active=False))
    ]


def test_get_webhooks_not_recognized_value():
    all_hooks = []
    assert webhooks_list.get_webhooks(all_hooks, "test") == []


@patch("modules.slack.webhooks_list.get_webhooks_list")
def test_get_webhooks_list_all(get_webhooks_list_mock):
    expected_webhooks_list = helper_generate_webhook("name1", "channel1", "id1")
    get_webhooks_list_mock.return_value = [expected_webhooks_list]
    assert (
        webhooks_list.get_webhooks_list([expected_webhooks_list])
        == get_webhooks_list_mock.return_value
    )


@patch("modules.slack.webhooks_list.get_webhooks_button_block")
def test_get_button_block_active(get_webhooks_button_block_mock):
    expected_webhooks_list = helper_generate_webhook("name1", "channel1", "id1")
    get_webhooks_button_block_mock.return_value = [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ("Next page"),
                        "emoji": True,
                    },
                    "value": "0,active",
                    "action_id": "next_page",
                }
            ],
        }
    ]
    assert (
        webhooks_list.get_webhooks_button_block("active", [expected_webhooks_list], 0)
        == get_webhooks_button_block_mock.return_value
    )


@patch("modules.slack.webhooks_list.get_webhooks_button_block")
def test_get_button_block_disabled(get_webhooks_button_block_mock):
    expected_webhooks_list = helper_generate_webhook("name1", "channel1", "id1")
    get_webhooks_button_block_mock.return_value = [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ("Next page"),
                        "emoji": True,
                    },
                    "value": "0,active",
                    "action_id": "next_page",
                }
            ],
        }
    ]
    assert (
        webhooks_list.get_webhooks_button_block("disabled", [expected_webhooks_list], 0)
        == get_webhooks_button_block_mock.return_value
    )


@patch("modules.slack.webhooks_list.get_webhooks_button_block")
def test_get_button_block_active_last_page(get_webhooks_button_block_mock):
    expected_webhooks_list = helper_generate_webhook("name1", "channel1", "id1")
    get_webhooks_button_block_mock.return_value = [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ("First page"),
                        "emoji": True,
                    },
                    "value": "4,active",
                    "action_id": "next_page",
                }
            ],
        }
    ]
    assert (
        webhooks_list.get_webhooks_button_block("active", [expected_webhooks_list], 4)
        == get_webhooks_button_block_mock.return_value
    )


@patch("modules.slack.webhooks_list.get_webhooks_button_block")
def test_get_button_block_empty(get_webhooks_button_block_mock):
    get_webhooks_button_block_mock.return_value = []
    expected_webhooks_list = []
    assert (
        webhooks_list.get_webhooks_button_block("active", [expected_webhooks_list], 0)
        == get_webhooks_button_block_mock.return_value
    )


def test_list_all_webhooks():
    all_hooks = [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
    ]
    client = MagicMock()
    body = {"trigger_id": "trigger_id"}
    webhooks_list.list_all_webhooks(
        client, body, 0, webhooks_list.MAX_BLOCK_SIZE, "all", all_hooks
    )
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view={
            "type": "modal",
            "callback_id": "webhooks_view",
            "title": {"type": "plain_text", "text": "SRE - Listing webhooks"},
            "close": {"type": "plain_text", "text": "Close"},
            "private_metadata": json.dumps(
                {
                    "start": 0,
                    "end": 16,
                    "type": "all",
                    "channel": None,
                    "channel_name": None,
                }
            ),
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "There are currently 2 enabled webhooks",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "name1"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reveal", "emoji": True},
                        "style": "primary",
                        "value": "id1",
                        "action_id": "reveal_webhook",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "<#channel1>"},
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Disable",
                            "emoji": True,
                        },
                        "style": "danger",
                        "value": "id1",
                        "action_id": "toggle_webhook",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "2020-01-01T00:00:00.000Z | Type: Alert\n 0 invocations | 0 acknowledged",
                        }
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "name2"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reveal", "emoji": True},
                        "style": "primary",
                        "value": "id2",
                        "action_id": "reveal_webhook",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "<#channel2>"},
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Disable",
                            "emoji": True,
                        },
                        "style": "danger",
                        "value": "id2",
                        "action_id": "toggle_webhook",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "2020-01-01T00:00:00.000Z | Type: Alert\n 0 invocations | 0 acknowledged",
                        }
                    ],
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "First page",
                                "emoji": True,
                            },
                            "value": "16,active",
                            "action_id": "next_page",
                        }
                    ],
                },
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "There are currently 0 disabled webhooks",
                    },
                },
                {"type": "divider"},
            ],
        },
    )


def test_list_all_webhooks_empty():
    all_hooks = []

    client = MagicMock()
    body = {"trigger_id": "trigger_id"}
    webhooks_list.list_all_webhooks(
        client, body, 0, webhooks_list.MAX_BLOCK_SIZE, "all", all_hooks
    )
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view={
            "type": "modal",
            "callback_id": "webhooks_view",
            "title": {"type": "plain_text", "text": "SRE - Listing webhooks"},
            "close": {"type": "plain_text", "text": "Close"},
            "private_metadata": json.dumps(
                {
                    "start": 0,
                    "end": 16,
                    "type": "all",
                    "channel": None,
                    "channel_name": None,
                }
            ),
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "There are currently 0 enabled webhooks",
                    },
                },
                {"type": "divider"},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "There are currently 0 disabled webhooks",
                    },
                },
                {"type": "divider"},
            ],
        },
    )


def test_list_all_webhooks_update():
    all_hooks = [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
    ]
    client = MagicMock()
    private_metadata = {"channel": None}
    body = {"view": {"id": "id", "private_metadata": json.dumps(private_metadata)}}
    webhooks_list.list_all_webhooks(
        client, body, 0, webhooks_list.MAX_BLOCK_SIZE, "all", all_hooks, update=True
    )
    client.views_update.assert_called_with(view_id="id", view=ANY)


@patch("modules.slack.webhooks_list.logger")
@patch("modules.slack.webhooks_list.webhooks.get_webhook")
def test_reveal_webhook(get_webhook_mock, mock_logger):
    get_webhook_mock.return_value = helper_generate_webhook("name", "channel", "id")
    ack = MagicMock()
    client = MagicMock()
    body = {
        "actions": [{"value": "id"}],
        "user": {"username": "username"},
        "view": {"id": "id"},
        "trigger_id": "trigger_id",
    }
    webhooks_list.reveal_webhook(ack, body, client)
    ack.assert_called()
    mock_logger.info.assert_called_with(
        "reveal_webhook_called",
        user_name="username",
        webhook_id="id",
    )
    client.views_push.assert_called()


@patch("modules.slack.webhooks_list.logger")
@patch("modules.slack.webhooks_list.list_all_webhooks")
@patch("modules.slack.webhooks_list.webhooks.list_all_webhooks")
@patch("modules.slack.webhooks_list.webhooks.lookup_webhooks")
@patch("modules.slack.webhooks_list.webhooks.toggle_webhook")
@patch("modules.slack.webhooks_list.webhooks.get_webhook")
def test_toggle_webhook(
    get_webhook_mock,
    toggle_webhook_mock,
    lookup_webhooks_mock,
    list_all_webhooks_mock,
    list_all_webhooks_view_mock,
    logger_mock,
):
    get_webhook_mock.return_value = helper_generate_webhook("name", "channel", "id")
    ack = MagicMock()
    client = MagicMock()
    private_metadata = {"channel": None}
    body = {
        "actions": [{"value": "id"}],
        "user": {"id": "user_id", "username": "username"},
        "view": {"id": "id", "private_metadata": json.dumps(private_metadata)},
    }
    all_hooks = ["hook1", "hook2"]
    list_all_webhooks_mock.return_value = all_hooks
    webhooks_list.toggle_webhook(ack, body, client)
    ack.assert_called()
    toggle_webhook_mock.assert_called_with("id")
    logger_mock.info.assert_called_with(
        "toggle_webhook_called",
        user_name="username",
        webhook_id="id",
        channel="channel",
    )
    client.chat_postMessage.assert_called_with(
        channel="channel",
        user="user_id",
        text="Webhook name has been disabled by <@username>",
    )
    list_all_webhooks_mock.assert_called()
    lookup_webhooks_mock.assert_not_called()
    list_all_webhooks_view_mock.assert_called_with(
        client,
        body,
        0,
        webhooks_list.MAX_BLOCK_SIZE,
        "all",
        all_hooks,
        None,
        update=True,
    )


@patch("modules.slack.webhooks_list.logger")
@patch("modules.slack.webhooks_list.list_all_webhooks")
@patch("modules.slack.webhooks_list.webhooks.list_all_webhooks")
@patch("modules.slack.webhooks_list.webhooks.lookup_webhooks")
@patch("modules.slack.webhooks_list.webhooks.toggle_webhook")
@patch("modules.slack.webhooks_list.webhooks.get_webhook")
def test_toggle_webhook_with_channel(
    get_webhook_mock,
    toggle_webhook_mock,
    lookup_webhooks_mock,
    list_all_webhooks_mock,
    list_all_webhooks_view_mock,
    logger_mock,
):
    get_webhook_mock.return_value = helper_generate_webhook("name", "channel", "id")
    ack = MagicMock()
    client = MagicMock()
    private_metadata = {"channel": "channel_id"}
    body = {
        "actions": [{"value": "id"}],
        "user": {"id": "user_id", "username": "username"},
        "view": {"id": "id", "private_metadata": json.dumps(private_metadata)},
    }
    all_hooks = ["hook1", "hook2"]
    lookup_webhooks_mock.return_value = all_hooks
    webhooks_list.toggle_webhook(ack, body, client)
    ack.assert_called()
    toggle_webhook_mock.assert_called_with("id")
    logger_mock.info.assert_called_with(
        "toggle_webhook_called",
        user_name="username",
        webhook_id="id",
        channel="channel",
    )
    client.chat_postMessage.assert_called_with(
        channel="channel",
        user="user_id",
        text="Webhook name has been disabled by <@username>",
    )
    list_all_webhooks_mock.assert_not_called()
    lookup_webhooks_mock.assert_called_with("channel", "channel_id")
    list_all_webhooks_view_mock.assert_called_with(
        client,
        body,
        0,
        webhooks_list.MAX_BLOCK_SIZE,
        "all",
        all_hooks,
        "channel_id",
        update=True,
    )


@patch("modules.slack.webhooks_list.list_all_webhooks")
@patch("modules.slack.webhooks_list.webhooks.list_all_webhooks")
def test_button_next_page(list_all_webhooks_mock, mock_list_all_webhooks_view):
    client = MagicMock()
    ack = MagicMock()
    private_metadata = {"channel": None}
    body = {
        "actions": [
            {
                "action_id": "next_page",
                "block_id": "zBh",
                "text": {"type": "plain_text", "text": "Next page", "emoji": True},
                "value": "5,active",
                "type": "button",
                "action_ts": "1687986765.093236",
            }
        ],
        "user": {"id": "user_id", "username": "username"},
        "view": {"id": "id", "private_metadata": json.dumps(private_metadata)},
    }
    webhooks_list.next_page(ack, body, client)
    ack.assert_called()
    list_all_webhooks_mock.assert_called()
    mock_list_all_webhooks_view.assert_called()


@patch("modules.slack.webhooks_list.list_all_webhooks")
@patch("modules.slack.webhooks_list.webhooks.lookup_webhooks")
def test_button_next_page_with_channel(
    mock_lookup_webhooks, mock_list_all_webhooks_view
):
    client = MagicMock()
    ack = MagicMock()
    private_metadata = {"channel": "channel_id"}
    body = {
        "actions": [
            {
                "action_id": "next_page",
                "block_id": "zBh",
                "text": {"type": "plain_text", "text": "Next page", "emoji": True},
                "value": "5,active",
                "type": "button",
                "action_ts": "1687986765.093236",
            }
        ],
        "user": {"id": "user_id", "username": "username"},
        "view": {"id": "id", "private_metadata": json.dumps(private_metadata)},
    }
    webhooks_list.next_page(ack, body, client)
    ack.assert_called()
    mock_lookup_webhooks.assert_called_with("channel", "channel_id")
    mock_list_all_webhooks_view.assert_called()


def test_webhook_list_item():
    hook = helper_generate_webhook("name", "channel", "id")
    assert webhooks_list.webhook_list_item(hook) == [
        {
            "accessory": {
                "action_id": "reveal_webhook",
                "style": "primary",
                "text": {"emoji": True, "text": "Reveal", "type": "plain_text"},
                "type": "button",
                "value": "id",
            },
            "text": {"text": "name", "type": "mrkdwn"},
            "type": "section",
        },
        {
            "accessory": {
                "action_id": "toggle_webhook",
                "style": "danger",
                "text": {"emoji": True, "text": "Disable", "type": "plain_text"},
                "type": "button",
                "value": "id",
            },
            "text": {"text": "<#channel>", "type": "mrkdwn"},
            "type": "section",
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "emoji": True,
                    "text": "2020-01-01T00:00:00.000Z | Type: Alert\n 0 invocations | 0 acknowledged",
                }
            ],
        },
        {"type": "divider"},
    ]


def helper_generate_view(name="name"):
    return {
        "state": {
            "values": {
                "name": {"name": {"value": name}},
                "channel": {"channel": {"selected_channel": "channel"}},
                "hook_type": {"hook_type": {"selected_option": {"value": "Alert"}}},
            }
        }
    }


def helper_generate_webhook(name="name", channel="channel", id="id", active=True):
    return {
        "name": {"S": name},
        "channel": {"S": channel},
        "id": {"S": id},
        "active": {"BOOL": active},
        "created_at": {"S": "2020-01-01T00:00:00.000Z"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
    }
