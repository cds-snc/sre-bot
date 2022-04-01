from commands.helpers import webhook_helper


from unittest.mock import ANY, MagicMock, patch


def test_handle_webhooks_command_with_empty_args():
    respond = MagicMock()
    webhook_helper.handle_webhook_command([], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(webhook_helper.help_text)


@patch("commands.helpers.webhook_helper.create_webhook_modal")
def test_handle_webhooks_command_with_create_command(create_webhook_modal_mock):
    client = MagicMock()
    body = MagicMock()
    webhook_helper.handle_webhook_command(
        ["create"],
        client,
        body,
        MagicMock(),
    )

    create_webhook_modal_mock.assert_called_with(client, body)


def test_handle_webhooks_command_with_help():
    respond = MagicMock()
    webhook_helper.handle_webhook_command(["help"], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(webhook_helper.help_text)


@patch("commands.helpers.webhook_helper.list_all_webhooks")
def test_handle_webhooks_command_with_list_command(list_all_webhooks_mock):
    client = MagicMock()
    body = MagicMock()
    webhook_helper.handle_webhook_command(["list"], client, body, MagicMock())
    list_all_webhooks_mock.assert_called_with(client, body)


def test_handle_webhooks_command_with_unkown_command():
    respond = MagicMock()
    webhook_helper.handle_webhook_command(
        ["unknown"], MagicMock(), MagicMock(), respond
    )
    respond.assert_called_once_with(
        "Unknown command: unknown. Type `/sre webhook help` to see a list of commands."
    )


def test_create_webhook_with_illegal_name():
    ack = MagicMock()
    view = helper_generate_view("!@#$%%^&*()_+-=[]{};':,./<>?\\|`~")
    webhook_helper.create_webhook(
        ack,
        view,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    ack.assert_any_call(
        response_action="errors",
        errors={"name": "Description must only contain number and letters"},
    )


def test_create_webhook_with_long_name():
    ack = MagicMock()
    view = helper_generate_view("a" * 81)
    webhook_helper.create_webhook(
        ack,
        view,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    ack.assert_any_call(
        response_action="errors",
        errors={"name": "Description must be less than 80 characters"},
    )


@patch("commands.helpers.webhook_helper.webhooks.create_webhook")
def test_create_webhook_with_existing_webhook(create_webhook_mock):
    create_webhook_mock.return_value = "id"
    ack = MagicMock()
    view = helper_generate_view("foo")
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    say = MagicMock()
    webhook_helper.create_webhook(
        ack,
        view,
        body,
        logger,
        client,
        say,
    )
    create_webhook_mock.assert_called_with(
        "channel",
        "user",
        "foo",
    )
    logger.info.assert_called_with(
        "Webhook created with url: https://sre-bot.cdssandbox.xyz/hook/id"
    )

    say.assert_called_with(
        channel="channel",
        text="<@user> created a new SRE-Bot webhook: foo",
    )

    client.chat_postEphemeral.assert_called_with(
        channel="channel",
        user="user",
        text="Webhook created with url: https://sre-bot.cdssandbox.xyz/hook/id",
    )


@patch("commands.helpers.webhook_helper.webhooks.create_webhook")
def test_create_webhook_with_creation_error(create_webhook_mock):
    create_webhook_mock.return_value = None
    ack = MagicMock()
    view = helper_generate_view("foo")
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    say = MagicMock()
    webhook_helper.create_webhook(
        ack,
        view,
        body,
        logger,
        client,
        say,
    )
    create_webhook_mock.assert_called_with(
        "channel",
        "user",
        "foo",
    )
    logger.error.assert_called_with("Error creating webhook: channel, user, foo")

    client.chat_postEphemeral.assert_called_with(
        channel="channel",
        user="user",
        text="Something went wrong creating the webhook",
    )


def test_create_webhook_modal():
    client = MagicMock()
    body = MagicMock()
    webhook_helper.create_webhook_modal(client, body)
    client.views_open.assert_called()


@patch("commands.helpers.webhook_helper.webhooks.list_all_webhooks")
def test_list_all_webhooks(list_all_webhooks_mock):
    list_all_webhooks_mock.return_value = [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
    ]
    client = MagicMock()
    body = {"trigger_id": "trigger_id"}
    webhook_helper.list_all_webhooks(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view={
            "type": "modal",
            "callback_id": "webhooks_view",
            "title": {"type": "plain_text", "text": "SRE - Listing webhooks"},
            "close": {"type": "plain_text", "text": "Close"},
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
                            "text": "2020-01-01T00:00:00.000Z \n 0 invocations | 0 acknowledged",
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
                            "text": "2020-01-01T00:00:00.000Z \n 0 invocations | 0 acknowledged",
                        }
                    ],
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


@patch("commands.helpers.webhook_helper.webhooks.list_all_webhooks")
def test_list_all_webhooks_update(list_all_webhooks_mock):
    list_all_webhooks_mock.return_value = [
        helper_generate_webhook("name1", "channel1", "id1"),
        helper_generate_webhook("name2", "channel2", "id2"),
    ]
    client = MagicMock()
    body = {"view": {"id": "id"}}
    webhook_helper.list_all_webhooks(client, body, update=True)
    client.views_update.assert_called_with(view_id="id", view=ANY)


@patch("commands.helpers.webhook_helper.webhooks.get_webhook")
def test_reveal_webhook(get_webhook_mock):
    get_webhook_mock.return_value = helper_generate_webhook("name", "channel", "id")
    ack = MagicMock()
    client = MagicMock()
    body = {
        "actions": [{"value": "id"}],
        "user": {"username": "username"},
        "view": {"id": "id"},
    }
    logger = MagicMock()
    webhook_helper.reveal_webhook(ack, body, logger, client)
    ack.assert_called()
    logger.info.assert_called_with(
        "username has requested to see the webhook with ID: id"
    )


@patch("commands.helpers.webhook_helper.webhooks.get_webhook")
@patch("commands.helpers.webhook_helper.webhooks.toggle_webhook")
@patch("commands.helpers.webhook_helper.list_all_webhooks")
def test_toggle_webhook(list_all_webhooks_mock, toggle_webhook_mock, get_webhook_mock):
    get_webhook_mock.return_value = helper_generate_webhook("name", "channel", "id")
    ack = MagicMock()
    client = MagicMock()
    body = {
        "actions": [{"value": "id"}],
        "user": {"id": "user_id", "username": "username"},
        "view": {"id": "id"},
    }
    logger = MagicMock()
    webhook_helper.toggle_webhook(ack, body, logger, client)
    ack.assert_called()
    toggle_webhook_mock.assert_called_with("id")
    logger.info.assert_called_with("Webhook name has been enabled by <@username>")
    client.chat_postMessage.assert_called_with(
        channel="channel",
        user="user_id",
        text="Webhook name has been enabled by <@username>",
    )
    list_all_webhooks_mock.assert_called_with(client, body, update=True)


def test_webhook_list_item():
    hook = helper_generate_webhook("name", "channel", "id")
    assert webhook_helper.webhook_list_item(hook) == [
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
                    "text": "2020-01-01T00:00:00.000Z \n 0 invocations | 0 acknowledged",
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
