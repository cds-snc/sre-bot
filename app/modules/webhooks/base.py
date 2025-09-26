from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel
from core.logging import get_module_logger
from models.utils import select_best_model
from models.webhooks import WebhookPayload, AwsSnsPayload, AccessRequest, UpptimePayload

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
