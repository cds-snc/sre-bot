from commands.helpers import vpn_helper


from unittest.mock import call, MagicMock, patch


def test_handle_vpn_empty_command():
    respond = MagicMock()
    vpn_helper.handle_vpn_command([], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(vpn_helper.help_text)


def test_handle_vpn_unknown_command():
    respond = MagicMock()
    vpn_helper.handle_vpn_command(["foobar"], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(
        "Unknown command: `foobar`. Type `/sre vpn help` to see a list of commands.\nCommande inconnue: `foobar`. Tapez `/sre vpn help` pour voir une liste de commandes."
    )


def test_handle_vpn_help_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    vpn_helper.handle_vpn_command(
        ["help"],
        client,
        body,
        respond,
    )
    respond.assert_called_once_with(vpn_helper.help_text)


@patch("commands.helpers.vpn_helper.vpn_on_modal")
def test_handle_vpn_on_command(mock_vpn_on_modal):
    client = MagicMock()
    body = MagicMock()
    vpn_helper.handle_vpn_command(["on"], client, body, MagicMock())
    mock_vpn_on_modal.assert_called_with(client, body)


@patch("commands.helpers.vpn_helper.vpn_status_modal")
def test_handle_vpn_status_command(mock_vpn_status_modal):
    client = MagicMock()
    body = MagicMock()
    vpn_helper.handle_vpn_command(["status"], client, body, MagicMock())
    mock_vpn_status_modal.assert_called_with(client, body)


@patch("commands.helpers.vpn_helper.VPN_PRODUCTS", {"vpn1": "", "vpn2": ""})
def test_vpn_on_modal():
    client = MagicMock()
    body = {"trigger_id": "trigger_id"}
    vpn_helper.vpn_on_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view={
            "type": "modal",
            "callback_id": "vpn_on",
            "title": {"type": "plain_text", "text": "SRE - VPN On"},
            "submit": {"type": "plain_text", "text": "Turn on"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Select the VPN to turn on",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "vpn",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a VPN",
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "vpn1",
                                    "emoji": True,
                                },
                                "value": "vpn1",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "vpn2",
                                    "emoji": True,
                                },
                                "value": "vpn2",
                            },
                        ],
                        "action_id": "vpn",
                    },
                    "label": {"type": "plain_text", "text": "VPN", "emoji": True},
                },
                {
                    "block_id": "duration",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a duration",
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "1 hour",
                                    "emoji": True,
                                },
                                "value": "1",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "4 hours",
                                    "emoji": True,
                                },
                                "value": "4",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "8 hours",
                                    "emoji": True,
                                },
                                "value": "8",
                            },
                        ],
                        "action_id": "duration",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "How long should it stay on?",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "reason",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reason",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Why is it being turned on?",
                    },
                },
            ],
        },
    )


@patch(
    "commands.helpers.vpn_helper.VPN_PRODUCTS",
    {"vpn1": {"vpn_id": "vpn-123", "role_arn": "test/role-name", "channel_id": "456"}},
)
@patch("commands.helpers.vpn_helper.AWSClientVPN")
def test_vpn_on(mock_aws_client_vpn):
    ack = MagicMock()
    view = {
        "state": {
            "values": {
                "vpn": {"vpn": {"selected_option": {"value": "vpn1"}}},
                "duration": {"duration": {"selected_option": {"value": "1"}}},
                "reason": {"reason": {"value": "because"}},
            }
        }
    }
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    client_vpn = MagicMock()
    mock_aws_client_vpn.return_value = client_vpn
    mock_aws_client_vpn.STATUS_TURNING_ON = "turning-on"
    client_vpn.turn_on.return_value = "turning-on"

    vpn_helper.vpn_on(ack, view, client, body, logger)

    ack.assert_called_once_with()
    mock_aws_client_vpn.assert_called_with(
        name="vpn1",
        reason="because",
        duration="1",
        vpn_id="vpn-123",
        assume_role_arn="test/role-name",
    )
    mock_aws_client_vpn().turn_on.assert_called_with()
    client.chat_postMessage.assert_called_with(
        channel="456",
        text=":beach-ball: The `vpn1` VPN is `turning-on` for 1 hour:\n```Reason: because```\n\nThis can take up to 5 minutes.  Use the following to check the status.\n```/sre vpn status```",
    )


