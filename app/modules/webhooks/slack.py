from integrations.slack.users import (
    replace_users_emails_in_dict,
    replace_users_emails_with_mention,
)
from models.webhooks import WebhookPayload


def map_emails_to_slack_users(webhook_payload: WebhookPayload) -> WebhookPayload:
    """Replace email addresses in a Slack webhook payload's 'blocks' or top-level 'text'
    with Slack user mentions when resolvable; return the modified payload."""
    if webhook_payload.text:
        webhook_payload.text = replace_users_emails_with_mention(webhook_payload.text)
    if webhook_payload.blocks:
        webhook_payload.blocks = replace_users_emails_in_dict(webhook_payload.blocks)
    return webhook_payload
