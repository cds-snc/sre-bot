import inspect
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sns_message_validator import (
    InvalidCertURLException,
    InvalidMessageTypeException,
    InvalidSignatureVersionException,
    SignatureVerificationFailureException,
)

from infrastructure.configuration.app import AppSettings
from models.webhooks import AwsSnsPayload, WebhookPayload
from modules.webhooks import aws_sns


@pytest.fixture
def force_production_app_settings(monkeypatch):
    monkeypatch.setattr(
        "modules.webhooks.aws_sns.app_settings",
        AppSettings(ENVIRONMENT="production"),
    )


@pytest.fixture
def non_production_app_settings(monkeypatch):
    """Force a non-production environment to prove validation is not environment-gated."""
    monkeypatch.setattr(
        "modules.webhooks.aws_sns.app_settings",
        AppSettings(ENVIRONMENT="local"),
    )


@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_validates_model(validate_message_mock, log_ops_message_mock, force_production_app_settings):
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
    validate_message_mock,
    log_ops_message_mock,
    logger_mock,
    force_production_app_settings,
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
    validate_message_mock.side_effect = InvalidMessageTypeException("InvalidType is not a valid message type.")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    assert e.value.detail == "Failed to validate AWS event message"
    assert "InvalidMessageTypeException" not in e.value.detail
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_invalid_signature_version(
    validate_message_mock,
    log_ops_message_mock,
    logger_mock,
    force_production_app_settings,
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
    validate_message_mock.side_effect = InvalidSignatureVersionException("Invalid signature version. Unable to verify signature.")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    assert e.value.detail == "Failed to validate AWS event message"
    assert "InvalidSignatureVersionException" not in e.value.detail
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_invalid_signature_url(
    validate_message_mock,
    log_ops_message_mock,
    logger_mock,
    force_production_app_settings,
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
    validate_message_mock.side_effect = InvalidCertURLException("Invalid certificate URL.")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    assert e.value.detail == "Failed to validate AWS event message"
    assert "InvalidCertURLException" not in e.value.detail
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_signature_verification_failure(
    validate_message_mock,
    log_ops_message_mock,
    logger_mock,
    force_production_app_settings,
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
    validate_message_mock.side_effect = SignatureVerificationFailureException("Invalid signature.")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    assert e.value.detail == "Failed to validate AWS event message"
    assert "SignatureVerificationFailureException" not in e.value.detail
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_unexpected_exception(
    validate_message_mock,
    log_ops_message_mock,
    logger_mock,
    force_production_app_settings,
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
    assert e.value.detail == "Failed to parse AWS event message"
    assert "Unexpected error" not in e.value.detail
    logger_mock.exception.assert_called_once()
    log_ops_message_mock.assert_called_once()


@patch("modules.webhooks.aws_sns.logger")
@patch("modules.webhooks.aws_sns.log_ops_message")
@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")
def test_validate_sns_payload_rejects_invalid_signature_outside_production(
    validate_message_mock,
    log_ops_message_mock,
    logger_mock,
    non_production_app_settings,
):
    """SNS signature validation must run in every environment, not just production."""
    client = MagicMock()
    payload = AwsSnsPayload(
        Type="Notification",
        Message="test",
        SignatureVersion="1",
        SigningCertURL="https://sns.us-east-1.amazonaws.com/valid-cert.pem",
        Signature="invalid_signature",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    validate_message_mock.side_effect = SignatureVerificationFailureException("Invalid signature.")
    with pytest.raises(HTTPException) as e:
        aws_sns.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    validate_message_mock.assert_called_once()


def test_aws_sns_module_does_not_interpolate_exception_details():
    """No 5xx webhook path should embed the exception class name or message."""
    source = inspect.getsource(aws_sns)

    assert "e.__class__" not in source


@patch("modules.webhooks.aws_sns.process_aws_notification_payload")
@patch("modules.webhooks.aws_sns.validate_sns_payload")
def test_process_aws_sns_payload_with_notification_no_message(validate_sns_payload_mock, process_aws_notification_payload_mock):
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
def test_process_aws_sns_payload_aws_sns_notification(validate_sns_payload_mock, process_aws_notification_payload_mock):
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
def test_process_aws_sns_payload_aws_sns_subscription_confirmation(validate_sns_payload_mock, get_mock, log_ops_message_mock):
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
def test_process_aws_sns_payload_with_aws_sns_unsubscribe_confirmation(validate_sns_payload_mock, get_mock, log_ops_message_mock):
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
