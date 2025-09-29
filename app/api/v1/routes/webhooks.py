import json
from typing import Union, Dict, Any

from api.dependencies.rate_limits import get_limiter
from core.logging import get_module_logger
from fastapi import APIRouter, HTTPException, Request, Body
from integrations.sentinel import log_to_sentinel
from models.webhooks import (
    WebhookPayload,
)
from modules.slack import webhooks
from modules.webhooks.base import handle_webhook_payload


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
