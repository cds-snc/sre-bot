from models.webhooks import WebhookPayload
from modules.webhooks.simple_text import SimpleTextPattern


def handle_upptime_payload(text: str) -> WebhookPayload:
    """
    Wrapper to call the Upptime alert handler.
    """
    text_lower = text.lower()

    # Check for down status indicators
    if (
        ":large_red_square:" in text
        or "🟥" in text
        or "**down**" in text
        or "down" in text_lower
    ):
        header_text = "🚨 Service Down Alert"
    # Check for recovery status indicators
    elif (
        ":large_green_square:" in text
        or "🟩" in text
        or "back up" in text_lower
        or "is back up" in text_lower
        or "performance has improved" in text_lower
    ):
        header_text = "✅ Service Recovered"
    # Check for degraded status indicators
    elif (
        ":large_yellow_square:" in text
        or "🟨" in text
        or "degraded performance" in text_lower
        or "experiencing degraded performance" in text_lower
    ):
        header_text = "⚠️ Service Degraded"
    else:
        header_text = "📈 Web Application Status Changed!"
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{header_text}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{text}",
            },
        },
    ]
    return WebhookPayload(blocks=blocks)


def is_upptime_pattern(text: str) -> bool:
    """
    Check if the text matches Upptime alert patterns.
    Looks for emoji indicators and status keywords.
    """
    # Check for Upptime emoji indicators
    emoji_indicators = [
        ":large_red_square:",
        ":large_green_square:",
        ":large_yellow_square:",
        "🟥",
        "🟩",
        "🟨",
    ]

    # Check for status keywords that indicate Upptime alerts
    status_keywords = [
        "down",
        "is back up",
        "back up",
        "experiencing degraded performance",
        "degraded performance",
        "performance has improved",
    ]

    has_emoji = any(emoji in text for emoji in emoji_indicators)
    has_status = any(
        keyword in text.lower() for keyword in [k.lower() for k in status_keywords]
    )

    # Must have both an emoji indicator AND a status keyword to be considered Upptime
    return has_emoji and has_status


UPPTIME_HANDLER: SimpleTextPattern = SimpleTextPattern(
    name="upptime_monitoring",
    match_type="callable",
    pattern="modules.webhooks.patterns.simple_text.upptime.is_upptime_pattern",
    handler="modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
    priority=10,
    enabled=True,
)
