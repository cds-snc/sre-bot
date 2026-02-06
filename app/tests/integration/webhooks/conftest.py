"""Webhook integration test fixtures and payloads.

Provides:
- Test payloads for all webhook types (SNS, simple text, access request, generic)
- Webhook ID fixtures
- Mock database lookups for webhook validation
"""

import pytest
from unittest.mock import MagicMock, PropertyMock


# ============================================================================
# Test Payloads
# ============================================================================


@pytest.fixture
def webhook_id():
    """Standard webhook ID for testing."""
    return "ed44d4a4-ec32-4210-bca2-a98305503b04"


@pytest.fixture
def webhook_record():
    """Standard webhook database record."""
    return {
        "id": {"S": "ed44d4a4-ec32-4210-bca2-a98305503b04"},
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "alert"},
        "active": {"BOOL": True},
    }


# SNS Payloads
@pytest.fixture
def sns_cloudwatch_alarm_payload():
    """AWS SNS CloudWatch alarm notification payload.

    This payload matches the AwsSnsPayload type and exercises the
    SNS notification handler path that previously accessed request.state.bot.
    """
    return {
        "Type": "Notification",
        "MessageId": "12345",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        "Subject": "ALARM: Test CloudWatch Alarm",
        "Message": (
            '{"AlarmName":"TestAlarm",'
            '"AlarmArn":"arn:aws:cloudwatch:us-east-1:123456789012:alarm:TestAlarm",'
            '"AWSAccountId":"123456789012",'
            '"NewStateValue":"ALARM",'
            '"OldStateValue":"OK",'
            '"NewStateReason":"Threshold crossed: 1.0 (2024-02-06 17:46:22 UTC)",'
            '"AlarmDescription":"Test alarm description"}'
        ),
        "Timestamp": "2026-02-06T17:46:22.090Z",
        "SignatureVersion": "1",
        "Signature": "test-signature-base64",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService.pem",
    }


@pytest.fixture
def sns_budget_notification_payload():
    """AWS SNS budget notification payload."""
    return {
        "Type": "Notification",
        "MessageId": "budget-123",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:BudgetNotification",
        "Subject": "Budget Alert",
        "Message": "AWS Budget Notification: Your monthly budget has exceeded 80%",
        "Timestamp": "2026-02-06T17:46:22.090Z",
        "SignatureVersion": "1",
        "Signature": "test-signature",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService.pem",
    }


@pytest.fixture
def sns_subscription_confirmation_payload():
    """AWS SNS subscription confirmation payload.

    This is a special SNS type that confirms webhook subscription.
    """
    return {
        "Type": "SubscriptionConfirmation",
        "MessageId": "sub-123",
        "Token": "test-token",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        "Message": "You have chosen to subscribe to the topic...",
        "SubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription&...",
        "Timestamp": "2026-02-06T17:46:22.090Z",
        "SignatureVersion": "1",
        "Signature": "test-signature",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService.pem",
    }


# Simple Text Payloads
@pytest.fixture
def simple_text_payload():
    """Generic simple text payload."""
    return {"text": "Simple webhook message"}


@pytest.fixture
def upptime_status_payload():
    """Upptime status check webhook payload."""
    return {
        "text": "🟥 API Server (https://api.example.com/) is **down** : https://github.com/example/status/issues/123"
    }


# Access Request Payloads
@pytest.fixture
def access_request_payload():
    """AWS access request payload."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    return {
        "account": "ExampleAccount",
        "reason": "Testing access request webhook",
        "startDate": now.isoformat(),
        "endDate": (now + timedelta(hours=2)).isoformat(),
    }


# Generic Webhook Payloads
@pytest.fixture
def generic_webhook_payload():
    """Generic webhook payload (basic WebhookPayload)."""
    return {"text": "Generic webhook test", "channel": "test-channel"}


# ============================================================================
# Parameterized Payload Fixture
# ============================================================================


@pytest.fixture(
    params=[
        ("sns_cloudwatch_alarm", "sns_cloudwatch_alarm_payload"),
        ("sns_budget", "sns_budget_notification_payload"),
        ("sns_subscription", "sns_subscription_confirmation_payload"),
        ("simple_text", "simple_text_payload"),
        ("upptime", "upptime_status_payload"),
        ("access_request", "access_request_payload"),
        ("generic_webhook", "generic_webhook_payload"),
    ]
)
def webhook_payload_variety(request):
    """Parameterized fixture providing all webhook payload types.

    Use this to test that all webhook payload types are handled without crashes.

    Returns:
        tuple: (payload_type_name, payload_dict)
    """
    payload_type_name, fixture_name = request.param
    payload = request.getfixturevalue(fixture_name)
    return payload_type_name, payload


# ============================================================================
# Database Mocks
# ============================================================================


@pytest.fixture
def mock_webhook_lookup(monkeypatch):
    """Mock webhook database lookup to return valid webhook record.

    This prevents actual DynamoDB calls during webhook tests.
    """
    mock = MagicMock()
    mock.return_value = {
        "id": {"S": "ed44d4a4-ec32-4210-bca2-a98305503b04"},
        "channel": {"S": "test-channel"},
        "hook_type": {"S": "alert"},
        "active": {"BOOL": True},
    }

    monkeypatch.setattr(
        "modules.slack.webhooks.get_webhook",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_webhook_increment(monkeypatch):
    """Mock webhook invocation counter increment.

    This prevents actual DynamoDB writes during webhook tests.
    """
    mock = MagicMock()
    mock.return_value = None

    monkeypatch.setattr(
        "modules.slack.webhooks.increment_invocation_count",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_sns_signature_validation_disabled(monkeypatch):
    """Disable SNS signature validation to allow test payloads.

    In non-production environments, SNS signature validation is skipped.
    This ensures test payloads with fake signatures work.

    Since is_production is a read-only property, we monkeypatch the
    entire settings object in the aws_sns module.
    """
    mock_settings = MagicMock()
    # Make is_production return False so signature validation is skipped
    type(mock_settings).is_production = PropertyMock(return_value=False)

    monkeypatch.setattr(
        "modules.webhooks.aws_sns.settings",
        mock_settings,
    )

    return mock_settings
