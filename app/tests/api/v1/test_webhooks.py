from unittest.mock import patch, MagicMock, PropertyMock, call, ANY
import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from api.v1.routes import webhooks
from models.webhooks import AwsSnsPayload, WebhookPayload
from utils.tests import create_test_app
from server import bot_middleware

middlewares = [(bot_middleware.BotMiddleware, {"bot": MagicMock()})]
test_app = create_test_app(webhooks.router, middlewares)
client = TestClient(test_app)


@patch("api.v1.routes.webhooks.log_to_sentinel")
@patch("api.v1.routes.webhooks.append_incident_buttons")
@patch("api.v1.routes.webhooks.handle_webhook_payload")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.webhooks.get_webhook")
def test_handle_webhook(
    mock_get_webhook,
    mock_increment_invocation,
    mock_handle_webhook_payload,
    mock_append_incident_buttons,
    mock_log_to_sentinel,
):
    payload = {"text": "some text"}
    mock_get_webhook.return_value = {
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "alert"},
        "active": {"BOOL": True},
    }

    mock_handle_webhook_payload.return_value = WebhookPayload(text="some text")

    mock_append_incident_buttons.return_value = WebhookPayload(
        text="some text",
        channel="test-channel",
    )

    response = client.post("/hook/id", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    mock_get_webhook.assert_called_once()
    mock_increment_invocation.assert_called_once_with("id")
    mock_handle_webhook_payload.assert_called_once_with(payload, ANY)
    mock_append_incident_buttons.assert_called_once()
    mock_log_to_sentinel.assert_called_once()


def test_handle_webhook_string_payload_malformed_json_string():
    payload = '{"invalid_json": "missing_end_quote}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unterminated string starting at: line 1 column 18 (char 17)"
    }


@patch("api.v1.routes.webhooks.webhooks.get_webhook")
def test_handle_webhook_not_found(get_webhook_mock):
    get_webhook_mock.return_value = None
    payload = {"channel": "channel"}
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not found"}
    assert get_webhook_mock.call_count == 1


@patch("api.v1.routes.webhooks.append_incident_buttons")
@patch("api.v1.routes.webhooks.webhooks.get_webhook")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.log_to_sentinel")
def test_handle_webhook_disabled(
    _log_to_sentinel_mock,
    increment_invocation_count_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
):
    get_webhook_mock.return_value = {
        "channel": {"S": "channel"},
        "active": {"BOOL": False},
    }
    payload = {"channel": "channel"}
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not active"}
    assert get_webhook_mock.call_count == 1
    assert increment_invocation_count_mock.call_count == 0
    assert append_incident_buttons_mock.call_count == 0


@patch("api.v1.routes.webhooks.log_to_sentinel")
@patch("api.v1.routes.webhooks.append_incident_buttons")
@patch("api.v1.routes.webhooks.webhooks.get_webhook")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.handle_webhook_payload")
def test_handle_webhook_slack_api_failure(
    handle_webhook_payload_mock,
    increment_invocation_count_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
    _mock_log_to_sentinel,
):
    """Test that Slack API failures are handled correctly with a 500 error"""
    payload = {"text": "test message"}

    get_webhook_mock.return_value = {
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "alert"},
        "active": {"BOOL": True},
    }

    webhook_payload = WebhookPayload(text="test message")
    handle_webhook_payload_mock.return_value = webhook_payload
    append_incident_buttons_mock.return_value = webhook_payload

    # Configure the middleware mock bot client to raise an exception
    middlewares[0][1]["bot"].client.api_call.side_effect = Exception("Slack API error")

    response = client.post("/hook/id", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to send message"}

    # Verify the mocks were called as expected
    get_webhook_mock.assert_called_once()
    increment_invocation_count_mock.assert_called_once_with("id")
    handle_webhook_payload_mock.assert_called_once_with(payload, ANY)
    # calls = [
    #     call("chat.postMessage", json={"channel": "test-channel", "text": "test message"})
    # ]
    middlewares[0][1]["bot"].client.api_call.assert_called_once_with(
        "chat.postMessage", json={"channel": "test-channel", "text": "test message"}
    )


@patch("api.v1.routes.webhooks.webhooks.get_webhook")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.log_ops_message")
@patch("api.v1.routes.webhooks.handle_webhook_payload")
def test_handle_webhook_string_returns_webhook_payload(
    handle_webhook_payload_mock,
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
    caplog,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"channel": "channel"}'
    handle_webhook_payload_mock.return_value = {
        "channel": "channel",
        "blocks": "blocks",
    }
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"channel": "channel", "blocks": "blocks"}
    assert handle_webhook_payload_mock.call_count == 1


