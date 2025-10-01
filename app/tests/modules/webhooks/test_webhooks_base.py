from unittest.mock import patch, ANY, MagicMock
from modules.webhooks import base
from pydantic import BaseModel
from models.webhooks import (
    WebhookPayload,
    AwsSnsPayload,
    AccessRequest,
    SimpleTextPayload,
    WebhookResult,
)


@patch("modules.webhooks.base.logger")
@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_returns_model_if_valid(mock_select_best_model, mock_logger):
    payload = {"text": "Test"}

    class MockModel(BaseModel):
        text: str

    mock_select_best_model.return_value = (
        MockModel,
        MockModel(text="validated_payload"),
    )

    validated = base.validate_payload(payload)

    mock_select_best_model.assert_called_once_with(
        payload,
        ANY,  # models list
        None,  # priorities argument
    )
    assert validated == (MockModel, MockModel(text="validated_payload"))
    mock_logger.info.assert_called_once_with(
        "payload_validation_success",
        model="MockModel",
        payload={"text": "validated_payload"},
    )


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_returns_none_if_invalid(mock_select_best_model):
    payload = {"unknown_field": "value"}
    mock_select_best_model.return_value = None

    validated = base.validate_payload(payload)

    mock_select_best_model.assert_called_once_with(
        payload,
        ANY,  # models list
        None,  # priorities argument
    )
    assert validated is None


@patch("modules.webhooks.base.validate_payload")
def test_handle_webhook_payload_empty(mock_validate_payload):
    mock_validate_payload.return_value = None
    request = MagicMock()
    payload = {}

    response = base.handle_webhook_payload(payload, request)
    assert response.status == "error"
    assert response.message == "No matching model found for payload"


@patch("modules.webhooks.base.validate_payload")
def test_handle_webhook_payload_webhook_payload(validate_payload_mock):
    request = MagicMock()
    payload = {"text": "This is a test message"}
    validate_payload_mock.return_value = (
        WebhookPayload,
        WebhookPayload(text="This is a test message"),
    )
    result = base.handle_webhook_payload(payload, request)
    assert isinstance(result.payload, WebhookPayload)
    assert result.status == "success"
    assert result.action == "post"
    assert result.payload.text == "This is a test message"
    assert result.payload.channel is None
    assert result.payload.attachments == []
    assert result.payload.blocks == []


@patch("modules.webhooks.base.process_aws_sns_payload")
@patch("modules.webhooks.base.validate_payload")
def test_handle_webhook_payload_with_sns_payload(
    validate_payload_mock,
    process_aws_sns_payload_mock,
):
    request = MagicMock()
    payload = {
        "Type": "Notification",
        "MessageId": "12345",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        "Message": "This is a test message from SNS",
        "Timestamp": "2023-10-01T12:00:00.000Z",
    }
    validate_payload_mock.return_value = (
        AwsSnsPayload,
        AwsSnsPayload(
            Type="Notification",
            MessageId="12345",
            TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
            Message="This is a test message from SNS",
            Timestamp="2023-10-01T12:00:00.000Z",
        ),
    )

    process_aws_sns_payload_mock.return_value = WebhookResult(
        status="success",
        action="post",
        payload=WebhookPayload(text="Processed SNS message"),
    )
    response = base.handle_webhook_payload(payload, request)

    assert response.status == "success"
    assert response.action == "post"
    assert isinstance(response.payload, WebhookPayload)
    assert response.payload.text == "Processed SNS message"
    process_aws_sns_payload_mock.assert_called_once_with(
        ANY, request.state.bot.client
    )  # Ensure the client is passed


@patch("modules.webhooks.base.validate_payload")
def test_handle_webhook_payload_with_access_request(validate_payload_mock):
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
    response = base.handle_webhook_payload(payload, request)
    assert response.status == "success"
    assert response.action == "post"
    assert (
        response.payload.text
        == "{'account': 'account1', 'reason': 'reason1', 'startDate': datetime.datetime(2025, 9, 25, 12, 0, tzinfo=TzInfo(UTC)), 'endDate': datetime.datetime(2025, 9, 26, 12, 0, tzinfo=TzInfo(UTC))}"
    )


@patch("modules.webhooks.base.validate_payload")
def test_handle_webhook_payload_upptime(validate_payload_mock):
    request = MagicMock()
    payload = {
        "text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
    }
    validate_payload_mock.return_value = (
        SimpleTextPayload,
        SimpleTextPayload(
            text="🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
        ),
    )
    response = base.handle_webhook_payload(payload, request)
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


@patch("modules.webhooks.base.validate_payload")
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

    response = base.handle_webhook_payload(payload, request)
    assert response.status == "error"
    assert response.message == "No matching model found for payload"
