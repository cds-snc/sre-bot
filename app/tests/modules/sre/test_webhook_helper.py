from unittest.mock import MagicMock, patch
from modules import webhook_helper


def test_ack_action():
    ack = MagicMock()
    webhook_helper.ack_action(ack)
    ack.assert_called_once()


@patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
@patch("modules.sre.webhook_helper.webhooks.lookup_webhooks")
def test_handle_webhooks_command_with_empty_args_and_webhooks(
    mock_lookup_webhooks, mock_list_all_webhooks_view
):
    respond = MagicMock()
    client = MagicMock()
    hooks = [
        {"id": "1", "name": "hook1", "channel": "channel_id"},
        {"id": "2", "name": "hook2", "channel": "channel_id"},
    ]
    mock_lookup_webhooks.return_value = hooks
    body = {"channel_id": "channel_id"}
    webhook_helper.handle_webhook_command([], client, body, respond)
    respond.assert_not_called()
    mock_list_all_webhooks_view.assert_called_with(
        client,
        body,
        0,
        webhook_helper.MAX_BLOCK_SIZE,
        "all",
        hooks,
        channel="channel_id",
    )


@patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
@patch("modules.sre.webhook_helper.webhooks.lookup_webhooks")
def test_handle_webhooks_command_with_empty_args_no_webhooks(
    mock_lookup_webhooks, mock_list_all_webhooks_view: MagicMock
):
    respond = MagicMock()
    client = MagicMock()
    hooks = []
    mock_lookup_webhooks.return_value = hooks
    body = {"channel_id": "channel_id"}
    webhook_helper.handle_webhook_command([], client, body, respond)
    respond.assert_called_once_with(
        "No webhooks found for this channel. Type `/sre webhooks help` to see a list of commands."
    )
    mock_list_all_webhooks_view.assert_not_called()


@patch("modules.sre.webhook_helper.webhooks_create.create_webhook_modal")
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


@patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
@patch("modules.sre.webhook_helper.webhooks.list_all_webhooks")
def test_handle_webhooks_command_with_list_command(
    list_all_webhooks_mock, list_all_webhooks_view_mock
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    all_hooks = [
        {"id": "1", "name": "hook1", "channel": "channel1"},
        {"id": "2", "name": "hook2", "channel": "channel2"},
    ]
    list_all_webhooks_mock.return_value = all_hooks
    webhook_helper.handle_webhook_command(["list"], client, body, respond)
    list_all_webhooks_view_mock.assert_called_once_with(
        client, body, 0, webhook_helper.MAX_BLOCK_SIZE, "all", all_hooks
    )


@patch("modules.sre.webhook_helper.webhooks_list.list_all_webhooks")
@patch("modules.sre.webhook_helper.webhooks.list_all_webhooks")
def test_handle_webhooks_command_with_list_command_no_webhooks(
    list_all_webhooks_mock, list_all_webhooks_view
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    all_hooks = []
    list_all_webhooks_mock.return_value = all_hooks
    webhook_helper.handle_webhook_command(["list"], client, body, respond)
    list_all_webhooks_view.assert_not_called()
    respond.assert_called_once_with("No webhooks found.")


def test_handle_webhooks_command_with_unkown_command():
    respond = MagicMock()
    webhook_helper.handle_webhook_command(
        ["unknown"], MagicMock(), MagicMock(), respond
    )
    respond.assert_called_once_with(
        "Unknown command: `unknown`. Type `/sre webhooks help` to see a list of commands.\nCommande inconnue: `unknown`. Tapez `/sre webhooks help` pour voir une liste de commandes."
    )
