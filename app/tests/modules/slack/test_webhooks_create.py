from unittest.mock import MagicMock, patch

from modules.slack import webhooks_create
from tests.modules.slack.test_webhooks_list import helper_generate_view


def test_create_webhook_modal():
    client = MagicMock()
    body = MagicMock()
    webhooks_create.create_webhook_modal(client, body)
    client.views_open.assert_called()


def test_create_webhook_with_illegal_name():
    ack = MagicMock()
    view = helper_generate_view("!@#$%%^&*()_+-=[]{};':,./<>?\\|`~")
    webhooks_create.handle_create_webhook_action(
        ack,
        view,
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
    webhooks_create.handle_create_webhook_action(
        ack,
        view,
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    ack.assert_any_call(
        response_action="errors",
        errors={"name": "Description must be less than 80 characters"},
    )


@patch("modules.slack.webhooks_create.logger")
@patch("modules.slack.webhooks_create.webhooks.create_webhook")
def test_create_webhook_with_existing_webhook(create_webhook_mock, logger_mock):
    create_webhook_mock.return_value = "id"
    ack = MagicMock()
    view = helper_generate_view("foo")
    body = {"user": {"id": "user"}}
    client = MagicMock()
    say = MagicMock()
    webhooks_create.handle_create_webhook_action(
        ack,
        view,
        body,
        client,
        say,
    )
    create_webhook_mock.assert_called_with(
        "channel",
        "user",
        "foo",
        "alert",
    )
    logger_mock.info.assert_called_with(
        "webhook_creation_success",
        webhook_id="id",
        webhook_url="https://sre-bot.cdssandbox.xyz/hook/id",
        webhook_type="alert",
        channel="channel",
        user="user",
        name="foo",
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


@patch("modules.slack.webhooks_create.logger")
@patch("modules.slack.webhooks_create.webhooks.create_webhook")
def test_create_webhook_with_creation_error(create_webhook_mock, logger_mock):
    create_webhook_mock.return_value = None
    ack = MagicMock()
    view = helper_generate_view("foo")
    body = {"user": {"id": "user"}}
    client = MagicMock()
    say = MagicMock()
    webhooks_create.handle_create_webhook_action(
        ack,
        view,
        body,
        client,
        say,
    )
    create_webhook_mock.assert_called_with(
        "channel",
        "user",
        "foo",
        "alert",
    )
    logger_mock.error.assert_called_with(
        "webhook_creation_failure", channel="channel", user="user", name="foo"
    )

    client.chat_postEphemeral.assert_called_with(
        channel="channel",
        user="user",
        text="Something went wrong creating the webhook",
    )
