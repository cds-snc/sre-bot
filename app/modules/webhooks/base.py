import json
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel
from core.logging import get_module_logger
from models.utils import select_best_model
from models.webhooks import WebhookPayload, AwsSnsPayload, AccessRequest, UpptimePayload

logger = get_module_logger()

MODELS = [WebhookPayload, AwsSnsPayload, AccessRequest, UpptimePayload]


def validate_payload(
    payload: str | dict,
    models: List[Type[BaseModel]],
    priorities: Optional[Dict[Type[BaseModel], int]] = None,
) -> Optional[Tuple[type[BaseModel], Any]]:
    """
    Validate the incoming webhook payload against the known models.

    Args:
        payload (str | dict): The incoming webhook payload, either as a JSON string or a dictionary.
        models (List[Type[BaseModel]]): The list of known models to validate against.
        priorities (Optional[Dict[Type[BaseModel], int]]): Optional dictionary of model priorities.

    Returns:
        Optional[BaseModel]: The validated payload as a Pydantic model, or None if validation fails.
    """
    if not models:
        logger.warning(
            "payload_validation_error", error="No models provided for validation"
        )
        return None
    payload_dict = None
    result = None
    # handle payload input types
    if isinstance(payload, str):
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("payload_validation_error", error="Invalid JSON payload")
            return None
    elif isinstance(payload, dict):
        payload_dict = payload
    else:
        logger.warning(
            "payload_validation_error",
            error="Unsupported payload type",
            payload_type=type(payload).__name__,
        )
        return None

    if payload_dict is not None:
        result = select_best_model(payload_dict, models, priorities)
    return result
