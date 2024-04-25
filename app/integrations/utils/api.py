"""Utilities for API integrations."""
import re


def convert_string_to_camel_case(snake_str):
    """Convert a snake_case string to camelCase."""
    if not isinstance(snake_str, str):
        raise TypeError("Input must be a string")
    components = snake_str.split("_")
    if len(components) == 1:
        return components[0]
    else:
        return components[0] + "".join(
            x[0].upper() + x[1:] if x else "" for x in components[1:]
        )


def convert_dict_to_camel_case(dict):
    """Convert all keys in a dictionary from snake_case to camelCase."""
    new_dict = {}
    for k, v in dict.items():
        new_key = convert_string_to_camel_case(k)
        new_dict[new_key] = convert_kwargs_to_camel_case(v)
    return new_dict


def convert_kwargs_to_camel_case(kwargs):
    """Convert all keys in a list of dictionaries from snake_case to camelCase."""
    if isinstance(kwargs, dict):
        return convert_dict_to_camel_case(kwargs)
    elif isinstance(kwargs, list):
        return [convert_kwargs_to_camel_case(i) for i in kwargs]
    else:
        return kwargs


def convert_string_to_pascal_case(snake_str):
    """Convert a snake_case string to PascalCase."""
    if not isinstance(snake_str, str):
        raise TypeError("Input must be a string")
    # Convert camelCase to snake_case
    snake_str = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", snake_str)
    snake_str = re.sub("([a-z0-9])([A-Z])", r"\1_\2", snake_str).lower()

    components = snake_str.split("_")
    if len(components) == 1 and components[0] != "":
        # return components[0]
        return snake_str[0].upper() + snake_str[1:]
    else:
        return "".join(x.title() for x in components)


def convert_dict_to_pascale_case(dict):
    """Convert all keys in a dictionary from snake_case to PascalCase."""
    new_dict = {}
    for k, v in dict.items():
        new_key = convert_string_to_pascal_case(k)
        new_dict[new_key] = convert_kwargs_to_pascal_case(v)
    return new_dict


def convert_kwargs_to_pascal_case(kwargs):
    """Convert all keys in a list of dictionaries from snake_case to PascalCase."""
    if isinstance(kwargs, dict):
        return convert_dict_to_pascale_case(kwargs)
    elif isinstance(kwargs, list):
        return [convert_kwargs_to_pascal_case(i) for i in kwargs]
    else:
        return kwargs
