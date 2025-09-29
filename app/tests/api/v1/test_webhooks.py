from unittest.mock import patch, MagicMock, PropertyMock, call, ANY

# from urllib import response
from pydantic import BaseModel
import pytest
import httpx
from fastapi.testclient import TestClient
from api.v1.routes import webhooks
from models.webhooks import (
    AwsSnsPayload,
    WebhookPayload,
    AccessRequest,
    UpptimePayload,
    WebhookResult,
)
from utils.tests import create_test_app
from server import bot_middleware


@pytest.fixture
def bot_mock():
    return MagicMock()


@pytest.fixture
def test_client(bot_mock):
    middlewares = [(bot_middleware.BotMiddleware, {"bot": bot_mock})]
    test_app = create_test_app(webhooks.router, middlewares)
    return TestClient(test_app)


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
    test_client,
):
    payload = {"text": "some text"}
    mock_get_webhook.return_value = {
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "alert"},
        "active": {"BOOL": True},
    }

    mock_handle_webhook_payload.return_value = WebhookResult(
        status="success",
        action="post",
        payload=WebhookPayload(text="some text"),
    )

    mock_append_incident_buttons.return_value = WebhookPayload(
        text="some text",
        channel="test-channel",
    )

    response = test_client.post("/hook/id", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    mock_get_webhook.assert_called_once()
    mock_increment_invocation.assert_called_once_with("id")
    mock_handle_webhook_payload.assert_called_once_with(payload, ANY)
    mock_append_incident_buttons.assert_called_once()
    mock_log_to_sentinel.assert_called_once()


def test_handle_webhook_malformed_json_string(test_client):
    payload = '{"invalid_json": "missing_end_quote}'
    response = test_client.post("/hook/id", json=payload)
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unterminated string starting at: line 1 column 18 (char 17)"
    }


@patch("api.v1.routes.webhooks.webhooks.get_webhook")
def test_handle_webhook_not_found(get_webhook_mock, test_client):
    get_webhook_mock.return_value = None
    payload = {"channel": "channel"}
    response = test_client.post("/hook/id", json=payload)
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
    test_client,
):
    get_webhook_mock.return_value = {
        "channel": {"S": "channel"},
        "active": {"BOOL": False},
    }
    payload = {"channel": "channel"}
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    response = test_client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not active"}
    assert get_webhook_mock.call_count == 1
    assert increment_invocation_count_mock.call_count == 0
    assert append_incident_buttons_mock.call_count == 0


