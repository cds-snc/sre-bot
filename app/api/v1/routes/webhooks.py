import requests  # type: ignore
import json
from fastapi import APIRouter, Request, HTTPException
from models.webhooks import AwsSnsPayload, WebhookPayload
from core.logging import get_module_logger
from api.dependencies.rate_limits import get_limiter
from integrations.sentinel import log_to_sentinel
from modules.slack import webhooks
from server.event_handlers import aws
from server.utils import (
    log_ops_message,
)


logger = get_module_logger()
router = APIRouter(tags=["Access"])
limiter = get_limiter()


@router.post("/hook/{webhook_id}")
@limiter.limit(
    "30/minute"
)  # since some slack channels use this for alerting, we want to be generous with the rate limiting on this one
def handle_webhook(
    webhook_id: str,
    payload: WebhookPayload | str,
    request: Request,
):
    webhook = webhooks.get_webhook(webhook_id)
    webhook_payload = WebhookPayload()
    if webhook:
        hook_type: str = webhook.get("hook_type", {"S": "alert"})["S"]
        # if the webhook is active, then send forward the response to the webhook
        if webhooks.is_active(webhook_id):
            webhooks.increment_invocation_count(webhook_id)
            if isinstance(payload, str):
                processed_payload = handle_string_payload(payload, request)
                if isinstance(processed_payload, dict):
                    return processed_payload
                else:
                    logger.info(
                        "payload_processed",
                        payload=processed_payload,
                        webhook_id=webhook_id,
                    )
                    webhook_payload = processed_payload
            else:
                webhook_payload = payload
            webhook_payload.channel = webhook["channel"]["S"]
            if hook_type == "alert":
                webhook_payload = append_incident_buttons(webhook_payload, webhook_id)
            try:
                webhook_payload_parsed = webhook_payload.model_dump(exclude_none=True)
                request.state.bot.client.api_call(
                    "chat.postMessage", json=webhook_payload_parsed
                )
                log_to_sentinel(
                    "webhook_sent",
                    {"webhook": webhook, "payload": webhook_payload_parsed},
                )
                return {"ok": True}
            except Exception as e:
                logger.exception(
                    "webhook_posting_error",
                    webhook_id=webhook_id,
                    webhook_payload=webhook_payload,
                    error=str(e),
                )
                body = webhook_payload.model_dump(exclude_none=True)
                log_ops_message(
                    request.state.bot.client, f"Error posting message: ```{body}```"
                )
                raise HTTPException(
                    status_code=500, detail="Failed to send message"
                ) from e
        else:
            logger.info(
                "webhook_not_active",
                webhook_id=webhook_id,
                webhook_payload=webhook_payload,
                error="Webhook is not active",
            )
            raise HTTPException(status_code=404, detail="Webhook not active")
    else:
        raise HTTPException(status_code=404, detail="Webhook not found")


def handle_string_payload(
    payload: str,
    request: Request,
) -> WebhookPayload | dict:

    string_payload_type, validated_payload = webhooks.validate_string_payload_type(
        payload
    )
    logger.info(
        "string_payload_type",
        payload=payload,
        string_payload_type=string_payload_type,
        validated_payload=validated_payload,
    )
    match string_payload_type:
        case "WebhookPayload":
            webhook_payload = WebhookPayload(**validated_payload)
        case "AwsSnsPayload":
            awsSnsPayload = aws.validate_sns_payload(
                AwsSnsPayload(**validated_payload),
                request.state.bot.client,
            )
            if awsSnsPayload.Type == "SubscriptionConfirmation":
                requests.get(awsSnsPayload.SubscribeURL, timeout=60)
                logger.info(
                    "subscribed_webhook_to_topic",
                    webhook_id=awsSnsPayload.TopicArn,
                    subscribed_topic=awsSnsPayload.TopicArn,
                )
                log_ops_message(
                    request.state.bot.client,
                    f"Subscribed webhook {id} to topic {awsSnsPayload.TopicArn}",
                )
                return {"ok": True}
            if awsSnsPayload.Type == "UnsubscribeConfirmation":
                log_ops_message(
                    request.state.bot.client,
                    f"{awsSnsPayload.TopicArn} unsubscribed from webhook {id}",
                )
                return {"ok": True}
            if awsSnsPayload.Type == "Notification":
                blocks = aws.parse(awsSnsPayload, request.state.bot.client)
                # if we have an empty message, log that we have an empty
                # message and return without posting to slack
                if not blocks:
                    logger.info(
                        "payload_empty_message",
                    )
                    return {"ok": True}
                webhook_payload = WebhookPayload(blocks=blocks)
        case "AccessRequest":
            # Temporary fix for the Access Request payloads
            message = json.dumps(validated_payload)
            webhook_payload = WebhookPayload(text=message)
        case "UpptimePayload":
            # Temporary fix for Upptime payloads
            text = validated_payload.get("text", "")
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
            webhook_payload = WebhookPayload(blocks=blocks)
        case _:
            raise HTTPException(
                status_code=500,
                detail="Invalid payload type. Must be a WebhookPayload object or a recognized string payload type.",
            )
    return WebhookPayload(**webhook_payload.model_dump(exclude_none=True))


def append_incident_buttons(payload: WebhookPayload, webhook_id):
    if payload.attachments is None:
        payload.attachments = []
    elif isinstance(payload.attachments, str):
        payload.attachments = [payload.attachments]
    payload.attachments += [
        {
            "fallback": "Incident",
            "callback_id": "handle_incident_action_buttons",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "call-incident",
                    "text": "🎉   Call incident ",
                    "type": "button",
                    "value": payload.text,
                    "style": "primary",
                },
                {
                    "name": "ignore-incident",
                    "text": "🙈   Acknowledge and ignore",
                    "type": "button",
                    "value": webhook_id,
                    "style": "default",
                },
            ],
        }
    ]
    return payload
