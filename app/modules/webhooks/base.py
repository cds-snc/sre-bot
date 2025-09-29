from typing import Any, Dict, List, Optional, Tuple, Type, cast

from fastapi import Request
from pydantic import BaseModel
import requests
from core.logging import get_module_logger
from models.utils import select_best_model
from models.webhooks import (
    WebhookPayload,
    AwsSnsPayload,
    AccessRequest,
    UpptimePayload,
    WebhookResult,
)
from modules.webhooks import aws
from modules.ops.notifications import log_ops_message

logger = get_module_logger()


def validate_payload(
    payload_dict: dict,
    priorities: Optional[Dict[Type[BaseModel], int]] = None,
) -> Optional[Tuple[Type[BaseModel], Any]]:
    """
    Wrapper around select_best_model to validate incoming webhook payloads.

    Args:
        payload (dict): The incoming webhook payload, either as a JSON string or a dictionary.
        priorities (Optional[Dict[Type[BaseModel], int]]): Optional dictionary of model priorities.

    Returns:
        Optional[BaseModel]: The validated payload as a Pydantic model, or None if validation fails.
    """
    models: List[Type[BaseModel]] = [
        WebhookPayload,
        AwsSnsPayload,
        AccessRequest,
        UpptimePayload,
    ]

    selected_model = select_best_model(payload_dict, models, priorities)
    if selected_model:
        model, validated_payload = selected_model
        logger.info(
            "payload_validation_success",
            model=model.__name__,
            payload=validated_payload.model_dump(),
        )
        return model, validated_payload
    else:
        logger.error("payload_validation_failure", payload=payload_dict)
        return None


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