@patch("api.v1.routes.webhooks.log_to_sentinel")
@patch("api.v1.routes.webhooks.append_incident_buttons")
@patch("api.v1.routes.webhooks.handle_webhook_payload")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.webhooks.get_webhook")
def test_handle_webhook_hook_type_info(
    mock_get_webhook,
    mock_increment_invocation,
    mock_handle_webhook_payload,
    mock_append_incident_buttons,
    mock_log_to_sentinel,
    test_client,
):
    payload = {"text": "some text"}
    mock_get_webhook.return_value = {
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "info"},
        "active": {"BOOL": True},
    }

    mock_handle_webhook_payload.return_value = WebhookResult(
        status="success",
        action="post",
        payload=WebhookPayload(text="some text"),
    )

    mock_append_incident_buttons.return_value = WebhookPayload(
        text="some text",
        channel="test-channel",
    )

    response = test_client.post("/hook/id", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    mock_get_webhook.assert_called_once()
    mock_increment_invocation.assert_called_once_with("id")
    mock_handle_webhook_payload.assert_called_once_with(payload, ANY)
    mock_append_incident_buttons.assert_not_called()
    mock_log_to_sentinel.assert_called_once()


@patch("api.v1.routes.webhooks.log_to_sentinel")
@patch("api.v1.routes.webhooks.append_incident_buttons")
@patch("api.v1.routes.webhooks.handle_webhook_payload")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.webhooks.get_webhook")
def test_handle_webhook_hook_type_not_defined(
    mock_get_webhook,
    mock_increment_invocation,
    mock_handle_webhook_payload,
    mock_append_incident_buttons,
    mock_log_to_sentinel,
    test_client,
):
    payload = {"text": "some text"}
    mock_get_webhook.return_value = {
        "channel": {"S": "test-channel"},
        "active": {"BOOL": True},
    }

    mock_handle_webhook_payload.return_value = WebhookResult(
        status="success",
        action="post",
        payload=WebhookPayload(text="some text"),
    )

    mock_append_incident_buttons.return_value = WebhookPayload(
        text="some text",
        channel="test-channel",
    )

    response = test_client.post("/hook/id", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    mock_get_webhook.assert_called_once()
    mock_increment_invocation.assert_called_once_with("id")
    mock_handle_webhook_payload.assert_called_once_with(payload, ANY)
    mock_append_incident_buttons.assert_called_once()
    mock_log_to_sentinel.assert_called_once()


@patch("api.v1.routes.webhooks.handle_webhook_payload")
@patch("api.v1.routes.webhooks.append_incident_buttons")
@patch("api.v1.routes.webhooks.webhooks.get_webhook")
@patch("api.v1.routes.webhooks.webhooks.increment_invocation_count")
@patch("api.v1.routes.webhooks.log_to_sentinel")
def test_handle_webhook_with_none_payload_none(
    _log_to_sentinel_mock,
    increment_invocation_count_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
    handle_webhook_payload_mock,
    test_client,
):
    """Test that when handle_webhook_payload returns None, a 400 error is raised"""
    payload = {"text": "test message"}

    get_webhook_mock.return_value = {
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "standard"},
        "active": {"BOOL": True},
    }
    handle_webhook_payload_mock.return_value = WebhookResult(
        status="error", action=None, payload=None
    )

    response = test_client.post("/hook/id", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid payload"}

    # Verify the mocks were called as expected
    get_webhook_mock.assert_called_once()
    increment_invocation_count_mock.assert_called_once_with("id")
    handle_webhook_payload_mock.assert_called_once_with(payload, ANY)
    append_incident_buttons_mock.assert_not_called()


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
    test_client,
    bot_mock,
):
    """Test that Slack API failures are handled correctly with a 500 error"""
    payload = {"text": "test message"}

    get_webhook_mock.return_value = {
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "alert"},
        "active": {"BOOL": True},
    }

    webhook_payload = WebhookPayload(text="test message")
    handle_webhook_payload_mock.return_value = WebhookResult(
        status="success",
        action="post",
        payload=webhook_payload,
    )
    append_incident_buttons_mock.return_value = webhook_payload

    # Configure the bot mock to raise an exception
    bot_mock.client.api_call.side_effect = Exception("Slack API error")

    response = test_client.post("/hook/id", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to send message"}

    # Verify the mocks were called as expected
    get_webhook_mock.assert_called_once()
    increment_invocation_count_mock.assert_called_once_with("id")
    handle_webhook_payload_mock.assert_called_once_with(payload, ANY)
    bot_mock.client.api_call.assert_called_once_with(
        "chat.postMessage",
        json={
            "channel": "test-channel",
            "text": "test message",
            "attachments": [],
            "blocks": [],
        },
    )


@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_empty(mock_validate_payload):
    mock_validate_payload.return_value = None
    request = MagicMock()
    payload = {}

    response = webhooks.handle_webhook_payload(payload, request)
    assert response.status == "error"
    assert response.message == "No matching model found for payload"


@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_webhook_payload(validate_payload_mock):
    request = MagicMock()
    payload = {"text": "This is a test message"}
    validate_payload_mock.return_value = (
        WebhookPayload,
        WebhookPayload(text="This is a test message"),
    )
    result = webhooks.handle_webhook_payload(payload, request)
    assert isinstance(result.payload, WebhookPayload)
    assert result.status == "success"
    assert result.action == "post"
    assert result.payload.text == "This is a test message"
    assert result.payload.channel is None
    assert result.payload.attachments == []
    assert result.payload.blocks == []


@patch("api.v1.routes.webhooks.aws.parse")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_aws_sns_notification_no_message(
    validate_payload_mock,
    validate_sns_payload_mock,
    parse_mock,
):
    request = MagicMock()
    payload = {"Type": "Notification", "Message": ""}
    validate_payload_mock.return_value = (
        AwsSnsPayload,
        AwsSnsPayload(Type="Notification", Message=""),
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="Notification", Message=""
    )
    parse_mock.return_value = ""

    response = webhooks.handle_webhook_payload(payload, request)
    assert response.status == "error"
    assert response.action == "none"
    assert response.message == "Empty AWS SNS Notification message"


@patch("api.v1.routes.webhooks.aws.parse")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_aws_sns_notification(
    validate_payload_mock, validate_sns_payload_mock, parse_mock
):
    request = MagicMock()
    payload = {"Type": "Notification", "Message": "message"}
    validate_payload_mock.return_value = (
        AwsSnsPayload,
        AwsSnsPayload(Type="Notification", Message="message"),
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="Notification", Message="message"
    )
    parse_mock.return_value = "parsed_blocks"
    result = webhooks.handle_webhook_payload(payload, request)
    assert result.status == "success"
    assert result.action == "post"
    assert isinstance(result.payload, WebhookPayload)
    assert result.payload.blocks == "parsed_blocks"


@patch("api.v1.routes.webhooks.log_ops_message")
@patch("api.v1.routes.webhooks.requests.get")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_aws_sns_subscription_confirmation(
    validate_payload_mock,
    validate_sns_payload_mock,
    get_mock,
    log_ops_message_mock,
):
    request = MagicMock()
    payload = {"Type": "SubscriptionConfirmation", "SubscribeURL": "http://example.com"}
    validate_payload_mock.return_value = (
        AwsSnsPayload,
        AwsSnsPayload(
            Type="SubscriptionConfirmation", SubscribeURL="http://example.com"
        ),
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="SubscriptionConfirmation", SubscribeURL="http://example.com"
    )
    result = webhooks.handle_webhook_payload(payload, request)
    assert result.status == "success"
    assert result.action == "log"
    assert result.payload is None
    assert log_ops_message_mock.call_count == 1


@patch("api.v1.routes.webhooks.log_ops_message")
@patch("api.v1.routes.webhooks.requests.get")
@patch("api.v1.routes.webhooks.aws.validate_sns_payload")
@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_with_aws_sns_unsubscribe_confirmation(
    validate_payload_mock,
    validate_sns_payload_mock,
    get_mock,
    log_ops_message_mock,
):
    request = MagicMock()
    payload = {
        "Type": "UnsubscribeConfirmation",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
    }
    validate_payload_mock.return_value = (
        AwsSnsPayload,
        AwsSnsPayload(
            Type="UnsubscribeConfirmation",
            TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
        ),
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="UnsubscribeConfirmation",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.status == "success"
    assert response.action == "log"
    assert response.payload is None
    assert log_ops_message_mock.call_count == 1


@patch("api.v1.routes.webhooks.log_ops_message")
@patch("api.v1.routes.webhooks.requests.get")
@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_with_access_request(
    validate_payload_mock, get_mock, log_ops_message_mock
):
    request = MagicMock()
    payload = {
        "account": "account1",
        "reason": "reason1",
        "startDate": "2025-09-25T12:00:00Z",
        "endDate": "2025-09-26T12:00:00Z",
    }
    validate_payload_mock.return_value = (
        AccessRequest,
        AccessRequest(
            account="account1",
            reason="reason1",
            startDate="2025-09-25T12:00:00Z",
            endDate="2025-09-26T12:00:00Z",
        ),
    )
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.status == "success"
    assert response.action == "post"
    assert (
        response.payload.text
        == "{'account': 'account1', 'reason': 'reason1', 'startDate': datetime.datetime(2025, 9, 25, 12, 0, tzinfo=TzInfo(UTC)), 'endDate': datetime.datetime(2025, 9, 26, 12, 0, tzinfo=TzInfo(UTC))}"
    )


@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_upptime(validate_payload_mock):
    request = MagicMock()
    payload = {
        "text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
    }
    validate_payload_mock.return_value = (
        UpptimePayload,
        UpptimePayload(
            text="🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
        ),
    )
    response = webhooks.handle_webhook_payload(payload, request)
    assert response.status == "success"
    assert response.action == "post"
    assert response.payload.blocks == [
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


@patch("api.v1.routes.webhooks.validate_payload")
def test_handle_webhook_payload_with_invalid_payload_type(
    mock_validate_payload,
):
    class UnknownPayload(BaseModel):
        invalid_field: str

        class Config:
            extra = "forbid"

    request = MagicMock()
    payload = {}
    mock_validate_payload.return_value = (
        UnknownPayload,
        UnknownPayload(invalid_field="invalid_field"),
    )

    response = webhooks.handle_webhook_payload(payload, request)
    assert response.status == "error"
    assert response.message == "No matching model found for payload"


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
    return_value={
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "standard"},
        "active": {"BOOL": True},
    },
)
@pytest.mark.asyncio
async def test_webhooks_rate_limiting(
    get_webhook_mock,
    is_active_mock,
    increment_invocation_count_mock,
    handle_webhook_payload_mock,
    bot_mock,
    test_client,
):
    # Create a custom transport to mount the ASGI app
    transport = httpx.ASGITransport(app=test_client.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = '{"Type": "Notification"}'
        # Return a proper WebhookPayload instance
        mock_webhook_payload = WebhookPayload(text="Test message")
        handle_webhook_payload_mock.return_value = WebhookResult(
            status="success", action="post", payload=mock_webhook_payload
        )
        # Make 30 requests to the handle_webhook endpoint
        for _ in range(30):
            response = await client.post("/hook/test-id", json=payload)
            assert response.status_code == 200

        # The 31st request should be rate limited
        response = await client.post("/hook/test-id", json=payload)
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}