@patch(
    "commands.helpers.vpn_helper.VPN_PRODUCTS",
    {"vpn1": {"vpn_id": "vpn-123", "role_arn": "test/role-name", "channel_id": "456"}},
)
@patch("commands.helpers.vpn_helper.AWSClientVPN")
def test_vpn_on_error(mock_aws_client_vpn):
    ack = MagicMock()
    view = {
        "state": {
            "values": {
                "vpn": {"vpn": {"selected_option": {"value": "vpn1"}}},
                "duration": {"duration": {"selected_option": {"value": "1"}}},
                "reason": {"reason": {"value": "because"}},
            }
        }
    }
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    client_vpn = MagicMock()
    mock_aws_client_vpn.return_value = client_vpn
    mock_aws_client_vpn.STATUS_ERROR = "error"
    client_vpn.turn_on.return_value = "error"

    vpn_helper.vpn_on(ack, view, client, body, logger)

    ack.assert_called_once_with()
    mock_aws_client_vpn.assert_called_with(
        name="vpn1",
        reason="because",
        duration="1",
        vpn_id="vpn-123",
        assume_role_arn="test/role-name",
    )
    mock_aws_client_vpn().turn_on.assert_called_with()
    client.chat_postMessage.assert_called_with(
        channel="456",
        text=":red: There was an error turning on the `vpn1` VPN.  Please contact SRE for help.",
    )


def test_vpn_on_validation_error():
    ack = MagicMock()
    view = {
        "state": {
            "values": {
                "vpn": {"vpn": {"selected_option": {"value": "vpn1"}}},
                "duration": {"duration": {"selected_option": {"value": "2"}}},
                "reason": {"reason": {"value": ""}},
            }
        }
    }
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()

    vpn_helper.vpn_on(ack, view, client, body, logger)

    ack.assert_has_calls(
        [
            call(),
            call(
                response_action="errors",
                errors={
                    "vpn": "Please select a VPN from the dropdown",
                    "reason": "Please enter a reason",
                    "duration": "Please select a valid duration",
                },
            ),
        ]
    )


@patch("commands.helpers.vpn_helper.VPN_PRODUCTS", {"vpn1": "", "vpn2": ""})
def test_vpn_status_modal():
    client = MagicMock()
    body = {"trigger_id": "trigger_id"}
    vpn_helper.vpn_status_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view={
            "type": "modal",
            "callback_id": "vpn_status",
            "title": {"type": "plain_text", "text": "SRE - VPN Status"},
            "submit": {"type": "plain_text", "text": "Get status"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Select the VPN",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "vpn",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a VPN",
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "vpn1",
                                    "emoji": True,
                                },
                                "value": "vpn1",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "vpn2",
                                    "emoji": True,
                                },
                                "value": "vpn2",
                            },
                        ],
                        "action_id": "vpn",
                    },
                    "label": {"type": "plain_text", "text": "VPN", "emoji": True},
                },
            ],
        },
    )


@patch(
    "commands.helpers.vpn_helper.VPN_PRODUCTS",
    {"vpn1": {"vpn_id": "vpn-123", "role_arn": "test/role-name", "channel_id": "456"}},
)
@patch("commands.helpers.vpn_helper.AWSClientVPN")
def test_vpn_status_vpn_off(mock_aws_client_vpn):
    ack = MagicMock()
    view = {
        "state": {
            "values": {
                "vpn": {"vpn": {"selected_option": {"value": "vpn1"}}},
            }
        }
    }
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    client_vpn = MagicMock()
    mock_aws_client_vpn.return_value = client_vpn
    client_vpn.get_status.return_value = {"status": "off"}

    vpn_helper.vpn_status(ack, view, client, body, logger)

    ack.assert_called_once_with()
    mock_aws_client_vpn.assert_called_with(
        name="vpn1",
        vpn_id="vpn-123",
        assume_role_arn="test/role-name",
    )
    mock_aws_client_vpn().get_status.assert_called_with()
    client.chat_postEphemeral.assert_called_with(
        channel="456", text=":red: The `vpn1` VPN is `off`", user="user"
    )


