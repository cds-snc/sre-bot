import os
from unittest.mock import MagicMock, patch

import pytest

from contracts.configuration import HostInfo, install_host_info
from modules.webhooks.patterns.aws_sns_notification import api_key_detected
from modules.webhooks.patterns.aws_sns_notification.settings import NotifyApiKeyLeakSettings


def _use_settings(monkeypatch, channel_id="C0123456789", oncall_group_id="S0123456789"):
    """Replace the slice getter with a slice built from explicit values (the ci files are installed)."""
    settings = NotifyApiKeyLeakSettings(channel_id=channel_id, oncall_group_id=oncall_group_id)
    monkeypatch.setattr(api_key_detected, "get_notify_api_key_leak_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def configured_notify_settings(monkeypatch):
    """Provide the Notify channel and Slack user-group ID for handler tests."""
    return _use_settings(monkeypatch)


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
    assert any("successfully revoked" in b["text"]["text"] for b in blocks if "text" in b)


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
    assert any("could not be revoked" in b["text"]["text"] for b in blocks if "text" in b)


def test_api_key_detected_matcher():
    payload = mock_api_key_detected()
    # parsed_message is not used in matcher
    assert api_key_detected.is_api_key_detected(payload, None)


@patch("modules.webhooks.patterns.aws_sns_notification.api_key_detected.send_message_to_notify_channel")
@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_sends_message(mock_revoke, mock_send):
    client = MagicMock()
    mock_revoke.return_value = "revoked"
    payload = mock_api_key_detected()
    api_key_detected.handle_api_key_detected(payload, client)
    mock_send.assert_called_once()


@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_mentions_configured_oncall_group(revoke_api_key_mock):
    """The notification includes the configured Slack user-group mention after the repository."""
    revoke_api_key_mock.return_value = "revoked"

    blocks = api_key_detected.handle_api_key_detected(mock_api_key_detected(), MagicMock())

    message = blocks[2]["text"]["text"]
    assert message.endswith("(cc <!subteam^S0123456789|notify-oncall>)")


@patch("integrations.notify.revoke_api_key")
def test_api_key_detected_handler_requires_oncall_group_id(revoke_api_key_mock, monkeypatch):
    """The handler rejects delivery when the Slack user-group ID is not configured."""
    revoke_api_key_mock.return_value = "revoked"
    _use_settings(monkeypatch, oncall_group_id="")

    with pytest.raises(ValueError, match="notify_api_key_leak.oncall_group_id is not set"):
        api_key_detected.handle_api_key_detected(mock_api_key_detected(), MagicMock())

    revoke_api_key_mock.assert_not_called()


@pytest.mark.parametrize("environment", ["local", "ci", "production"])
def test_send_message_posts_to_configured_channel_in_every_environment(environment):
    """The channel comes from the settings alone; the environment does not pick a different one."""
    install_host_info(HostInfo(environment=environment, git_sha="test-sha", public_base_url="http://127.0.0.1:8000"))
    client = MagicMock()

    api_key_detected.send_message_to_notify_channel(client, [{"type": "divider"}])

    client.chat_postMessage.assert_called_once_with(channel="C0123456789", blocks=[{"type": "divider"}])


def test_send_message_requires_channel_id(monkeypatch):
    """An empty channel id raises instead of posting nowhere."""
    _use_settings(monkeypatch, channel_id="")
    client = MagicMock()

    with pytest.raises(ValueError, match="notify_api_key_leak.channel_id is not set"):
        api_key_detected.send_message_to_notify_channel(client, [])

    client.chat_postMessage.assert_not_called()
