import json
from unittest.mock import MagicMock

from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import process_aws_notification_payload
from modules.webhooks.patterns.aws_sns_notification import blazer_check

PLAIN_TEXT_MESSAGE = "Check Passing: tester-jumana\nhttp://localhost:8080/queries/62"


def make_payload(message: str, subject: str | None = "Blazer check") -> AwsSnsPayload:
    return AwsSnsPayload(
        Type="Notification",
        TopicArn="arn:aws:sns:ca-central-1:123456789012:alert-general",
        Subject=subject,
        Message=message,
    )


def block_texts(blocks: list[dict]) -> list[str]:
    return [b["text"]["text"] for b in blocks if "text" in b]


def test_blazer_check_matcher_accepts_blazer_subject():
    assert blazer_check.is_blazer_check_notification(make_payload(PLAIN_TEXT_MESSAGE), PLAIN_TEXT_MESSAGE)


def test_blazer_check_matcher_accepts_json_marked_as_blazer():
    message = {"source": "blazer", "query_name": "q"}
    payload = make_payload(json.dumps(message), subject=None)
    assert blazer_check.is_blazer_check_notification(payload, message)


def test_blazer_check_matcher_rejects_other_notifications():
    payload = make_payload("AWS Budget Notification", subject="AWS Budgets: over threshold")
    assert not blazer_check.is_blazer_check_notification(payload, "AWS Budget Notification")
    assert not blazer_check.is_blazer_check_notification(payload, {"AlarmArn": "arn"})


def test_blazer_check_handler_formats_plain_text_message():
    blocks = blazer_check.handle_blazer_check(make_payload(PLAIN_TEXT_MESSAGE), MagicMock())

    assert blocks[2] == {"type": "header", "text": {"type": "plain_text", "text": "tester-jumana"}}
    assert "*<http://localhost:8080/queries/62|✅ Blazer Check>*" in block_texts(blocks)
    assert blocks[-1] == {"type": "section", "fields": [{"type": "mrkdwn", "text": "*State:*\n Passing"}]}


def test_blazer_check_handler_uses_failing_emoji_and_keeps_detail_lines():
    message = "Check Failing: tester-jumana\n1 row\nhttp://localhost:8080/queries/62"
    blocks = blazer_check.handle_blazer_check(make_payload(message), MagicMock())

    assert any("🔥" in text for text in block_texts(blocks))
    assert "1 row" in block_texts(blocks)


def test_blazer_check_handler_does_not_treat_detail_as_link_when_no_url():
    blocks = blazer_check.handle_blazer_check(make_payload("Check Failing: q\n3 rows"), MagicMock())

    assert "3 rows" in block_texts(blocks)
    assert "*🔥 Blazer Check*" in block_texts(blocks)


def test_blazer_check_handler_formats_failing_checks_summary():
    message = "2 Checks Failing\n<http://x/queries/1|a> failing\n<http://x/queries/2|b> error"
    blocks = blazer_check.handle_blazer_check(make_payload(message), MagicMock())

    assert blocks[2]["text"]["text"] == "2 Checks Failing"
    assert "<http://x/queries/1|a> failing\n<http://x/queries/2|b> error" in block_texts(blocks)
    assert not any("fields" in b for b in blocks)


def test_blazer_check_handler_includes_description_from_json_message():
    message = json.dumps(
        {
            "source": "blazer",
            "query_name": "stuck notifications",
            "state": "Failing",
            "query_url": "https://blazer.example/queries/62",
            "description": "Notifications stuck in sending for over 10 minutes",
            "message": "4 rows",
        }
    )
    blocks = blazer_check.handle_blazer_check(make_payload(message, subject=None), MagicMock())

    texts = block_texts(blocks)
    assert blocks[2]["text"]["text"] == "stuck notifications"
    assert "Notifications stuck in sending for over 10 minutes" in texts
    assert "4 rows" in texts
    assert "*<https://blazer.example/queries/62|🔥 Blazer Check>*" in texts


def test_blazer_check_handler_escapes_slack_control_characters_in_json_fields():
    message = json.dumps({"source": "blazer", "query_name": "q", "description": "<!channel> a & b"})
    blocks = blazer_check.handle_blazer_check(make_payload(message), MagicMock())

    assert "&lt;!channel&gt; a &amp; b" in block_texts(blocks)


def test_blazer_check_handler_truncates_title_to_slack_header_limit():
    blocks = blazer_check.handle_blazer_check(make_payload("Check Failing: " + "x" * 400), MagicMock())

    assert len(blocks[2]["text"]["text"]) == blazer_check.HEADER_MAX_LENGTH


def test_blazer_check_handler_handles_empty_message():
    blocks = blazer_check.handle_blazer_check(make_payload(""), MagicMock())

    assert blocks[2]["text"]["text"] == "Blazer check"


def test_blazer_check_notification_is_routed_to_blazer_handler_end_to_end():
    blocks = process_aws_notification_payload(make_payload(PLAIN_TEXT_MESSAGE), MagicMock())

    assert blocks
    assert blocks[2]["text"]["text"] == "tester-jumana"
