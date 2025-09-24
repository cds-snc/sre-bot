from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel
from core.logging import get_module_logger

logger = get_module_logger()


def get_parameters_from_model(model: Type[BaseModel]) -> List[str]:
    return list(model.model_fields.keys())


def get_dict_of_parameters_from_models(
    models: List[Type[BaseModel]],
) -> Dict[str, List[str]]:
    """
    Returns a dictionary of model names and their parameters as a list.

    Args:
        models (List[Type[BaseModel]]): A list of models to extract parameters from.

    Returns:
        Dict[str, List[str]]: A dictionary of model names and their parameters as a list.

    Example:
        ```python
        class User(BaseModel):
            id: str
            username: str
            password: str
            email: str

        class Webhook(BaseModel):
            id: str
            channel: str
            name: str
            created_at: str

        get_dict_of_parameters_from_models([User, Webhook])
        # Output:
        # {
        #     "User": ["id", "username", "password", "email"],
        #     "Webhook": ["id", "channel", "name", "created_at"]
        # }
        ```
    """
    return {model.__name__: get_parameters_from_model(model) for model in models}


def is_parameter_in_model(model_params: List[str], payload: Dict[str, Any]) -> bool:
    return any(param in model_params for param in payload.keys())


def has_parameters_in_model(model_params: List[str], payload: Dict[str, Any]) -> int:
    """Returns the number of parameters in the payload that are in the model."""
    return sum(1 for param in model_params if param in payload.keys())


def are_all_parameters_in_model(
    model_params: List[str], payload: Dict[str, Any]
) -> bool:
    return all(param in model_params for param in payload.keys())


def select_best_model(
    data: dict,
    models: List[Type[BaseModel]],
    priorities: Optional[Dict[Type[BaseModel], int]] = None,
) -> Optional[BaseModel]:
    """
    Select the best matching model for the given data.

    Args:
        data (dict): The data to validate against the models.
        models (List[Type[BaseModel]]): The list of known models to validate against.
        priorities (Optional[Dict[Type[BaseModel], int]]): Optional dictionary of model priorities.

    Returns:
        Optional[BaseModel]: The best matching model instance, or None if no match is found.
    """
    best_match = None
    best_score = float("-inf")

    for model in models:
        # Get model fields and calculate overlap
        model_fields = set(model.__pydantic_fields__.keys())
        matching_fields = model_fields.intersection(data.keys())

        # Calculate score based on matching fields
        score = len(matching_fields) / len(model_fields)
        if priorities and model in priorities:
            score += priorities[model]

        # Only consider models that match at least one field
        if len(matching_fields) > 0:
            # Extract only the matched fields from data
            filtered_data = {key: data[key] for key in matching_fields}

            # Create model instance without validation
            instance = model.model_construct(**filtered_data)
            if score > best_score:
                best_score = score
                best_match = instance

    return best_match
