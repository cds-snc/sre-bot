"""Pins how ``POST /hook/{webhook_id}`` handles AWS SNS messages, through the production ASGI app.

Signatures are real: a test RSA key signs each message and the SNS signing-certificate and
``SubscribeURL`` hosts are answered over a faked HTTP edge, so the route's own validation runs.
The webhook record store, the Slack Web API and the GC Notify API are faked at their external
edges. Layout the bot builds for each notification kind is asserted by identifying facts (the
alarm name and state, the budget figure, the repository, the mention), not as a golden layout.
``test_legacy_only_webhook_*`` tests pin behaviour the webhooks rebuild ends and are deleted by
the task named in each docstring.
"""

import json
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes

from integrations.notify.settings import get_notify_settings
from tests.integration.legacy_surface.conftest import (
    NOTIFY_LEAK_CHANNEL_ID,
    NOTIFY_ONCALL_GROUP_ID,
    SNS_TOPIC_ARN,
    SnsEdges,
    WebhookSurface,
)

pytestmark = pytest.mark.integration

ACCOUNT_ID = "123456789012"
NOTIFY_API_URL = "https://notify.example.test"
VALIDATION_FAILED = {"detail": "Failed to validate AWS event message"}

SERVICE_ID = "11111111-2222-3333-4444-555555555555"
KEY_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
LEAKED_REPOSITORY = "https://github.com/example-org/example-repo/blob/main/.env"
LEAKED_KEY = f"gcntfy-pipeline-key-{SERVICE_ID}-{KEY_ID}"
LEAK_MESSAGE = (
    f"API Key with value token='{LEAKED_KEY}', type='cds-tokens' and source='github' "
    f"has been detected in url='{LEAKED_REPOSITORY}'!"
)


def blocks_text(post: dict[str, Any]) -> str:
    """The posted blocks as one searchable string, for identifying facts."""
    return json.dumps(post["blocks"], ensure_ascii=False)


NOTIFICATIONS: list[Any] = [
    pytest.param(
        None,
        json.dumps(
            {
                "AlarmName": "checkout-5xx-rate",
                "AlarmArn": f"arn:aws:cloudwatch:ca-central-1:{ACCOUNT_ID}:alarm:checkout-5xx-rate",
                "AWSAccountId": ACCOUNT_ID,
                "NewStateValue": "ALARM",
                "OldStateValue": "OK",
                "NewStateReason": "Threshold crossed: 7 datapoints were above 5",
                "AlarmDescription": "Checkout is returning server errors",
            }
        ),
        ["checkout-5xx-rate", "ALARM", "ca-central-1", "Threshold crossed"],
        id="cloudwatch-alarm",
    ),
    pytest.param(
        "AWS Budget Notification",
        "AWS Budget Notification: actual spend has passed 85% of the monthly budget",
        ["85%", ACCOUNT_ID],
        id="budget",
    ),
    pytest.param(
        None,
        json.dumps(
            {
                "ExecutionArn": f"arn:aws:states:ca-central-1:{ACCOUNT_ID}:execution:aft-account-provisioning:run-42",
                "StateMachineArn": f"arn:aws:states:ca-central-1:{ACCOUNT_ID}:stateMachine:aft-account-provisioning",
                "Status": "FAILED",
                "Name": "run-42",
                "Error": "States.TaskFailed",
                "Cause": "the account request was rejected",
            }
        ),
        ["aft-account-provisioning", "FAILED", "run-42", "the account request was rejected"],
        id="step-functions",
    ),
    pytest.param(
        None,
        "Unexpected DynamoDB access\nEvent: Scan\nPrincipal: arn:aws:iam::123456789012:user/mallory\nSource IP: 198.51.100.4",
        ["Unexpected DynamoDB access", "Scan", "user/mallory", "198.51.100.4"],
        id="dynamodb-access",
    ),
    pytest.param(
        None,
        json.dumps(
            {
                "detail": {
                    "service": "ABUSE",
                    "eventTypeCode": "AWS_ABUSE_PII_REPORT",
                    "eventDescription": [{"latestDescription": "Your account may be hosting exposed personal data"}],
                }
            }
        ),
        ["AWS ABUSE PII REPORT", "exposed personal data", ACCOUNT_ID],
        id="abuse",
    ),
    pytest.param(
        "Blazer check",
        "Check Failing: slow checkout query\nhttps://blazer.example.test/queries/7",
        ["slow checkout query", "Failing", "https://blazer.example.test/queries/7"],
        id="blazer-check",
    ),
    pytest.param(
        None,
        "AUTO-MITIGATED: security group: sg-0abc123 that was added by "
        f"arn:aws:sts::{ACCOUNT_ID}:assumed-role/Admin/alice: "
        '[{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": []}]',
        ["22", "alice", "sg-0abc123", ACCOUNT_ID],
        id="auto-mitigation",
    ),
    pytest.param(
        None,
        f"IAM User: svc-ci\nActor: arn:aws:sts::{ACCOUNT_ID}:assumed-role/Admin/alice",
        ["svc-ci", "alice", ACCOUNT_ID],
        id="iam-user",
    ),
]


