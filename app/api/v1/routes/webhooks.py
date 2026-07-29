import json
from typing import Any

import structlog
from fastapi import APIRouter, Body, HTTPException, Request
from slack_sdk import WebClient

from infrastructure.security import get_limiter
from integrations.sentinel import log_to_sentinel
from models.webhooks import WebhookPayload
from modules.slack import webhooks
from modules.webhooks.base import handle_webhook_payload
from modules.webhooks.slack import hydrate_ip_addresses, map_emails_to_slack_users

logger = structlog.get_logger()
router = APIRouter(tags=["Webhooks"])
limiter = get_limiter()

SIGNATURE_HEADER_CANDIDATES = (
    "x-hub-signature",
    "x-hub-signature-256",
    "x-webhook-signature",
)


def _get_bot_client(request: Request) -> WebClient | None:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return None
    return getattr(bot, "client", None)


def _signing_indicator_present(request: Request) -> bool:
    headers = request.headers
    if any(header_name in headers for header_name in SIGNATURE_HEADER_CANDIDATES):
        return True
    return any("signature" in header_name.lower() for header_name in headers)


@router.post("/hook/{webhook_id}")
@limiter.limit(
    "300/minute"
)  # since some slack channels use this for alerting, we want to be generous with the rate limiting on this one
def handle_webhook(
    webhook_id: str,
    request: Request,
    payload: dict[Any, Any] | str = Body(...),  # noqa: B008 -- FastAPI dependency injection requires a call in the default
):
    """Handle incoming webhook requests and post to Slack channel.

    Emits a `webhook_invocation` event with request-origin fingerprint metadata
    to seed sender inventory analysis per webhook_id and matched payload type.
    This supports migration from legacy unsigned webhook senders toward signed
    authentication tiers while keeping request handling behavior unchanged.

    Query example (CloudWatch Logs Insights):
    fields @timestamp, webhook_id, matched_payload_type, signing_indicator_present
    | filter event = "webhook_invocation"
    | stats count() by webhook_id, matched_payload_type

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
    log = logger.bind(
        webhook_id=webhook_id,
        path=request.url.path,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else "unknown",
    )

    fingerprint = {
        "webhook_id": webhook_id,
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent"),
        "signing_indicator_present": _signing_indicator_present(request),
        "matched_payload_type": None,
    }

    try:
        if isinstance(payload, dict):
            payload_dict = payload
        else:
            try:
                payload_dict = json.loads(payload)
            except json.JSONDecodeError as e:
                log.error("payload_validation_error", error=str(e), payload=str(payload))
                raise HTTPException(status_code=400, detail=str(e)) from e

        webhook = webhooks.get_webhook(webhook_id)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        if not webhook.get("active", {}).get("BOOL", False):
            log.info("webhook_not_active", error="Webhook is not active")
            raise HTTPException(status_code=404, detail="Webhook not active")
        webhooks.increment_invocation_count(webhook_id)

        webhook_result = handle_webhook_payload(payload_dict, request)
        fingerprint["matched_payload_type"] = webhook_result.matched_payload_type

        if webhook_result.status == "error":
            status_code = 400
            if webhook_result.message == "Slack bot not initialized":
                status_code = 503
            raise HTTPException(
                status_code=status_code,
                detail=webhook_result.message or "Invalid payload",
            )

        if webhook_result.action == "post" and isinstance(webhook_result.payload, WebhookPayload):
            webhook_payload = webhook_result.payload
            webhook_payload = map_emails_to_slack_users(webhook_payload)
            webhook_payload = hydrate_ip_addresses(webhook_payload)
            webhook_payload.channel = webhook["channel"]["S"]
            hook_type = webhook.get("hook_type", {}).get("S", "alert")  # Default to "alert" if hook_type is missing
            if hook_type == "alert":
                webhook_payload = append_incident_buttons(webhook_payload, webhook_id)

            webhook_payload_parsed = webhook_payload.model_dump(exclude_none=True)

            bot_client = _get_bot_client(request)
            if bot_client is None:
                log.error("slack_bot_unavailable")
                raise HTTPException(
                    status_code=503,
                    detail="Slack bot not initialized",
                )

            try:
                bot_client.api_call("chat.postMessage", json=webhook_payload_parsed)
                log_to_sentinel(
                    "webhook_sent",
                    {"webhook": webhook, "payload": webhook_payload_parsed},
                )

            except Exception as e:
                log.exception(
                    "webhook_posting_error",
                    error=str(e),
                )
                raise HTTPException(status_code=500, detail="Failed to send message") from e

        return {"ok": True}
    finally:
        log.info("webhook_invocation", **fingerprint)


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
