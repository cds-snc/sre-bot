import json
from typing import Union, Dict, Any, cast

import requests  # type: ignore
from api.dependencies.rate_limits import get_limiter
from core.logging import get_module_logger
from fastapi import APIRouter, HTTPException, Request, Body
from integrations.sentinel import log_to_sentinel
from models.webhooks import (
    AwsSnsPayload,
    WebhookPayload,
    AccessRequest,
    UpptimePayload,
    WebhookResult,
)
from modules.slack import webhooks
from modules.webhooks.base import validate_payload
from server.event_handlers import aws
from server.utils import log_ops_message


logger = get_module_logger()
router = APIRouter(tags=["Access"])
limiter = get_limiter()


@router.post("/hook/{webhook_id}")
@limiter.limit(
    "30/minute"
)  # since some slack channels use this for alerting, we want to be generous with the rate limiting on this one
def handle_webhook(
    webhook_id: str,
    request: Request,
    payload: Union[Dict[Any, Any], str] = Body(...),
):
    """Handle incoming webhook requests and post to Slack channel.

    Args:
        webhook_id (str): The ID of the webhook to handle.
        request (Request): The incoming HTTP request.
        payload (Union[Dict[Any, Any], str]): The incoming webhook payload, either as
            a JSON string or a dictionary.

    Raises:
        HTTPException: If the webhook is not found, not active, or if there are issues
            with payload validation or posting to Slack.
    Returns:
        dict: A dictionary indicating success if the message was posted successfully.
    """
    if isinstance(payload, dict):
        payload_dict = payload
    else:
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error("payload_validation_error", error=str(e), payload=str(payload))
            raise HTTPException(status_code=400, detail=str(e)) from e

    webhook = webhooks.get_webhook(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if not webhook.get("active", {}).get("BOOL", False):
        logger.info(
            "webhook_not_active",
            webhook_id=webhook_id,
            error="Webhook is not active",
        )
        raise HTTPException(status_code=404, detail="Webhook not active")
    webhooks.increment_invocation_count(webhook_id)

    webhook_result = handle_webhook_payload(payload_dict, request)

    if webhook_result.status == "error":
        raise HTTPException(status_code=400, detail="Invalid payload")

    if webhook_result.action == "post" and isinstance(
        webhook_result.payload, WebhookPayload
    ):
        webhook_payload = webhook_result.payload
        webhook_payload.channel = webhook["channel"]["S"]
        hook_type = webhook.get("hook_type", {}).get(
            "S", "alert"
        )  # Default to "alert" if hook_type is missing
        if hook_type == "alert":
            webhook_payload = append_incident_buttons(webhook_payload, webhook_id)

        webhook_payload_parsed = webhook_payload.model_dump(exclude_none=True)

        try:
            request.state.bot.client.api_call(
                "chat.postMessage", json=webhook_payload_parsed
            )
            log_to_sentinel(
                "webhook_sent",
                {"webhook": webhook, "payload": webhook_payload_parsed},
            )

        except Exception as e:
            logger.exception(
                "webhook_posting_error",
                webhook_id=webhook_id,
                error=str(e),
            )
            raise HTTPException(status_code=500, detail="Failed to send message") from e

    return {"ok": True}


def handle_webhook_payload(
    payload_dict: dict,
    request: Request,
) -> WebhookResult:
    """Process and validate the webhook payload.

    Returns:
        dict: A dictionary containing:
            - status (str): The status of the operation (e.g., "success", "error").
            - action (Literal["post", "log", "none"]): The action to take.
            - payload (Optional[WebhookPayload]): The payload to post, if applicable.
    """
    logger.info("processing_webhook_payload", payload=payload_dict)
    payload_validation_result = validate_payload(payload_dict)

    webhook_result = WebhookResult(
        status="error", message="Failed to process payload for unknown reasons"
    )
    if payload_validation_result is not None:
        payload_type, validated_payload = payload_validation_result
    else:
        error_message = "No matching model found for payload"
        return WebhookResult(status="error", message=error_message)

    match payload_type.__name__:
        case "WebhookPayload":
            webhook_result = WebhookResult(
                status="success", action="post", payload=validated_payload
            )
        case "AwsSnsPayload":
            aws_sns_payload_instance = cast(AwsSnsPayload, validated_payload)
            aws_sns_payload = aws.validate_sns_payload(
                aws_sns_payload_instance,
                request.state.bot.client,
            )

            if aws_sns_payload.Type == "SubscriptionConfirmation":
                requests.get(aws_sns_payload.SubscribeURL, timeout=60)
                logger.info(
                    "subscribed_webhook_to_topic",
                    webhook_id=aws_sns_payload.TopicArn,
                    subscribed_topic=aws_sns_payload.TopicArn,
                )
                log_ops_message(
                    request.state.bot.client,
                    f"Subscribed webhook {id} to topic {aws_sns_payload.TopicArn}",
                )
                webhook_result = WebhookResult(
                    status="success", action="log", payload=None
                )

            if aws_sns_payload.Type == "UnsubscribeConfirmation":
                log_ops_message(
                    request.state.bot.client,
                    f"{aws_sns_payload.TopicArn} unsubscribed from webhook {id}",
                )
                webhook_result = WebhookResult(
                    status="success", action="log", payload=None
                )

            if aws_sns_payload.Type == "Notification":
                blocks = aws.parse(aws_sns_payload, request.state.bot.client)
                if not blocks:
                    logger.info(
                        "payload_empty_message",
                        payload_type="AwsSnsPayload",
                        sns_type=aws_sns_payload.Type,
                    )
                    return WebhookResult(
                        status="error",
                        action="none",
                        message="Empty AWS SNS Notification message",
                    )
                webhook_result = WebhookResult(
                    status="success",
                    action="post",
                    payload=WebhookPayload(blocks=blocks),
                )

        case "AccessRequest":
            message = str(cast(AccessRequest, validated_payload).model_dump())
            webhook_result = WebhookResult(
                status="success",
                action="post",
                payload=WebhookPayload(text=message),
            )

        case "UpptimePayload":
            text = cast(UpptimePayload, validated_payload).text
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
            webhook_result = WebhookResult(
                status="success",
                action="post",
                payload=WebhookPayload(blocks=blocks),
            )

        case _:
            webhook_result = WebhookResult(
                status="error",
                message="No matching model found for payload",
            )

    return webhook_result


def append_incident_buttons(payload: WebhookPayload, webhook_id) -> WebhookPayload:
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