@pytest.fixture
def notify_revocation(monkeypatch: pytest.MonkeyPatch, sns: SnsEdges) -> SnsEdges:
    """Configure the GC Notify tenant the API-key-leak response revokes keys through, over the faked HTTP edge."""
    monkeypatch.setenv("NOTIFY__TENANT", json.dumps({"api_url": NOTIFY_API_URL}))
    monkeypatch.setenv("NOTIFY__SRE_USER_NAME", "sre-bot-test")
    monkeypatch.setenv("NOTIFY__SRE_CLIENT_SECRET", "x" * 32)
    get_notify_settings.cache_clear()
    return sns


def test_webhook_route_sns_subscription_confirmation_is_confirmed_and_announced_in_ops(
    webhook_surface: WebhookSurface, sns: SnsEdges
) -> None:
    """A signed SubscriptionConfirmation makes the bot call its SubscribeURL, tells the ops channel and posts nothing else."""
    webhook_surface.records.seed()

    response = webhook_surface.post(sns.signer.message("SubscriptionConfirmation", message="You have chosen to subscribe"))

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(sns.subscribe_requests) == 1
    [ops_message] = webhook_surface.ops_messages
    assert SNS_TOPIC_ARN in ops_message
    assert webhook_surface.webhook_posts == []


def test_webhook_route_sns_unsubscribe_confirmation_is_announced_in_ops_only(
    webhook_surface: WebhookSurface, sns: SnsEdges
) -> None:
    """A signed UnsubscribeConfirmation tells the ops channel which topic left, without calling any URL or posting."""
    webhook_surface.records.seed()

    response = webhook_surface.post(sns.signer.message("UnsubscribeConfirmation", message="You have chosen to unsubscribe"))

    assert response.status_code == 200
    [ops_message] = webhook_surface.ops_messages
    assert SNS_TOPIC_ARN in ops_message
    assert sns.subscribe_requests == []
    assert webhook_surface.webhook_posts == []


@pytest.mark.parametrize(("subject", "message", "facts"), NOTIFICATIONS)
def test_webhook_route_sns_notification_is_posted_as_a_message_naming_its_facts(
    webhook_surface: WebhookSurface, sns: SnsEdges, subject: str | None, message: str, facts: list[str]
) -> None:
    """Each recognised notification kind is posted to the record's channel as blocks naming the event's identifying facts."""
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post(sns.signer.message(message=message, subject=subject))

    assert response.status_code == 200
    [post] = webhook_surface.webhook_posts
    text = blocks_text(post)
    for fact in facts:
        assert fact in text
    assert webhook_surface.sentinel_event_names() == ["webhook_sent"]


def test_webhook_route_sns_notification_on_an_alert_webhook_carries_the_incident_buttons(
    webhook_surface: WebhookSurface, sns: SnsEdges
) -> None:
    """An alert webhook gets the incident buttons on an SNS notification too; ``call-incident`` carries no text, as the post has none."""
    webhook_surface.records.seed(hook_type="alert")

    webhook_surface.post(
        sns.signer.message(message="AWS Budget Notification: spend passed 85%", subject="AWS Budget Notification")
    )

    [post] = webhook_surface.webhook_posts
    assert post["attachments"][-1]["callback_id"] == "handle_incident_action_buttons"
    assert [action["name"] for action in post["attachments"][-1]["actions"]] == ["call-incident", "ignore-incident"]


