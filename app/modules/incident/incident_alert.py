from integrations.sentinel import log_to_sentinel
from modules.incident import incident
from modules.slack import webhooks
from core.logging import get_module_logger

logger = get_module_logger()


def handle_incident_action_buttons(client, ack, body):
    delete_block = False
    name = body["actions"][0]["name"]
    value = body["actions"][0]["value"]
    user = body["user"]["id"]
    if name == "call-incident":
        incident.open_create_incident_modal(client, ack, {"text": value}, body)
        log_to_sentinel("call_incident_button_pressed", body)
    elif name == "ignore-incident":
        ack()
        webhooks.increment_acknowledged_count(value)
        attachments = body["original_message"]["attachments"]
        msg = (
            f"🙈  <@{user}> has acknowledged and ignored the incident.\n"
            f"<@{user}> a pris connaissance et ignoré l'incident."
        )
        # if the last attachment is a preview from a link, switch the places of the last 2 attachments so that the incident buttons can be appended properly
        if len(attachments) > 1:
            if "app_unfurl_url" in attachments[-1]:
                attachments[-2], attachments[-1] = attachments[-1], attachments[-2]
        attachments[-1] = {
            "color": "3AA3E3",
            "fallback": f"{msg}",
            "text": f"{msg}",
        }
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