@patch("api.v1.routes.webhooks.webhooks.get_webhook")

@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.log_ops_message")
@patch("api.v1.routes.webhooks.handle_webhook_payload")
def test_handle_webhook_string_payload_returns_OK_status(
    handle_webhook_payload_mock,
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = "test"
    handle_webhook_payload_mock.return_value = {"ok": True}
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert handle_webhook_payload_mock.call_count == 1


@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_webhook_string(
    validate_string_payload_type_mock,
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "WebhookPayload",
        {"channel": "channel"},
    )
    payload = '{"channel": "channel"}'
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.channel == "channel"


@patch("api.v1.routes.webhooks.aws.parse")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_aws_sns_notification_without_message(
    validate_string_payload_type_mock,
    validate_sns_payload_mock,
    parse_mock,
):
    request = MagicMock()
    payload = '{"Type": "Notification", "Message": "{}"}'
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {"Type": "Notification", "Message": ""},
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="Notification", Message=""
    )
    parse_mock.return_value = ""
    response = webhooks.handle_webhook_payload(payload, request)
    assert response == {"ok": True}


@patch("api.v1.routes.webhooks.aws.parse")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_aws_sns_notification(
    validate_string_payload_type_mock, validate_sns_payload_mock, parse_mock
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {"Type": "Notification", "Message": "message"},
    )
    payload = '{"Type": "Notification", "Message": "message"}'
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="Notification", Message="message"
    )
    parse_mock.return_value = "parsed_blocks"
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.blocks == "parsed_blocks"


@patch("api.v1.routes.webhooks.log_ops_message")
@patch("api.v1.routes.webhooks.requests.get")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_aws_sns_subscription_confirmation(
    validate_string_payload_type_mock,
    validate_sns_payload_mock,
    get_mock,
    log_ops_message_mock,
):
    request = MagicMock()
    payload = (
        '{"Type": "SubscriptionConfirmation", "SubscribeURL": "http://example.com"}'
    )
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {"Type": "SubscriptionConfirmation", "SubscribeURL": "http://example.com"},
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="SubscriptionConfirmation", SubscribeURL="http://example.com"
    )
    response = webhooks.handle_webhook_payload(payload, request)
    assert response == {"ok": True}
    assert log_ops_message_mock.call_count == 1


@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_aws_sns_unsubscribe_confirmation(
    validate_string_payload_type_mock, validate_sns_payload_mock
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {
            "Type": "UnsubscribeConfirmation",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        },
    )
    payload = '{"Type": "UnsubscribeConfirmation", "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic"}'
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="UnsubscribeConfirmation",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    response = webhooks.handle_webhook_payload(payload, request)
    assert response == {"ok": True}


@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_access_request(validate_string_payload_type_mock):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "AccessRequest",
        {"user": "user1"},
    )
    payload = '{"user": "user1"}'
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.text == '{"user": "user1"}'


@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_upptime_payload(validate_string_payload_type_mock):
    request = MagicMock()
    payload = '{"text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"}'
    validate_string_payload_type_mock.return_value = (
        "UpptimePayload",
        {
            "text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
        },
    )
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.blocks == [
        {"text": {"text": " ", "type": "mrkdwn"}, "type": "section"},
        {
            "text": {
                "text": "📈 Web Application Status Changed!",
                "type": "plain_text",
            },
            "type": "header",
        },
        {
            "text": {
                "text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222",
                "type": "mrkdwn",
            },
            "type": "section",
        },
    ]