@pytest.mark.parametrize(
    ("revocation_status", "outcome_fact"),
    [(201, "successfully revoked"), (200, "not found"), (500, "could not be revoked")],
    ids=["revoked", "not-found", "error"],
)
def test_webhook_route_sns_api_key_leak_is_revoked_and_announced_in_both_channels(
    webhook_surface: WebhookSurface,
    notify_revocation: SnsEdges,
    revocation_status: int,
    outcome_fact: str,
) -> None:
    """A leaked Notify API key is sent to Notify for revocation and reported to the webhook channel and the leak channel.

    The report names the key, its service, the repository and the revocation outcome, and mentions
    the on-call group from the typed settings slice.
    """
    webhook_surface.records.seed(hook_type="info")
    revoke = notify_revocation.http.post(f"{NOTIFY_API_URL}/sre-tools/api-key-revoke", status_code=revocation_status)

    response = webhook_surface.post(notify_revocation.signer.message(message=LEAK_MESSAGE))

    assert response.status_code == 200
    assert revoke.call_count == 1
    assert revoke.last_request.json() == {
        "token": LEAKED_KEY,
        "type": "cds-tokens",
        "url": LEAKED_REPOSITORY,
        "source": "github",
    }
    [post] = webhook_surface.webhook_posts
    [leak_post] = webhook_surface.channel_posts(NOTIFY_LEAK_CHANNEL_ID)
    assert leak_post["blocks"] == post["blocks"]
    text = blocks_text(post)
    for fact in ("pipeline-key", SERVICE_ID, LEAKED_REPOSITORY, f"<!subteam^{NOTIFY_ONCALL_GROUP_ID}|", outcome_fact):
        assert fact in text


@pytest.mark.parametrize(
    "tampering",
    [
        pytest.param({"Message": "a different message than the one signed"}, id="signature-does-not-match"),
        pytest.param({"SigningCertURL": "https://certs.attacker.example.test/cert.pem"}, id="certificate-url-not-aws"),
        pytest.param({"SignatureVersion": "3"}, id="unknown-signature-version"),
        pytest.param({"Type": "Subscribe"}, id="unknown-message-type"),
    ],
)
def test_webhook_route_sns_message_failing_validation_answers_500_and_posts_nothing(
    webhook_surface: WebhookSurface, sns: SnsEdges, tampering: dict[str, str]
) -> None:
    """A message that fails signature, certificate, version or type validation answers a generic 500.

    The ops channel is told, the webhook channel gets nothing and the response never echoes the
    message. Validation reads the same fields in the same order whatever the failure, so each
    case alters one field of an otherwise valid signed message.
    """
    webhook_surface.records.seed(hook_type="info")
    message = {
        **sns.signer.message(message="AWS Budget Notification: spend passed 85%", subject="AWS Budget Notification"),
        **tampering,
    }

    response = webhook_surface.post(message)

    assert response.status_code == 500
    assert response.json() == VALIDATION_FAILED
    assert len(webhook_surface.ops_messages) == 1
    assert webhook_surface.webhook_posts == []


def test_webhook_route_sns_message_without_a_signature_answers_500_as_unparseable(
    webhook_surface: WebhookSurface, sns: SnsEdges
) -> None:
    """An SNS-shaped message with no Signature cannot be parsed: a generic 500, an ops message and no post."""
    webhook_surface.records.seed(hook_type="info")
    message = {key: value for key, value in sns.signer.message(message="spend passed 85%").items() if key != "Signature"}

    response = webhook_surface.post(message)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to parse AWS event message"}
    assert len(webhook_surface.ops_messages) == 1
    assert webhook_surface.webhook_posts == []


