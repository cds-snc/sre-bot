from typing import Any, Dict, List, Type
from pydantic import BaseModel


def get_parameters_from_model(model: Type[BaseModel]) -> List[str]:
    return list(model.model_fields.keys())


def get_dict_of_parameters_from_models(
    models: List[Type[BaseModel]],
) -> Dict[str, List[str]]:
    return {model.__name__: get_parameters_from_model(model) for model in models}


def is_parameter_in_model(model_params: List[str], payload: Dict[str, Any]) -> bool:
    return any(param in model_params for param in payload.keys())


def are_all_parameters_in_model(
    model_params: List[str], payload: Dict[str, Any]
) -> bool:
    return all(param in model_params for param in payload.keys())