@patch("api.v1.routes.webhooks.webhooks.validate_string_payload_type")
def test_handle_webhook_payload_with_invalid_payload_type(
    validate_string_payload_type_mock,
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "InvalidPayloadType",
        {},
    )
    payload = "{}"
    with pytest.raises(HTTPException) as exc_info:
        webhooks.handle_webhook_payload(payload, request)
    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail
        == "Invalid payload type. Must be a WebhookPayload object or a recognized string payload type."
    )


@patch("api.v1.routes.webhooks.webhooks.get_webhook")

@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.log_ops_message")
def test_handle_webhook_payload_with_invalid_json_payload(
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = "not a json payload"
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Invalid payload type. Must be a WebhookPayload object or a recognized string payload type."
    }


def test_handle_webhook_payload_with_valid_json_payload():
    pass


def test_append_incident_buttons_with_list_attachments():
    payload = MagicMock()
    attachments = PropertyMock(return_value=[])
    type(payload).attachments = attachments
    type(payload).text = PropertyMock(return_value="text")
    webhook_id = "bar"
    resp = webhooks.append_incident_buttons(payload, webhook_id)
    assert payload == resp
    assert attachments.call_count == 4
    assert attachments.call_args_list == [
        call(),
        call(),
        call(),
        call(
            [
                {
                    "fallback": "Incident",
                    "callback_id": "handle_incident_action_buttons",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "call-incident",
                            "text": "🎉   Call incident ",
                            "type": "button",
                            "value": "text",
                            "style": "primary",
                        },
                        {
                            "name": "ignore-incident",
                            "text": "🙈   Acknowledge and ignore",
                            "type": "button",
                            "value": "bar",
                            "style": "default",
                        },
                    ],
                }
            ]
        ),
    ]


def test_append_incident_buttons_with_none_attachments():
    payload = MagicMock()
    payload.attachments = None
    payload.text = "text"
    webhook_id = "bar"

    resp = webhooks.append_incident_buttons(payload, webhook_id)

    assert payload == resp
    assert payload.attachments == [
        {
            "fallback": "Incident",
            "callback_id": "handle_incident_action_buttons",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "call-incident",
                    "text": "🎉   Call incident ",
                    "type": "button",
                    "value": "text",
                    "style": "primary",
                },
                {
                    "name": "ignore-incident",
                    "text": "🙈   Acknowledge and ignore",
                    "type": "button",
                    "value": "bar",
                    "style": "default",
                },
            ],
        }
    ]


def test_append_incident_buttons_with_str_attachments():
    payload = MagicMock()
    payload.attachments = "existing_attachment"
    payload.text = "text"
    webhook_id = "bar"

    resp = webhooks.append_incident_buttons(payload, webhook_id)
    assert payload == resp
    assert payload.attachments == [
        "existing_attachment",
        {
            "fallback": "Incident",
            "callback_id": "handle_incident_action_buttons",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "call-incident",
                    "text": "🎉   Call incident ",
                    "type": "button",
                    "value": "text",
                    "style": "primary",
                },
                {
                    "name": "ignore-incident",
                    "text": "🙈   Acknowledge and ignore",
                    "type": "button",
                    "value": "bar",
                    "style": "default",
                },
            ],
        },
    ]


@patch("api.v1.routes.webhooks.handle_webhook_payload")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.webhooks.is_active", return_value=True)
@patch(
    "api.v1.routes.webhooks.webhooks.get_webhook",
    return_value={"channel": {"S": "test-channel"}, "hook_type": {"S": "standard"}, "active": {"BOOL": True}},
)
@pytest.mark.asyncio
async def test_webhooks_rate_limiting(
    get_webhook_mock,
    is_active_mock,
    increment_invocation_count_mock,
    handle_webhook_payload_mock,
):
    # Create a custom transport to mount the ASGI app
    transport = httpx.ASGITransport(app=test_app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = '{"Type": "Notification"}'
        # Return a proper WebhookPayload instance
        mock_webhook_payload = WebhookPayload(text="Test message")
        handle_webhook_payload_mock.return_value = mock_webhook_payload
        # Make 30 requests to the handle_webhook endpoint
        for _ in range(30):
            response = await client.post("/hook/test-id", json=payload)
            assert response.status_code == 200

        # The 31st request should be rate limited
        response = await client.post("/hook/test-id", json=payload)
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}
