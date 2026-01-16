"""Schema-driven argument inference from Pydantic models.

Provides utilities to automatically infer Argument definitions from Pydantic
schema fields when arguments=None is provided to @register() decorator.
"""

from typing import List, get_origin, get_args, Union
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from infrastructure.platforms.parsing import Argument, ArgumentType


def infer_arguments_from_schema(
    schema: type,
) -> List[Argument]:
    """Infer Argument definitions from Pydantic model schema.

    Examines a Pydantic BaseModel and generates Argument definitions
    for each field, inferring types and defaults from the schema.

    Args:
        schema: Pydantic BaseModel class to analyze.

    Returns:
        List of inferred Argument definitions.

    Type Mapping:
        - str with email validator → ArgumentType.EMAIL
        - str → ArgumentType.STRING
        - int → ArgumentType.INTEGER
        - bool → ArgumentType.BOOLEAN
        - List[str] → ArgumentType.CSV
        - Literal or enum → ArgumentType.CHOICE

    Example:
        >>> class AddMemberRequest(BaseModel):
        ...     email: str
        ...     group_id: str
        ...     role: str = "MEMBER"
        ...
        >>> args = infer_arguments_from_schema(AddMemberRequest)
        >>> len(args) == 3
        >>> args[0].name == "email"
        >>> args[0].required == True
        >>> args[2].default == "MEMBER"
    """
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise TypeError(f"Expected Pydantic BaseModel, got {type(schema)}")

    arguments: List[Argument] = []
    model_fields = schema.model_fields

    for field_name, field_info in model_fields.items():
        arg_type = _infer_argument_type(field_info.annotation)
        is_required = field_info.is_required()

        # Convert PydanticUndefined to None
        default_value = field_info.default
        if default_value is PydanticUndefined:
            default_value = None

        argument = Argument(
            name=field_name,
            type=arg_type,
            required=is_required,
            description=field_info.description or "",
            default=default_value,
        )

        arguments.append(argument)

    return arguments


def _infer_argument_type(python_type: type) -> ArgumentType:
    """Infer ArgumentType from Python type hint.

    Maps Python types to ArgumentType enum values.

    Args:
        python_type: Python type hint from schema field.

    Returns:
        Inferred ArgumentType.
    """
    # Handle Optional types (Union[X, None])
    origin = get_origin(python_type)
    if origin is Union:
        args = get_args(python_type)
        # Filter out NoneType and get the actual type
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            return _infer_argument_type(non_none_args[0])

    # Handle List types
    if origin is list:
        args = get_args(python_type)
        if args and args[0] is str:
            return ArgumentType.CSV
        return ArgumentType.STRING

    # Handle basic types
    if python_type is str:
        return ArgumentType.STRING

    if python_type is int:
        return ArgumentType.INTEGER

    if python_type is bool:
        return ArgumentType.BOOLEAN

    # Default to STRING for unknown types
    return ArgumentType.STRING


def _has_email_validator(field_info) -> bool:
    """Check if a field has email validation.

    Args:
        field_info: Pydantic FieldInfo object.

    Returns:
        True if field has email validation.
    """
    # Check validators (Pydantic v2)
    if hasattr(field_info, "metadata"):
        metadata_str = str(field_info.metadata).lower()
        if "email" in metadata_str:
            return True

    # Check constraints
    if hasattr(field_info, "constraints"):
        for constraint in field_info.constraints:
            if "email" in str(constraint).lower():
                return True

    return False
