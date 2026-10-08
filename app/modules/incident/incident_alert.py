from structlog import get_logger

from integrations.sentinel import log_to_sentinel
from modules.incident import incident
from modules.slack import webhooks

logger = get_logger()

# Writable legacy attachment fields; Slack echoes read-only keys (id, app_unfurl_url, from_url, ...) that chat.update rejects.
ALLOWED_ATTACHMENT_KEYS = frozenset(
    {
        "fallback",
        "color",
        "pretext",
        "author_name",
        "author_link",
        "author_icon",
        "title",
        "title_link",
        "text",
        "fields",
        "image_url",
        "thumb_url",
        "footer",
        "footer_icon",
        "ts",
        "mrkdwn_in",
        "blocks",
        "callback_id",
        "actions",
        "attachment_type",
    }
)


def _get_source_alert_metadata(body):
    channel_id = body.get("channel", {}).get("id")
    message_ts = body.get("message_ts")

    container = body.get("container", {})
    if not channel_id:
        channel_id = container.get("channel_id")
    if not message_ts:
        message_ts = container.get("message_ts")

    return {
        "source_channel_id": channel_id,
        "source_message_ts": message_ts,
    }


def handle_incident_action_buttons(client, ack, body):
    delete_block = False
    name = body["actions"][0]["name"]
    value = body["actions"][0]["value"]
    user = body["user"]["id"]
    if name == "call-incident":
        incident.open_create_incident_modal(
            client,
            ack,
            {"text": value, "private_metadata": _get_source_alert_metadata(body)},
            body,
        )
        log_to_sentinel("call_incident_button_pressed", body)
    elif name == "ignore-incident":
        ack()
        webhooks.increment_acknowledged_count(value)
        attachments = body["original_message"]["attachments"]
        msg = f"🙈  <@{user}> has acknowledged and ignored the incident.\n<@{user}> a pris connaissance et ignoré l'incident."
        buttons_index = next(
            (i for i, attachment in enumerate(attachments) if attachment.get("callback_id") == "handle_incident_action_buttons"),
            len(attachments) - 1,
        )
        attachments = [
            {key: val for key, val in attachment.items() if key in ALLOWED_ATTACHMENT_KEYS}
            for i, attachment in enumerate(attachments)
            if i != buttons_index
        ]
        attachments.append(
            {
                "color": "3AA3E3",
                "fallback": f"{msg}",
                "text": f"{msg}",
            }
        )
        body["original_message"]["attachments"] = attachments
        body["original_message"]["channel"] = body["channel"]["id"]

        # rich_text blocks are only available for 1st party Slack clients (meaning Desktop, iOS, Android Slack apps)
        # https://github.com/slackapi/bolt-js/issues/1324
        if "blocks" in body["original_message"]:
            for block in body["original_message"]["blocks"]:
                if "type" in block and block["type"] == "rich_text":
                    delete_block = True

        if delete_block:
            body["original_message"]["blocks"] = []

        logger.info(
            "incident_alert_update_chat",
            channel=body["channel"]["id"],
            message=body["original_message"],
        )
        client.api_call("chat.update", json=body["original_message"])
        log_to_sentinel("ignore_incident_button_pressed", body)