@patch(
    "commands.helpers.vpn_helper.VPN_PRODUCTS",
    {"vpn1": {"vpn_id": "vpn-123", "role_arn": "test/role-name", "channel_id": "456"}},
)
@patch("commands.helpers.vpn_helper.AWSClientVPN")
def test_vpn_status_vpn_turning_on(mock_aws_client_vpn):
    ack = MagicMock()
    view = {
        "state": {
            "values": {
                "vpn": {"vpn": {"selected_option": {"value": "vpn1"}}},
            }
        }
    }
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    client_vpn = MagicMock()
    mock_aws_client_vpn.return_value = client_vpn
    mock_aws_client_vpn.STATUS_TURNING_ON = "turning-on"
    client_vpn.get_status.return_value = {
        "status": "turning-on",
        "session": {"duration": {"N": "4"}, "reason": {"S": "because"}},
    }

    vpn_helper.vpn_status(ack, view, client, body, logger)

    ack.assert_called_once_with()
    mock_aws_client_vpn.assert_called_with(
        name="vpn1",
        vpn_id="vpn-123",
        assume_role_arn="test/role-name",
    )
    mock_aws_client_vpn().get_status.assert_called_with()
    client.chat_postEphemeral.assert_called_with(
        channel="456",
        text=":beach-ball: The `vpn1` VPN is `turning-on` for 4 hours:\n```Reason: because```",
        user="user",
    )


@patch(
    "commands.helpers.vpn_helper.VPN_PRODUCTS",
    {"vpn1": {"vpn_id": "vpn-123", "role_arn": "test/role-name", "channel_id": "456"}},
)
@patch("commands.helpers.vpn_helper.AWSClientVPN")
@patch("commands.helpers.vpn_helper.datetime")
def test_vpn_status_vpn_on(mock_datetime, mock_aws_client_vpn):
    ack = MagicMock()
    view = {
        "state": {
            "values": {
                "vpn": {"vpn": {"selected_option": {"value": "vpn1"}}},
            }
        }
    }
    body = {"user": {"id": "user"}}
    logger = MagicMock()
    client = MagicMock()
    client_vpn = MagicMock()
    mock_aws_client_vpn.return_value = client_vpn
    mock_aws_client_vpn.STATUS_ON = "on"
    client_vpn.get_status.return_value = {
        "status": "on",
        "session": {
            "duration": {"N": "4"},
            "reason": {"S": "because"},
            "expires_at": {"N": "1640092800"},
        },
    }
    mock_datetime.datetime.now.return_value.timestamp.return_value = 1640081000

    vpn_helper.vpn_status(ack, view, client, body, logger)

    ack.assert_called_once_with()
    mock_aws_client_vpn.assert_called_with(
        name="vpn1",
        vpn_id="vpn-123",
        assume_role_arn="test/role-name",
    )
    mock_aws_client_vpn().get_status.assert_called_with()
    client.chat_postEphemeral.assert_called_with(
        channel="456",
        text=":green: The `vpn1` VPN is `on` for 3 hours 16 minutes:\n```Reason: because```",
        user="user",
    )


def test_get_select_options():
    options = ["1", "4", "8"]
    transform = lambda x: "hour" if x == "1" else "hours"  # noqa: E731
    assert vpn_helper.get_select_options(options, transform=transform) == [
        {"text": {"type": "plain_text", "text": "hour", "emoji": True}, "value": "1"},
        {"text": {"type": "plain_text", "text": "hours", "emoji": True}, "value": "4"},
        {"text": {"type": "plain_text", "text": "hours", "emoji": True}, "value": "8"},
    ]


def test_get_status_icon():
    assert vpn_helper.get_status_icon("turning-on") == ":beach-ball:"
    assert vpn_helper.get_status_icon("on") == ":green:"
    assert vpn_helper.get_status_icon("off") == ":red:"
    assert vpn_helper.get_status_icon("error") == ":red:"


def test_pluralize():
    assert vpn_helper.pluralize(1, "hour") == "1 hour"
    assert vpn_helper.pluralize(2, "hour") == "2 hours"
