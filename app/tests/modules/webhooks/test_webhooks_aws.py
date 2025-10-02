from unittest.mock import MagicMock, patch

import pytest
from models.webhooks import AwsSnsPayload, WebhookPayload
from modules.webhooks import aws_sns
from fastapi import HTTPException
from sns_message_validator import SignatureVerificationFailureException


@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_validates_model(
    validate_message_mock, log_ops_message_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="test",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.return_value = None
    response = aws_sns.validate_sns_payload(payload, client)
    assert validate_message_mock.call_count == 1
    assert log_ops_message_mock.call_count == 0
    assert response == payload


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_invalid_message_type(
    validate_message_mock, log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="InvalidType",
        Message="test",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.side_effect = Exception(
        "InvalidType is not a valid message type."
    )
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_invalid_signature_version(
    validate_message_mock, log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="test",
        SignatureVersion="InvalidVersion",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.side_effect = Exception(
        "Invalid signature version. Unable to verify signature."
    )
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_invalid_signature_url(
    validate_message_mock, log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="test",
        SignatureVersion="1",
        SigningCertURL="https://invalid.url",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.side_effect = Exception("Invalid certificate URL.")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_signature_verification_failure(
    validate_message_mock, log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="test",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="invalid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.side_effect = SignatureVerificationFailureException(
        "Invalid signature."
    )
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_unexpected_exception(
    validate_message_mock, log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="test",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.side_effect = Exception("Unexpected error")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.process_aws_notification_payload")
@patch("modules.webhooks.aws_sns.validate_sns_payload")
def test_process_aws_sns_payload_with_notification_no_message(
    validate_sns_payload_mock, process_aws_notification_payload_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_sns_payload_mock.return_value = payload
    process_aws_notification_payload_mock.return_value = []
    response = aws_sns.process_aws_sns_payload(payload, client)
    assert response.status == "error"
    assert response.action == "none"
    assert response.message == "Empty AWS SNS Notification message"


@patch("modules.webhooks.aws_sns.process_aws_notification_payload")
@patch("modules.webhooks.aws_sns.validate_sns_payload")
def test_process_aws_sns_payload_aws_sns_notification(
    validate_sns_payload_mock, process_aws_notification_payload_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="message",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="valid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_sns_payload_mock.return_value = payload
    process_aws_notification_payload_mock.return_value = "parsed_blocks"
    result = aws_sns.process_aws_sns_payload(payload, client)
    assert result.status == "success"
    assert result.action == "post"
    assert isinstance(result.payload, WebhookPayload)
    assert result.payload.blocks == "parsed_blocks"


@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.requests.get")
@patch("modules.webhooks.aws_sns.validate_sns_payload")
def test_process_aws_sns_payload_aws_sns_subscription_confirmation(
    validate_sns_payload_mock, get_mock, log_ops_message_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="SubscriptionConfirmation",
        SubscribeURL="http://example.com",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_sns_payload_mock.return_value = payload
    result = aws_sns.process_aws_sns_payload(payload, client)
    assert result.status == "success"
    assert result.action == "log"
    assert result.payload is None
    assert log_ops_message_mock.call_count == 1


@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.requests.get")
@patch("modules.webhooks.aws_sns.validate_sns_payload")
def test_process_aws_sns_payload_with_aws_sns_unsubscribe_confirmation(
    validate_sns_payload_mock, get_mock, log_ops_message_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="UnsubscribeConfirmation",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_sns_payload_mock.return_value = payload
    response = aws_sns.process_aws_sns_payload(payload, client)
    assert response.status == "success"
    assert response.action == "log"
    assert response.payload is None
    assert log_ops_message_mock.call_count == 1
    assert get_mock.call_count == 0
