import json
from unittest.mock import MagicMock

from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import (
    NOTIFICATION_HANDLERS,
    find_matching_handler,
    register_notification_pattern,
)
from modules.webhooks.patterns.aws_sns_notification import dynamodb_access


def dynamodb_access_message():
    return (
        "Unexpected DynamoDB access in secret-production\n"
        "Event: Scan\n"
        "Principal: arn:aws:sts::637287734259:assumed-role/AWSReservedSSO_AWSAdministratorAccess_187a62b857c9ffd5/max.neuvians@cds-snc.ca\n"
        "Source IP: 142.114.34.223\n"
        "Region: ca-central-1\n"
        "Resource: arn:aws:dynamodb:ca-central-1:637287734259:table/secret-production-table\n"
        "Time: 2026-06-05T15:51:53Z"
    )


def mock_dynamodb_access():
    return AwsSnsPayload(
        Type="Notification",
        MessageId="587dbeca-445c-571c-b1f3-dc56b6bad9aa",
        TopicArn="arn:aws:sns:ca-central-1:637287734259:internal-sre-alert",
        Message=json.dumps(dynamodb_access_message()),
        Timestamp="2026-06-05T15:52:06.262Z",
        SignatureVersion="1",
        Signature="signature",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-7506a1e35b36ef5a444dd1a8e7cc3ed8.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe",
    )


def block_text(blocks):
    text_parts = []
    for block in blocks:
        text = block.get("text")
        if isinstance(text, dict):
            text_parts.append(text.get("text", ""))
    return "\n".join(text_parts)


def test_dynamodb_access_handler_formats_message():
    client = MagicMock()
    payload = mock_dynamodb_access()

    blocks = dynamodb_access.handle_dynamodb_access(payload, client)
    rendered_text = block_text(blocks)

    assert blocks[1]["text"]["text"] == "Unexpected DynamoDB access in secret-production"
    assert "Scan" in rendered_text
    assert "arn:aws:sts::637287734259:assumed-role" in rendered_text
    assert "142.114.34.223" in rendered_text
    assert "ca-central-1" in rendered_text
    assert "secret-production-table" in rendered_text
    assert "2026-06-05T15:51:53Z" in rendered_text


def test_dynamodb_access_matcher_accepts_json_encoded_message():
    payload = mock_dynamodb_access()
    parsed_message = json.loads(payload.Message)

    assert dynamodb_access.is_dynamodb_access(payload, parsed_message)


def test_dynamodb_access_matcher_accepts_plain_message():
    payload = mock_dynamodb_access()
    payload.Message = dynamodb_access_message()

    assert dynamodb_access.is_dynamodb_access(payload, payload.Message)


def test_dynamodb_access_matcher_rejects_other_messages():
    payload = AwsSnsPayload(Message="An IAM User was created in an Account")

    assert not dynamodb_access.is_dynamodb_access(payload, payload.Message)


def test_dynamodb_access_registry_pattern_matches():
    original_handlers = list(NOTIFICATION_HANDLERS)
    try:
        NOTIFICATION_HANDLERS.clear()
        register_notification_pattern(dynamodb_access.DYNAMODB_ACCESS_HANDLER)
        payload = mock_dynamodb_access()
        parsed_message = json.loads(payload.Message)

        matched_handler = find_matching_handler(payload, parsed_message)

        assert matched_handler is not None
        assert matched_handler.name == "dynamodb_access"
    finally:
        NOTIFICATION_HANDLERS.clear()
        NOTIFICATION_HANDLERS.extend(original_handlers)
