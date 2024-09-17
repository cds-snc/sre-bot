from typing import Any, Dict, List, Type
from pydantic import BaseModel


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
