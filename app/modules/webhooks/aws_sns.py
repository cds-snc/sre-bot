import requests
from core.logging import get_module_logger
from core.config import settings
from fastapi import HTTPException
from models.webhooks import AwsSnsPayload, WebhookPayload, WebhookResult
from modules.ops.notifications import log_ops_message
from modules.webhooks.aws_sns_notification import process_aws_notification_payload
from slack_sdk import WebClient
from sns_message_validator import (
    InvalidCertURLException,
    InvalidMessageTypeException,
    InvalidSignatureVersionException,
    SignatureVerificationFailureException,
    SNSMessageValidator,
)

logger = get_module_logger()
sns_message_validator = SNSMessageValidator()


def process_aws_sns_payload(payload: AwsSnsPayload, client: WebClient) -> WebhookResult:
    """Process the AWS SNS payload and return the blocks to be sent to Slack."""
    aws_sns_payload = validate_sns_payload(
        payload,
        client,
    )
    webhook_result = WebhookResult(
        status="error",
        action="none",
        payload=None,
        message="Unhandled AWS SNS payload type",
    )
    if aws_sns_payload.Type == "SubscriptionConfirmation":
        requests.get(aws_sns_payload.SubscribeURL, timeout=60)
        logger.info(
            "subscribed_webhook_to_topic",
            webhook_id=aws_sns_payload.TopicArn,
            subscribed_topic=aws_sns_payload.TopicArn,
        )
        log_ops_message(
            f"Subscribed webhook {id} to topic `{aws_sns_payload.TopicArn}`",
        )
        webhook_result = WebhookResult(status="success", action="log", payload=None)

    if aws_sns_payload.Type == "UnsubscribeConfirmation":
        log_ops_message(
            f"`{aws_sns_payload.TopicArn}` unsubscribed from webhook {id}",
        )
        webhook_result = WebhookResult(status="success", action="log", payload=None)

    if aws_sns_payload.Type == "Notification":
        blocks = process_aws_notification_payload(aws_sns_payload, client)
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
    return webhook_result


def validate_sns_payload(awsSnsPayload: AwsSnsPayload, client):
    """Validate the AWS SNS payload using the sns_message_validator library and return the valid payload or raise an HTTPException.
    Args:
        awsSnsPayload (AwsSnsPayload): The AWS SNS payload to be validated.
        client: The Slack WebClient instance to log operational messages.
    Raises:
        HTTPException: If the payload is invalid or if there is an error during validation.
    Returns:
        AwsSnsPayload: The validated AWS SNS payload.
    """

    if not settings.is_production:
        return awsSnsPayload
    try:
        valid_payload = AwsSnsPayload.model_validate(awsSnsPayload)
        sns_message_validator.validate_message(message=valid_payload.model_dump())
    except (
        InvalidMessageTypeException,
        InvalidSignatureVersionException,
        SignatureVerificationFailureException,
        InvalidCertURLException,
    ) as e:
        logger.exception("aws_sns_payload_validation_error", error=str(e))
        log_message = f"Failed to validate AWS event message due to {e.__class__.__qualname__}: {e}"
        if isinstance(e, InvalidMessageTypeException):
            log_message = f"Invalid message type ```{awsSnsPayload.Type}``` in message: ```{awsSnsPayload}```"
        elif isinstance(e, InvalidSignatureVersionException):
            log_message = f"Unexpected signature version ```{awsSnsPayload.SignatureVersion}``` in message: ```{awsSnsPayload}```"
        elif isinstance(e, InvalidCertURLException):
            log_message = f"Invalid certificate URL ```{awsSnsPayload.SigningCertURL}``` in message: ```{awsSnsPayload}```"
        elif isinstance(e, SignatureVerificationFailureException):
            log_message = f"Failed to verify signature ```{awsSnsPayload.Signature}``` in message: ```{awsSnsPayload}```"
        log_ops_message(log_message)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
        ) from e
    except Exception as e:
        logger.exception(
            "aws_sns_payload_validation_error",
            error=str(e),
        )
        log_ops_message(
            f"Error parsing AWS event due to {e.__class__.__qualname__}: ```{awsSnsPayload}```",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
        ) from e
    return valid_payload