def test_webhook_route_sns_message_with_the_slack_bot_absent_answers_503(webhook_surface: WebhookSurface, sns: SnsEdges) -> None:
    """With no Slack bot on the app an SNS message answers 503 and nothing is confirmed or posted."""
    webhook_surface.records.seed()
    webhook_surface.remove_bot()

    response = webhook_surface.post(sns.signer.message("SubscriptionConfirmation", message="subscribe"))

    assert response.status_code == 503
    assert response.json() == {"detail": "Slack bot not initialized"}
    assert sns.subscribe_requests == []
    assert webhook_surface.all_posts == []


def test_legacy_only_webhook_sns_signature_version_2_is_rejected_with_500(webhook_surface: WebhookSurface, sns: SnsEdges) -> None:
    """A correctly SHA256-signed SignatureVersion 2 message is rejected: the validator accepts only version 1.

    AWS signs with SHA256 when the topic's SignatureVersion attribute is 2, so such a topic
    cannot deliver today. Ended by TASK-37.2, whose validation accepts both versions (the
    webhooks architecture review rules on it).
    """
    webhook_surface.records.seed(hook_type="info")
    message = sns.signer.message(
        message="AWS Budget Notification: spend passed 85%",
        subject="AWS Budget Notification",
        signature_version="2",
        digest=hashes.SHA256(),
    )

    response = webhook_surface.post(message)

    assert response.status_code == 500
    assert response.json() == VALIDATION_FAILED
    assert webhook_surface.webhook_posts == []


@pytest.mark.parametrize(
    "message",
    [
        pytest.param("a message no pattern recognises", id="unrecognised"),
        pytest.param(json.dumps({"previousBudgetLimit": 100, "currentBudgetLimit": 120}), id="budget-auto-adjustment-not-posted"),
    ],
)
def test_legacy_only_webhook_sns_notification_with_nothing_to_post_answers_400(
    webhook_surface: WebhookSurface, sns: SnsEdges, message: str
) -> None:
    """A valid SNS notification that no pattern renders, or one deliberately not posted, answers 400 and posts nothing.

    Ended by TASK-37.2, whose generic fallback accepts a notification it cannot render, so the
    sender gets 2xx instead of a failure SNS retries.
    """
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post(sns.signer.message(message=message))

    assert response.status_code == 400
    assert response.json() == {"detail": "Empty AWS SNS Notification message"}
    assert webhook_surface.webhook_posts == []


def test_legacy_only_webhook_unrecognised_sns_notification_is_reported_to_ops(
    webhook_surface: WebhookSurface, sns: SnsEdges
) -> None:
    """An SNS notification no pattern recognises is reported to the ops channel with its message text.

    Ended by TASK-37.2, whose generic fallback decides how an unrecognised notification is surfaced.
    """
    webhook_surface.records.seed(hook_type="info")

    webhook_surface.post(sns.signer.message(message="a message no pattern recognises"))

    [ops_message] = webhook_surface.ops_messages
    assert "a message no pattern recognises" in ops_message


def test_legacy_only_webhook_equal_priority_patterns_pick_one_by_import_order(
    webhook_surface: WebhookSurface, sns: SnsEdges
) -> None:
    """A notification matching two equal-priority patterns is rendered by exactly one of them, chosen by import order.

    The patterns are registered by walking a directory at import, so which of two equal-priority
    patterns wins follows the filesystem's listing order; the pin accepts either winner and
    rejects both or neither. Ended by TASK-168's registration rework, which replaces the
    import-time walk with declared sources.
    """
    webhook_surface.records.seed(hook_type="info")
    both = json.dumps(
        {
            "ExecutionArn": f"arn:aws:states:ca-central-1:{ACCOUNT_ID}:execution:aft-sm:run-1",
            "StateMachineArn": f"arn:aws:states:ca-central-1:{ACCOUNT_ID}:stateMachine:aft-sm",
            "Status": "Unexpected DynamoDB access",
            "Name": "run-1",
        }
    )

    response = webhook_surface.post(sns.signer.message(message=both))

    assert response.status_code == 200
    [post] = webhook_surface.webhook_posts
    headers = [block["text"]["text"] for block in post["blocks"] if block["type"] == "header"]
    rendered_by_step_functions = headers == ["aft-sm"]
    rendered_by_dynamodb_access = len(headers) == 1 and headers[0].startswith("{")
    assert rendered_by_step_functions != rendered_by_dynamodb_access
