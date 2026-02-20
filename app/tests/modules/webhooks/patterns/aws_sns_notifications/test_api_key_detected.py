import os
from unittest.mock import MagicMock, patch
from modules.webhooks.patterns.aws_sns_notification import api_key_detected


def mock_api_key_detected():
    NOTIFY_TEST_KEY = os.getenv("NOTIFY_TEST_KEY", "api-key-blah")
    return MagicMock(
        Type="Notification",
        MessageId="1e5f5647g-adb5-5d6f-ab5e-c2e508881361",
        TopicArn="arn:aws:sns:ca-central-1:412578375350:test-sre-bot",
        Subject="API Key detected",
        Message=f"API Key with value token='{NOTIFY_TEST_KEY}', type='cds_test_type' and source='source_data' has been detected in url='https://github.com/blah'!",
        Timestamp="2023-09-25T20:50:37.868Z",
        SignatureVersion="1",
        Signature="EXAMPLEO0OA1HN4MIHrtym3N6SWqvotsY4EcG+Ty/wrfZcxpQ3mximWM7ZfoYlzZ8NBh4s1XTPuqbl5efK64TEuPgNWBMKsm5Gc2d8H6hoDpLqAOELGl2/xlvWf2CovLH/KPj8xrSwAgOS9jL4r/EEMdXYb705YMMBudu78gooatU9EpVl+1I2MCP2AW0ZJWrcSwYMqxo9yo7H6coyBRlmTxP97PlELXoqXLfufsfFBjZ0eFycndG5A0YHeue82uLF5fIHGpcTjqNzLF0PXuJoS9xVkGx3X7p+dzmRE4rp/swGyKCqbXvgldPRycuj7GSk3r8HLSfzjqHyThnDqMECA==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:412578375350:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_success(revoke_api_key_mock):
    client = MagicMock()
    revoke_api_key_mock.return_value = "revoked"
    payload = mock_api_key_detected()
    blocks = api_key_detected.handle_api_key_detected(payload, client)
    assert any(
        "successfully revoked" in b["text"]["text"] for b in blocks if "text" in b
    )


@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_not_found(revoke_api_key_mock):
    client = MagicMock()
    revoke_api_key_mock.return_value = "not_found"
    payload = mock_api_key_detected()
    blocks = api_key_detected.handle_api_key_detected(payload, client)
    assert any("was not found" in b["text"]["text"] for b in blocks if "text" in b)


@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_failure(revoke_api_key_mock):
    client = MagicMock()
    revoke_api_key_mock.return_value = "error"
    payload = mock_api_key_detected()
    blocks = api_key_detected.handle_api_key_detected(payload, client)
    assert any(
        "could not be revoked" in b["text"]["text"] for b in blocks if "text" in b
    )


def test_api_key_detected_matcher():
    payload = mock_api_key_detected()
    # parsed_message is not used in matcher
    assert api_key_detected.is_api_key_detected(payload, None)


@patch(
    "modules.webhooks.patterns.aws_sns_notification.api_key_detected.send_message_to_notify_channel"
)
@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_sends_message(mock_revoke, mock_send):
    client = MagicMock()
    mock_revoke.return_value = "revoked"
    payload = mock_api_key_detected()
    api_key_detected.handle_api_key_detected(payload, client)
    mock_send.assert_called_once()
